"""Acrobatics and symbol handling for the character controller (simulation side).

- **Structures**: a character standing on a platform or glyph top steps off when it walks past the end, and drops
  (the fall is physics). Walking into a structure is an authoring error (the dry run names it).
- `roll`: a forward roll along the surface (a landing roll when it follows a jump: it starts at touchdown).
- `vault`: over a low structure or prop. A hand plants on top, the legs swing over, and he lands on the far side.
- `climb`: onto a platform or glyph top. Jump up, hang from the edge, pull up, mantle, stand on top.
- `wall_kick`: run at a wall (a room wall or a structure's side), two steps up it, then push off into a ballistic
  jump (with `flip: back`, a back flip) that lands at `target_x`.
- `pick_up` a light prop (a glyph), carry it; `throw` it on a ballistic arc at a character or a point. A thrown
  prop that reaches a character hits (a reaction), is blocked by a guard, or misses one who ducks. All of this is
  decided geometrically in the simulation.

Flips (`jump_to` / `wall_kick` with `flip`) are driven in physics along a planned rotation that completes before the
landing (see `_flip_control`).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..core.mathx import Vec, clamp, wrap_angle
from ..scene import structures
from ..scene.schema import ActionSpec
from .interaction import _smooth

ACRO = ("roll", "vault", "climb", "wall_kick", "pick_up", "throw")
VAULT_MAX = 0.95  # x stand height: higher than this, climb
CARRY_MASS_G = 0.9  # a character lifts at most 0.9 x strength (force) overhead
PICK_T, THROW_T, THROW_RELEASE = 0.7, 0.62, 0.3
WALL_T = (0.24, 0.42, 0.52)  # first foot on the wall, second foot, push-off


def keys_at(keys: Sequence[Tuple[float, Any]], u: float):
    """Smoothly interpolated key values (numbers or tuples) at u."""
    for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
        if u <= u1:
            w = _smooth((u - u0) / (u1 - u0)) if u1 > u0 else 1.0
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * w for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * w
    return keys[-1][1]


def _seg_dist(p: Vec, q: Vec, a: Vec, b: Vec) -> Tuple[float, Vec]:
    """Distance between segments pq and ab (and the closest point on pq)."""
    def pt_seg(x, a, b):
        ax, ay = b[0] - a[0], b[1] - a[1]
        L = ax * ax + ay * ay
        u = 0.0 if L < 1e-9 else clamp(((x[0] - a[0]) * ax + (x[1] - a[1]) * ay) / L, 0.0, 1.0)
        c = (a[0] + ax * u, a[1] + ay * u)
        return math.dist(x, c), c
    best = (math.inf, p)
    for x, (s0, s1), onpq in ((p, (a, b), True), (q, (a, b), True), (a, (p, q), False), (b, (p, q), False)):
        d, c = pt_seg(x, s0, s1)
        if d < best[0]:
            best = (d, x if onpq else c)
    return best


class AcroMixin:
    # ------------------------------------------------------------ structures: support and blocking
    def _acro_init(self) -> None:
        self.blocks = structures.blocks(self.env)
        self.thrown: Optional[Dict[str, Any]] = None
        self.carry_log: List[List[Any]] = []  # [prop, t_from, t_to] (for the animation: both hands hold it)

    def _upright(self) -> bool:
        return abs(self.frame.normal[1] - 1.0) < 1e-6 and abs(self.frame.normal[0]) < 1e-6

    def _feet_y(self) -> float:
        return self.frame.origin[1]

    def _path_blocker(self, s0: float, s1: float, top: Optional[float] = None):
        """The first structure face ahead between s0 and s1 that the body would walk into (upright surfaces only)."""
        if not self._upright() or abs(s1 - s0) < 1e-6:
            return None
        d = 1.0 if s1 > s0 else -1.0
        fy = self._feet_y()
        hi = fy + (top if top is not None else self.stand_h + 40.0)
        best = None
        for b in self.blocks:
            if b.y1 <= fy + 12.0 or b.y0 >= hi:
                continue
            face = b.x0 if d > 0 else b.x1
            if (face - s0) * d > -4.0 and (s1 - face) * d > -10.0:
                if best is None or (face - s0) * d < (best[0] - s0) * d:
                    best = (face, b)
        return best

    def _check_walk(self, t: float, a: ActionSpec) -> ActionSpec:
        hit = self._path_blocker(self.s, a.target_x)
        if hit is None:
            return a
        face, b = hit
        d = 1.0 if a.target_x > self.s else -1.0
        msg = (f"{self.cid}: walking from x {self.s:.0f} to {a.target_x:.0f} runs into structure '{b.owner}' (face at x {face:.0f}); "
               f"vault over it, climb onto it or jump_to onto it")
        if self.strict:
            raise ValueError(msg)
        self.violation = self.violation or msg
        return a.model_copy(update={"target_x": face - d * 14.0})

    def _edge_check(self, t: float) -> bool:
        F = self.frame
        if not F.bounded or self.mode != "grounded" or self.posture != "stand" or (self.cur is not None and self.cur.type in ("climb",)):
            return False
        if F.lo - 3.0 <= self.s <= F.hi + 3.0:
            return False
        self._step_off(t)
        return True

    def _step_off(self, t: float) -> None:
        from .controller import MASS, Event
        tan = self.frame.tangent
        v = self.v if abs(self.v) > 20.0 else self.facing * 60.0
        self.world.set_dynamic(self.cid, (tan[0] * v, tan[1] * v), 0.0, MASS, self.moment)
        st = self.world.state(self.cid)
        self.mode = "airborne"
        self.air = {"intent": "jump", "t0": t, "drop": True, "ang0": st.angle}
        self.overlay = None
        if self.cur is not None and self.cur.type in ("walk_to", "run_to"):
            self.queue.appendleft(self.cur)  # keeps walking once down (lands into the walk)
        self.cur = None
        self.body_tilt = 0.0
        self._open("airborne", t, intent="jump", drop=True)
        self.emit(Event(t, "step_off", self.cid, {"surface": self.frame.tag, "point": st.pos}))

    def _top_of(self, ref: str, near_s: Optional[float] = None):
        return structures.obstacle_top(self.env, self.frames, ref.split(":", 1)[1], near_s)

    def _target_bounds(self, ref: str) -> Tuple[float, float, float, float]:
        kind, _, rid = ref.partition(":")
        if kind == "obstacle":
            return structures.obstacle_bounds(self.env, rid)
        sp = self.props[rid]
        if sp.kind == "glyph":
            from ..scene import glyphs
            ex = glyphs.extent(sp.glyph, sp.size, sp.weight or glyphs.default_weight(sp.size))
            pts = [self._prop_point(rid, (x, y)) for x in (ex[0], ex[2]) for y in (ex[1], ex[3])]
        else:
            hx, hy = sp.size[0] / 2, sp.size[1] / 2
            pts = [self._prop_point(rid, (x, y)) for x in (-hx, hx) for y in (-hy, hy)]
        return min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)

    def _fail(self, msg: str) -> None:
        if self.strict:
            raise ValueError(msg)
        self.violation = self.violation or msg

    # ------------------------------------------------------------ action start
    def _start_acro(self, t: float, a: ActionSpec, landing: Optional[float] = None) -> None:
        if a.type != "throw" and a.type != "pick_up" and not self._upright():
            self._fail(f"{self.cid}: '{a.type}' needs an upright floor-like surface")
            self._next_action(t)
            return
        if a.type == "roll":
            self._start_roll(t, a, landing)
        else:
            getattr(self, f"_start_{a.type}")(t, a)

    def _tick_acro(self, t: float, dt: float, a: ActionSpec) -> None:
        getattr(self, f"_{a.type}_tick")(t, dt, a)

    # ------------------------------------------------------------ roll
    def _start_roll(self, t: float, a: ActionSpec, landing: Optional[float] = None) -> None:
        from .controller import Event
        d = self.facing
        dist = a.distance or 1.6 * self.stand_h
        if a.target_x is not None:
            d = 1.0 if a.target_x >= self.s else -1.0
            dist = abs(a.target_x - self.s)
            if landing is None and self._face(t, a, d):
                return
        hit = self._path_blocker(self.s, self.s + d * dist, top=0.78 * self.stand_h)  # a roll fits under a high beam
        if hit is not None:
            self._fail(f"{self.cid}: the roll runs into structure '{hit[1].owner}'")
        T = clamp(0.32 + dist / 330.0, 0.55, 1.25)
        self.inter = {"t0": t, "s0": self.s, "h0": min(self.h, self.stand_h), "d": d, "dist": dist, "T": T,
                      "v0": abs(self.v) if landing is not None else 0.0}
        self.v = 0.0
        self.facing = d
        self._open("roll", t, s0=self.s, d=d, dist=dist, T=T, landing=landing)
        self.emit(Event(t, "roll_start", self.cid, {"surface": self.frame.tag, "point": self.frame.to_world(self.s, 0.0),
                                                    "landing": landing is not None}))

    def _roll_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        u = clamp((t - I["t0"]) / I["T"], 0.0, 1.0)
        d, R, off = I["d"], 0.4 * self.stand_h, 0.3 * self.stand_h  # tucked body: a ball, the hips over the top when inverted
        carry = clamp(I["v0"] * I["T"] / max(I["dist"], 1.0), 0.0, 1.0)  # a landing roll starts at the landing speed
        prog = (0.35 + 0.4 * carry) * u + (0.65 - 0.4 * carry) * _smooth(u)
        rot = 2 * math.pi * _smooth(clamp((u - 0.1) / 0.78, 0.0, 1.0))
        w = _smooth(u / 0.14) * (1.0 - _smooth((u - 0.86) / 0.14))
        s_c = I["s0"] + d * I["dist"] * prog
        ball_s, ball_h = s_c - d * off * math.sin(rot), R - off * math.cos(rot)
        stand_h = I["h0"] + (self.stand_h - I["h0"]) * _smooth(u)
        self.s = s_c + (ball_s - s_c) * w
        self.h = stand_h + (ball_h - stand_h) * w
        self.body_tilt = rot if u < 1.0 else 0.0
        if u >= 1.0:
            self.body_tilt, self.h = 0.0, self.stand_h
            self.emit(Event(t, "roll_end", self.cid, {"surface": self.frame.tag}))
            self._next_action(t)

    # ------------------------------------------------------------ vault
    def _start_vault(self, t: float, a: ActionSpec) -> None:
        x0, x1, y0, y1 = self._target_bounds(a.target)
        fy = self._feet_y()
        if y1 - fy > VAULT_MAX * self.stand_h:
            self._fail(f"{self.cid}: '{a.target}' is {y1 - fy:.0f} high, too high to vault (max {VAULT_MAX * self.stand_h:.0f}); climb onto it")
            self._next_action(t)
            return
        d = 1.0 if self.s < (x0 + x1) / 2 else -1.0
        near, far = (x0, x1) if d > 0 else (x1, x0)
        start = near - d * 0.5 * self.stand_h
        if self._go(t, a, start, run=bool(a.speed and a.speed > 250)) or self._face(t, a, d):
            return
        T = 0.55 + abs(far - near) / 700.0
        land = far + d * 0.55 * self.stand_h
        plant = (near + d * min(14.0, abs(far - near) / 3.0), y1)
        self.inter = {"t0": t, "s0": self.s, "s1": land, "top": y1 - fy, "T": T, "d": d, "plant": plant, "said": False}
        self._open("vault", t, s0=self.s, s1=land, plant=plant, top=y1, T=T, d=d, target=a.target)
        from .controller import Event
        self.emit(Event(t, "vault_start", self.cid, {"target": a.target}))

    def _vault_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        u = clamp((t - I["t0"]) / I["T"], 0.0, 1.0)
        peak = max(I["top"] + 0.36 * self.stand_h, self.stand_h + 8.0)
        self.s = I["s0"] + (I["s1"] - I["s0"]) * (0.25 * u + 0.75 * _smooth(u))
        self.h = keys_at([(0.0, self.stand_h - 4.0), (0.18, self.stand_h - 20.0), (0.5, peak), (0.86, 0.86 * self.stand_h),
                          (1.0, 0.8 * self.stand_h)], u)
        self.body_tilt = keys_at([(0.0, 0.1), (0.3, 0.5), (0.6, 0.32), (1.0, 0.06)], u)
        if not I["said"] and u >= 0.3:
            I["said"] = True
            self.emit(Event(t, "vault", self.cid, {"target": a.target, "point": I["plant"]}))
        if u >= 1.0:
            self._soft_land(t, 380.0, I["d"] * 110.0)

    def _soft_land(self, t: float, approach: float, vt: float) -> None:
        """Land at the end of a keyed move (vault): the landing absorption plays as after a real touchdown."""
        from .controller import Event
        self.body_tilt = 0.0
        self.mode = "landing"
        self.land = {"t_contact": t, "s0": self.s, "h0": min(self.h, self.stand_h), "approach": approach, "vt": vt, "ang0": 0.0,
                     "w0": 0.0}
        self.cur = None
        self._open("landing", t, **self.land)
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.frame.body_angle)
        self.emit(Event(t, "impact", self.cid, {"surface": self.frame.tag, "normal_speed": approach,
                                                "point": self.frame.to_world(self.s, 0.0), "tangent_speed": vt}))

    # ------------------------------------------------------------ ledge climb
    def _start_climb(self, t: float, a: ActionSpec) -> None:
        from .controller import Event
        F = self._top_of(a.target, self.s)
        if F.lo <= self.s <= F.hi:
            self._fail(f"{self.cid}: already under or on '{a.target}'; climb from beside it")
            self._next_action(t)
            return
        d = 1.0 if self.s < F.lo else -1.0
        edge = F.lo if d > 0 else F.hi
        fy, top = self._feet_y(), F.origin[1]
        H = top - fy
        reach = self.stand_h + self.shoulder_up + self.arm_reach + 120.0
        if H > reach:
            self._fail(f"{self.cid}: the top of '{a.target}' is {H:.0f} high, out of reach (max {reach:.0f})")
            self._next_action(t)
            return
        if H < 0.45 * self.stand_h:
            self._fail(f"{self.cid}: '{a.target}' is only {H:.0f} high; walk_to or vault instead of climb")
            self._next_action(t)
            return
        base = edge - d * 0.3 * self.stand_h
        if self._go(t, a, base) or self._face(t, a, d):
            return
        sh, ar = self.shoulder_up, self.arm_reach
        hang_y = top - (sh + 0.9 * ar)
        hang = hang_y - fy > self.stand_h + 6.0
        P0 = (self.s, fy + self.stand_h)
        P1 = (self.s, fy + self.stand_h - 24.0)
        # hanging and pulling up, the hips stay outside the end face of the top (the chest comes over the edge)
        P2 = (edge - d * 0.28 * self.stand_h, hang_y) if hang else (edge - d * 0.28 * self.stand_h, max(fy + self.stand_h, top - sh - 0.55 * ar))
        P4 = (edge - d * 0.28 * self.stand_h, top - 0.05 * self.stand_h)
        P5 = (edge + d * 0.22 * self.stand_h, top + 0.45 * self.stand_h)
        P6 = (edge + d * 0.42 * self.stand_h, top + self.stand_h)
        times = [0.0, 0.2, 0.5, 0.7 if hang else 0.52, 0.0, 0.0, 0.0]
        times[4] = times[3] + 0.42
        times[5] = times[4] + 0.4
        times[6] = times[5] + 0.36
        T = times[6]
        keys = [(times[0] / T, P0), (times[1] / T, P1), (times[2] / T, P2), (times[3] / T, P2), (times[4] / T, P4), (times[5] / T, P5), (1.0, P6)]
        tilt = [(times[0] / T, 0.0), (times[1] / T, 0.08), (times[2] / T, 0.0), (times[3] / T, 0.0), (times[4] / T, 0.35), (times[5] / T, 0.45),
                (1.0, 0.0)]
        self.inter = {"t0": t, "T": T, "keys": keys, "tilt": tilt, "frame": F, "edge": (edge, top), "d": d, "grab_t": times[2], "grabbed": False,
                      "fy": fy}
        self._open("climb", t, keys=keys, edge=(edge, top), d=d, T=T, times=times, hang=hang, top_frame=F.tag)
        self.emit(Event(t, "climb_start", self.cid, {"target": a.target}))

    def _climb_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        tau = t - I["t0"]
        u = clamp(tau / I["T"], 0.0, 1.0)
        x, y = keys_at(I["keys"], u)
        self.s, self.h = x, y - I["fy"]
        self.body_tilt = keys_at(I["tilt"], u)
        if not I["grabbed"] and tau >= I["grab_t"]:
            I["grabbed"] = True
            self.emit(Event(t, "ledge_grab", self.cid, {"target": a.target, "point": I["edge"]}))
        if u >= 1.0:
            F = I["frame"]
            self.frame = F
            self.s, self.h, self.body_tilt, self.v = x, self.stand_h, 0.0, 0.0
            self.emit(Event(t, "climbed", self.cid, {"target": a.target, "surface": F.tag}))
            self._next_action(t)

    # ------------------------------------------------------------ wall kick
    def _start_wall_kick(self, t: float, a: ActionSpec) -> None:
        from .controller import Event
        fy = self._feet_y()
        if a.target:
            x0, x1, y0, y1 = self._target_bounds(a.target)
            if y1 - fy < 1.1 * self.stand_h:
                self._fail(f"{self.cid}: '{a.target}' is too low to run up ({y1 - fy:.0f}); vault or climb it")
                self._next_action(t)
                return
            d = 1.0 if self.s < x0 else -1.0
            xw = x0 if d > 0 else x1
        else:
            d = self.facing
            xw = d * self.env.room.width / 2
        start = xw - d * 1.9 * self.stand_h
        if (self.s - start) * d > 0.4 * self.stand_h or abs(self.s - start) > 6.0 and (self.s - start) * d < 0:
            if self._go(t, a, start):
                return
        if self._face(t, a, d):
            return
        sh = self.stand_h
        keys = [(0.0, (self.s, sh)), (WALL_T[0], (xw - d * 0.58 * sh, sh + 8.0)), (WALL_T[1], (xw - d * 0.5 * sh, 1.5 * sh)),
                (WALL_T[2], (xw - d * 0.52 * sh, 1.85 * sh))]
        self.inter = {"t0": t, "keys": keys, "d": d, "xw": xw, "touch": 0, "fy": fy}
        self._open("wall_run", t, keys=keys, d=d, xw=xw, times=WALL_T, contacts=[0.38 * sh, 0.85 * sh])
        self.emit(Event(t, "wall_run", self.cid, {"wall_x": xw}))

    def _wall_kick_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        tau = t - I["t0"]
        s, h = keys_at(I["keys"], tau)
        self.s, self.h = s, h
        self.body_tilt = keys_at([(0.0, 0.18), (WALL_T[0], -0.05), (WALL_T[2], -0.32)], tau)
        while I["touch"] < 2 and tau >= WALL_T[I["touch"]]:
            hh = (0.38, 0.85)[I["touch"]] * self.stand_h
            I["touch"] += 1
            self.emit(Event(t, "wall_contact", self.cid, {"point": (I["xw"], I["fy"] + hh), "step": I["touch"]}))
        if tau >= WALL_T[2]:
            self._launch(t, a, a.target_x, a.height or 70.0, a.flip, kick=True)

    def _launch(self, t: float, a: ActionSpec, target_x: float, apex: float, flip: Optional[str], kick: bool = False) -> None:
        """Ballistic launch from the current pose to land (feet) at `target_x` on the floor below / this frame."""
        from .controller import MASS, Event
        g = math.hypot(*self.gravity.at(t))
        vn = math.sqrt(2 * g * apex)
        drop = self.h - self.stand_h  # the pelvis is this much higher than at a standing landing
        T = (vn + math.sqrt(vn * vn + 2 * g * max(0.0, drop))) / g
        vt = (target_x - self.s) / T
        tan, nrm = self.frame.tangent, self.frame.normal
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.frame.body_angle - self.facing * self.body_tilt)
        self.world.set_dynamic(self.cid, (tan[0] * vt + nrm[0] * vn, tan[1] * vt + nrm[1] * vn), 0.0, MASS, self.moment)
        st = self.world.state(self.cid)
        if flip is None and vt * self.facing < 0:
            self.facing = -self.facing  # turns in the air toward where he is going
        self.body_tilt = 0.0
        self.mode = "airborne"
        sgn = 0.0 if flip is None else (-self.facing if flip == "front" else self.facing)
        self.air = {"intent": "jump", "t0": t, "T": T, "flip": flip, "sgn": sgn, "ang0": st.angle}
        self._open("airborne", t, intent="jump", flip=flip, T=T, target_x=target_x, wall=kick)
        self.cur = None
        if kick:
            self.emit(Event(t, "wall_kick", self.cid, {"point": st.pos, "speed": math.hypot(vt, vn)}))
        self.emit(Event(t, "takeoff", self.cid, {"surface": self.frame.tag, "speed": vt, "apex": apex}))
        if flip:
            self.emit(Event(t, "flip", self.cid, {"dir": flip}))

    def _flip_control(self, t: float) -> None:
        """Rotate the airborne body along a planned somersault that completes at 80% of the flight."""
        A = self.air
        st = self.world.state(self.cid)
        T = A["T"]
        span = max(0.12, 0.8 * T - 0.04)
        u = clamp((t - A["t0"] - 0.04) / span, 0.0, 1.0)
        prof = u * u * u * (u * (6 * u - 15) + 10)
        dprof = 30 * u * u * (u - 1) ** 2 / span if 0 < u < 1 else 0.0
        plan = A["ang0"] + A["sgn"] * 2 * math.pi * prof
        w = 14.0 * (plan - st.angle) + A["sgn"] * 2 * math.pi * dprof
        self.world.set_angular_velocity(self.cid, clamp(w, -32.0, 32.0))
        A["flip_u"] = u

    # ------------------------------------------------------------ pick up, carry, throw
    def _start_pick_up(self, t: float, a: ActionSpec) -> None:
        from .controller import Event
        pid = self._pid(a.target)
        sp = self.props[pid]
        g = math.hypot(*self.gravity.at(t))
        if sp.mass * g > CARRY_MASS_G * self.strength:
            self._fail(f"{self.cid}: '{pid}' ({sp.mass:.0f} kg) is too heavy to pick up (max {CARRY_MASS_G * self.strength / g:.0f})")
            self._next_action(t)
            return
        if self.carrying is not None:
            self._fail(f"{self.cid}: already carrying '{self.carrying}'")
            self._next_action(t)
            return
        ps = self.frame.to_frame(self.world.state(pid).pos)[0]
        side = 1.0 if self.s >= ps else -1.0
        stand = ps + side * 0.42 * self.stand_h
        if self._go(t, a, stand) or self._face(t, a, -side):
            return
        st = self.world.state(pid)
        self.inter = {"t0": t, "pid": pid, "rest": (st.pos, st.angle), "grabbed": False}
        self._open("pick_up", t, prop=pid, T=PICK_T)

    def _pick_up_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        u = clamp((t - I["t0"]) / PICK_T, 0.0, 1.0)
        pid = I["pid"]
        self.h = self.stand_h - 0.42 * self.stand_h * math.sin(math.pi * min(1.0, u / 0.9))
        if u >= 0.45:
            if not I["grabbed"]:
                I["grabbed"] = True
                self.world.set_kinematic(pid, *I["rest"])
                self.carry_log.append([pid, t, math.inf])
                self.emit(Event(t, "pick_up", self.cid, {"prop": pid, "point": I["rest"][0]}))
            k = _smooth((u - 0.45) / 0.55)
            (cx, cy), ca = self._hold_pose(pid)
            (rx, ry), ra = I["rest"]
            self.world.set_kinematic(pid, (rx + (cx - rx) * k, ry + (cy - ry) * k), ra + wrap_angle(ca - ra) * k)
        if u >= 1.0:
            self.h = self.stand_h
            self.carrying = pid
            self._next_action(t)

    def _grip_local(self, pid: str) -> Vec:
        sp = self.props[pid]
        return (-sp.size[0] / 2 + (sp.weight or 8.0), 0.0) if sp.kind == "glyph" else (0.0, 0.0)

    def _hold_pose(self, pid: str, ang: Optional[float] = None, ext: float = 0.0) -> Tuple[Vec, float]:
        """Glyph held in both hands in front at chest height, its long axis pointing forward and a little up
        (or at the swing angle `ang`, relative to forward, with the arms extended by `ext` 0..1)."""
        sp = self.props[pid]
        f = self.facing
        grip = self.frame.to_world(self.s + f * (20.0 + 0.5 * self.arm_reach * ext), self.h + 16.0 + 10.0 * ext)
        a = 0.35 if ang is None else ang
        wa = self.frame.body_angle + (a if f > 0 else math.pi - a)
        gl = self._grip_local(pid)
        ca, sa = math.cos(wa), math.sin(wa)
        c = (grip[0] - (gl[0] * ca - gl[1] * sa), grip[1] - (gl[0] * sa + gl[1] * ca))
        return c, wa

    def _start_throw(self, t: float, a: ActionSpec) -> None:
        from .controller import Event
        if self.carrying is None or self.props[self.carrying].kind == "bar" and getattr(self, "inter_action", None) is not None and \
                self.inter_action.type == "use_lever":
            self._fail(f"{self.cid}: throw needs a carried prop (pick_up first)")
            self._next_action(t)
            return
        pid = self.carrying
        tw = self._throw_aim(a.target)
        d = 1.0 if tw[0] >= self.frame.to_world(self.s, 0)[0] else -1.0
        if self._face(t, a, d):
            return
        self.inter = {"t0": t, "pid": pid, "released": False}
        self._open("throw", t, prop=pid, T=THROW_T, release=THROW_RELEASE, target=a.target)
        self.emit(Event(t, "throw_start", self.cid, {"prop": pid, "target": a.target}))

    def _throw_aim(self, ref: str) -> Vec:
        kind, _, rid = ref.partition(":")
        if kind == "char":
            oc = self.others[rid]
            return oc.frame.to_world(oc.s, oc.h + 0.55 * oc.rig.p.spine + 10.0)
        from ..scene.targets import resolve
        return resolve(self.env, ref)

    def _throw_pose(self, u: float) -> Tuple[Vec, float]:
        """Wind-up behind the shoulder, then over the top and forward."""
        f = self.facing
        back = _smooth(u / THROW_RELEASE)
        s = self.s + f * (20.0 - 44.0 * back)
        h = self.h + 16.0 + 40.0 * back
        a = 0.35 + 1.4 * back
        grip = self.frame.to_world(s, h)
        pid = self.inter["pid"]
        gl = self._grip_local(pid)
        wa = self.frame.body_angle + (a if f > 0 else math.pi - a)
        ca, sa = math.cos(wa), math.sin(wa)
        return (grip[0] - (gl[0] * ca - gl[1] * sa), grip[1] - (gl[0] * sa + gl[1] * ca)), wa

    def _throw_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        tau = t - I["t0"]
        pid = I["pid"]
        if not I["released"]:
            c, ang = self._throw_pose(tau)
            self.world.set_kinematic(pid, c, ang)
            if tau >= THROW_RELEASE:
                I["released"] = True
                self.carrying = None
                if self.carry_log:
                    self.carry_log[-1][2] = t
                tgt = self._throw_aim(a.target)
                st = self.world.state(pid)
                g = math.hypot(*self.gravity.at(t))
                D = tgt[0] - st.pos[0]
                vx = math.copysign(clamp(abs(D) / 0.42, 520.0, 1150.0) * min(1.25, a.power), D)
                T = abs(D) / abs(vx)
                vy = (tgt[1] - st.pos[1] + 0.5 * g * T * T) / T
                self.world.make_dynamic(pid, (vx, vy), -self.facing * 9.0)
                self.thrown = {"prop": pid, "t": t, "target": a.target, "done": set(), "power": a.power}
                self.seg.data["release_t"] = t
                self.emit(Event(t, "throw", self.cid, {"prop": pid, "target": a.target, "point": st.pos, "speed": math.hypot(vx, vy)}))
        if tau >= THROW_T:
            self._next_action(t)

    def _thrown_tick(self, t: float) -> None:
        """A thrown prop in flight: hit, blocked or missed, decided by geometry against each character's body."""
        from .controller import CAPSULE_R, Event
        T = self.thrown
        if T is None:
            return
        pid = T["prop"]
        st = self.world.state(pid)
        speed = math.hypot(*st.vel)
        if t - T["t"] > 3.0 or (t - T["t"] > 0.15 and speed < 90.0):
            self.thrown = None
            return
        sp = self.props[pid]
        from ..scene import glyphs
        wgt = sp.weight or glyphs.default_weight(sp.size)
        segs = [(self._prop_point(pid, p), self._prop_point(pid, q)) for p, q in glyphs.segments(sp.glyph, sp.size)] if sp.kind == "glyph" \
            else [(self._prop_point(pid, (-sp.size[0] / 2, 0)), self._prop_point(pid, (sp.size[0] / 2, 0)))]
        r = wgt / 2 if sp.kind == "glyph" else sp.size[1] / 2
        for cid, oc in self.others.items():
            if cid == self.cid or cid in T["done"] or oc.mode not in ("grounded", "landing") or oc.lying:
                continue
            cs = self.world.state(cid)
            ca, sa = math.cos(cs.angle), math.sin(cs.angle)
            ends = [(cs.pos[0] - sa * y, cs.pos[1] + ca * y) for y in (oc.cap_a[1], oc.cap_b[1])]
            best = min((_seg_dist(p, q, ends[0], ends[1]) for p, q in segs), key=lambda x: x[0])
            if best[0] > r + CAPSULE_R + 2.0:
                continue
            T["done"].add(cid)
            point = best[1]
            direction = 1.0 if st.vel[0] >= 0 else -1.0
            fy = oc.frame.to_frame(point)[1]
            part = "head" if fy > oc.h + oc.shoulder_up - 4 else "body" if fy > 0.45 * oc.stand_h else "legs"
            eff = clamp(sp.mass * speed / 5200.0 * T["power"] * (self.strength / 45000.0), 0.2, 1.9)
            data = {"move": "throw", "target": cid, "part": part, "point": point, "dir": direction, "power": round(eff, 3), "prop": pid}
            guarded = oc.cur is not None and oc.cur.type == "guard" and oc.facing == -direction and part != "legs"
            if guarded:
                self.emit(Event(t, "blocked", self.cid, data))
                oc._receive(t, self.cid, "throw", "block", eff, direction, part, point)
            else:
                reaction = "flinch" if eff < 0.7 else "stagger" if eff < 1.1 else "knockdown"
                data["reaction"] = reaction
                self.emit(Event(t, "hit", self.cid, data))
                oc._receive(t, self.cid, "throw", reaction, eff, direction, part, point, (1.0, 0.2))
            self.emit(Event(t, "prop_hit", pid, {"prop": pid, "target": cid, "point": point, "normal_speed": speed, "blocked": guarded}))
            # the prop glances off the body
            self.world.set_dynamic(pid, (-st.vel[0] * 0.22, abs(st.vel[1]) * 0.2 + 160.0), st.angvel * -0.6, *self.world._mass_moment[pid])
            break
