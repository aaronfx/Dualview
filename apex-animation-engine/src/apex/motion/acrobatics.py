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

ACRO = ("roll", "vault", "climb", "wall_kick", "pick_up", "throw", "place")
VAULT_MAX = 0.95  # x stand height: higher than this, climb
CARRY_MASS_G = 0.9  # a character lifts at most 0.9 x strength (force) overhead
PICK_T, THROW_T, THROW_RELEASE = 0.7, 0.62, 0.3
WALL_T = (0.24, 0.42, 0.52)  # first foot on the wall, second foot, push-off


BODY_MASS_HIT, BODY_MASS_GUARD = 35.0, 70.0  # kg of body that takes a thrown prop: the struck part, or the braced body
RESTITUTION = 0.35  # a hard glyph on a body
IMPULSE_REF = 4200.0  # impulse (kg u/s) that counts as power 1.0 (about a heavy punch)
ROOM_LANE = 60.0  # the depth lanes a character can use (|z|)
KNEE_FRAC = 0.42  # the body's lower end (as in controller.KNEE_UP): lower things are stepped over
BODY_GAP = 30.0  # closest two standing bodies' centres come in the same lane (two torso half-widths + clothing)
BODY_PASS_Z = 28.0  # depth separation at which two bodies pass one in front of the other (two half-depths)
TUCK_INERTIA = 0.4  # a tight tuck has about 0.4 of the open body's moment of inertia about the centre of mass


def flip_tuck(tau: float, T: float) -> float:
    """How tucked a somersaulting body is (0 open .. 1 tight) at time tau of a flight lasting T."""
    def ss(a, b, x):
        u = clamp((x - a) / (b - a), 0.0, 1.0)
        return u * u * (3 - 2 * u)
    return ss(0.04 * T, 0.2 * T, tau) * (1.0 - ss(0.6 * T, 0.8 * T, tau))


def flip_inertia(tuck: float) -> float:
    return 1.0 - (1.0 - TUCK_INERTIA) * tuck


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
        self._now = 0.0
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
            if b.y1 <= fy + 12.0 or b.y0 >= hi or b.owner in self.world.collapsed:
                continue
            face = b.x0 if d > 0 else b.x1
            if (face - s0) * d > -4.0 and (s1 - face) * d > -10.0:
                if best is None or (face - s0) * d < (best[0] - s0) * d:
                    best = (face, b)
        return best

    def _props_in_path(self, lo_s: float, hi_s: float, skip=(), *, lookahead: float = 0.0) -> List[Tuple[str, float, float]]:
        """Props (id, depth z, half depth) standing across the body's height band between lo_s and hi_s."""
        fy = self._feet_y()
        out = []
        # A held object may extend beyond the actor in both travel directions.
        if self.carrying:
            lo_s -= self._carried_front(-1.0)
            hi_s += self._carried_front(1.0)
        for pid, sp in self.props.items():
            if pid in skip or not sp.collide_characters or pid in self.world.inactive:
                continue
            st = self.world.state(pid)
            r = max(sp.size) / 2
            # Short, conservative swept horizontal envelope from native velocity.
            # This is not a prediction of impacts or arbitrary ballistic motion.
            future_x = st.pos[0] + st.vel[0] * lookahead
            if max(st.pos[0], future_x) + r < lo_s - 11.0 or min(st.pos[0], future_x) - r > hi_s + 11.0:
                continue
            if st.pos[1] + r < fy + KNEE_FRAC * self.stand_h or st.pos[1] - r > fy + 1.9 * self.stand_h:
                continue
            pz, ph = self.world.depth.get(pid, (0.0, 30.0))
            out.append((pid, pz, ph))
        return out

    def _carry_route_blocker(self, dx: float) -> Optional[str]:
        """Conservative swept held-object bounds for grounded locomotion.

        Prop-to-prop impulses remain disabled for carried bodies. This guard
        prevents advancing a held load into a solid prop in the same depth lane;
        it does not claim to predict arbitrary impacts or moving-body intrusion.
        """
        pid = self.carrying
        if pid is None or not self._upright() or abs(dx) < 1e-9:
            return None
        l, r, b, top = self._target_bounds(f"prop:{pid}")
        l, r = min(l, l + dx), max(r, r + dx)
        half = self.props[pid].depth / 2
        # Native lever staging owns the entire tool approach and seating
        # trajectory, including deliberate overlap in its 2.5D geometry.
        # Cargo transit protection must not intercept that authored mechanic.
        if (self.inter_action is not None and self.inter_action.type == "use_lever"
                and self.inter.get("phase") == "carry" and self.inter.get("bar") == pid):
            return None
        for other, sp in self.props.items():
            if other == pid or other in self.world.inactive or not sp.solid:
                continue
            z, ph = self.world.depth.get(other, (0.0, 30.0))
            if abs(self.z - z) >= half + ph:
                continue
            ol, ore, ob, ot = self._target_bounds(f"prop:{other}")
            if l < ore and r > ol and b < ot and top > ob:
                return other
        return None

    def _route_half_depth(self) -> float:
        """Depth clearance of the actor plus the carried prop, if any."""
        return max(14.0, self.props[self.carrying].depth / 2) if self.carrying else 14.0

    def _free_lane(self, blockers: List[Tuple[str, float, float]]) -> Optional[float]:
        """The nearest depth lane (to the current one) clear of all the blockers, within the room."""
        margin = self._route_half_depth() + 3.0
        bands = [(pz - ph - margin, pz + ph + margin) for _, pz, ph in blockers]
        cands = [self.z] + [e for b in bands for e in b]
        ok = [z for z in cands if -ROOM_LANE <= z <= ROOM_LANE and all(not (lo < z < hi) for lo, hi in bands)]
        return min(ok, key=lambda z: abs(z - self.z)) if ok else None

    def _hold_for_lane(self, s_prev: float) -> None:
        sd = getattr(self, "_sidestep", None)
        if sd is None or self.z_target is None or abs(self.z - self.z_target) < 1.0:
            return
        # Every prop considered by the lane planner must be clear before
        # forward motion resumes; the farthest prop alone is insufficient.
        if all(abs(self.z - pz) >= ph + self._route_half_depth()
               for pid in sd.get("props", (sd["prop"],))
               if pid not in self.world.inactive
               for pz, ph in (self.world.depth.get(pid, (0.0, 30.0)),)):
            return
        # step aside first, then walk on (no forward motion until clear of it in depth)
        if abs(self.s - s_prev) > 1e-9:
            self.s, self.v = s_prev, 0.0
            self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.world.state(self.cid).angle)

    def _refresh_prop_route(self, t: float) -> None:
        """Bounded live decision boundary for grounded walks; never overrides explicit lanes."""
        a = self.cur
        if (self.mode != "grounded" or self.lying or a is None
                or a.type not in ("walk_to", "run_to") or a.target_x is None
                or a.lane is not None or not self._upright()):
            return
        if t < getattr(self, "_prop_route_next", 0.0):
            return
        self._prop_route_next = t + 0.1
        self._plan_around_props(t, a, refresh=True)

    def _plan_around_props(self, t: float, a: ActionSpec, *, refresh: bool = False) -> None:
        """Choose a depth lane from live native prop positions; refresh for newly arriving moving blockers."""
        sd = getattr(self, "_sidestep", None)
        if a.lane is not None or (sd is not None and not refresh) or not self._upright():
            return
        lo_s, hi_s = sorted((self.s, a.target_x))
        handled = {self.carrying} | ({self.thrown["prop"]} if self.thrown else set())
        for q in self.queue:  # props the character is going to handle next are approached, not avoided
            for ref in (q.target, q.tool, q.fulcrum):
                if ref and ref.startswith("prop:"):
                    handled.add(ref.split(":", 1)[1])
        x0 = self.frame.to_world(self.s, self.h)[0]
        blockers = [b for b in self._props_in_path(lo_s, hi_s, handled, lookahead=0.35 if refresh else 0.0)
                    if abs(self.world.state(b[0]).pos[0] - x0) > max(self.props[b[0]].size) / 2 + 11.0]
        if refresh:
            known = set(sd.get("props", (sd["prop"],))) if sd else set()
            # Preserve authored static approaches, and the original sidestep's home lane.
            # A previously untracked moving prop is evidence that the route has changed.
            if not any(pid not in known and math.hypot(*self.world.state(pid).vel) > 20.0
                       and abs(pz - (self.z_target if self.z_target is not None else self.z)) < ph + self._route_half_depth() + 3.0
                       for pid, pz, ph in blockers):
                return
            if sd:
                # Retain passed-but-still-adjacent props until the original clearance check releases them.
                present = {pid for pid, _, _ in blockers}
                blockers.extend((pid, *self.world.depth.get(pid, (0.0, 30.0)))
                                for pid in known if pid not in present and pid not in self.world.inactive)
        elif not any(abs(pz - self.z) < ph + self._route_half_depth() for _, pz, ph in blockers):
            return
        z = self._free_lane(blockers)
        if z is not None and (abs(z - self.z) > 1e-6 or refresh and self.z_target is not None):
            from .controller import Event
            far = max(blockers, key=lambda b: abs(self.world.state(b[0]).pos[0] - x0))
            self._sidestep = {"prop": far[0], "props": tuple(b[0] for b in blockers),
                              "home": sd["home"] if sd else self.z, "planned": True}
            self.z_target = z
            self.emit(Event(t, "sidestep", self.cid, {"prop": far[0], "props": list(self._sidestep["props"]),
                                                       "lane": round(z, 1), "planned": True, "refreshed": refresh}))

    def _check_walk(self, t: float, a: ActionSpec) -> ActionSpec:
        hit = self._path_blocker(self.s, a.target_x)
        if hit is None:
            return a
        face, b = hit
        sp = self._portal_on_path(self.s, a.target_x) if getattr(self, "portal_maps", None) else None
        if sp is not None and (face - sp) * (1.0 if a.target_x > self.s else -1.0) > 12.0:
            return a  # the walk goes through a portal before it would reach the structure
        if getattr(self, "portal_maps", None) is not None and self._pad_on_path(self.s, face):
            return a  # a launch pad on the way: the walk is checked again from where the body lands
        d = 1.0 if a.target_x > self.s else -1.0
        msg = (f"{self.cid}: walking from x {self.s:.0f} to {a.target_x:.0f} runs into structure '{b.owner}' (face at x {face:.0f}); "
               f"vault over it, climb onto it or jump_to onto it")
        if self.strict:
            raise ValueError(msg)
        self.violation = self.violation or msg
        return a.model_copy(update={"target_x": face - d * 14.0})

    def _enforce_solid(self, t: float, s_prev: float) -> None:
        """Simulation-time guard: whatever moved the body this step (a walk, a strike's lunge, a dodge, a knockback, a
        landing slide, a roll), it stops at a structure's face instead of passing through it."""
        if self.cur is not None and self.cur.type in ("vault", "climb", "wall_kick"):
            return  # keyed moves that go over / up a structure by design
        if abs(self.s - s_prev) < 1e-9 or not self._upright():
            return
        top = 30.0 if self.lying else max(0.4 * self.stand_h, self.h + 0.72 * self.stand_h)
        d0 = 1.0 if self.s > s_prev else -1.0
        front = max(10.0, self._carried_front(d0) + 2.0) if self.carrying else 10.0
        hit = self._path_blocker(s_prev + d0 * (front - 10.0), self.s + d0 * (front - 10.0), top=top)
        if hit is None:
            return
        face, b = hit
        d = 1.0 if self.s > s_prev else -1.0
        stop = face - d * front  # the body's half thickness, or the carried prop's reach ahead of it
        if (self.s - stop) * d <= 0:
            return
        self.s, self.v = stop, 0.0
        last = getattr(self, "_bump_t", -1.0)
        if t - last > 0.4:
            from .controller import Event
            self.emit(Event(t, "bump", self.cid, {"structure": b.owner, "point": self.frame.to_world(face, self.h)}))
        self._bump_t = t
        if self.mode == "landing":
            self.land["s0"], self.land["vt"] = stop, 0.0
        tan = self.frame.tangent
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.world.state(self.cid).angle)

    def _enforce_props(self, t: float, s_prev: float) -> None:
        """Moves that place the body directly (strike lunges and rebounds, dodges, rolls, reactions, landing slides) stop
        at the face of a prop in the body's depth lane, as they do at structures. Walks are left to the bounded-force body
        (they can push what is light enough)."""
        if self.cur is not None and self.cur.type in ("walk_to", "run_to", "vault", "climb", "wall_kick"):
            return
        if abs(self.s - s_prev) < 1e-9 or not self._upright() or self.lying:
            return
        d = 1.0 if self.s > s_prev else -1.0
        fy = self._feet_y()
        handled = {p for (o, p) in self.world.proxy_ignore if o == self.cid} | self.world.carried | self.world.in_flight
        best = None
        for pid, sp in self.props.items():
            if pid in handled or not sp.collide_characters or pid in self.world.inactive:
                continue
            pz, ph = self.world.depth.get(pid, (0.0, 30.0))
            if abs(pz - self.z) >= ph + 14.0:
                continue
            x0, x1, y0, y1 = self._target_bounds(f"prop:{pid}")
            if y1 <= fy + KNEE_FRAC * self.stand_h or y0 >= fy + 1.9 * self.stand_h:
                continue
            face = x0 if d > 0 else x1
            if (face - s_prev) * d > -4.0 and (self.s - (face - d * 11.0)) * d > 0:
                if best is None or (face - s_prev) * d < (best - s_prev) * d:
                    best = face
        if best is not None:
            self.s, self.v = best - d * 11.0, 0.0
            self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.world.state(self.cid).angle)

    def _enforce_bodies(self, t: float, s_prev: float) -> None:
        """Two standing bodies in the same depth lane cannot pass through each other: whatever moved this body
        (a walk, a lunge, a roll, a knockback), it stops at the other's body. Lanes at least BODY_PASS_Z apart pass by
        in depth (one in front of the other)."""
        if abs(self.s - s_prev) < 1e-9 or not self._upright() or self._gone():
            return
        d = 1.0 if self.s > s_prev else -1.0
        for cid, oc in self.others.items():
            if cid == self.cid or oc.frame is not self.frame or oc.lying or oc.mode not in ("grounded", "landing") or oc._gone():
                continue
            if abs(oc.z - self.z) >= BODY_PASS_Z:
                continue
            # a rolling body is a ball about the pelvis: as it comes up the head sweeps ~0.7 stand_h ahead of the pelvis,
            # and the other's guard knee reaches ~0.3 stand_h towards it, so a roll keeps a body-length further off
            rolling = self.cur is not None and self.cur.type == "roll"
            gap = BODY_GAP + (1.0 * self.stand_h if rolling else 0.0)
            gap0, gap1 = (oc.s - s_prev) * d, (oc.s - self.s) * d
            if 0.0 < gap0 and gap1 < gap and gap1 < gap0:  # the other is ahead and this would move into (or further into) it
                # stop at its edge; a body already inside the gap (a roll starting close) does not advance at all
                s_free = self.s
                self.s, self.v = (oc.s - d * gap if gap0 >= gap - 1e-6 else s_prev), 0.0
                if rolling:  # the roll's plan is shortened by what the body could not travel (no pop at its end)
                    self.inter["s0"] += self.s - s_free
                if t - getattr(self, "_bodybump_t", -1.0) > 0.4:
                    from .controller import Event
                    self.emit(Event(t, "body_block", self.cid, {"other": cid}))
                self._bodybump_t = t
                if self.mode == "landing":
                    self.land["s0"], self.land["vt"] = self.s, 0.0
                self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.world.state(self.cid).angle)

    # ------------------------------------------------------------ carried props never enter structures
    def _prop_segs_at(self, pid: str, c: Vec, ang: float):
        """World segments (and radius) of a prop at centre c and angle ang."""
        from ..scene import glyphs
        sp = self.props[pid]
        ca, sa = math.cos(ang), math.sin(ang)
        W = lambda p: (c[0] + p[0] * ca - p[1] * sa, c[1] + p[0] * sa + p[1] * ca)
        if sp.kind == "glyph":
            g = getattr(self.world, "glyph_now", {}).get(pid, sp.glyph)  # its shape now (a morph may have changed it)
            return [(W(a), W(b)) for a, b in glyphs.segments(g, sp.size)], (sp.weight or glyphs.default_weight(sp.size)) / 2
        hx = sp.size[0] / 2
        return [(W((-hx, 0.0)), W((hx, 0.0)))], sp.size[1] / 2

    def _solids(self):
        """The exact solid geometry of the structures: glyph strokes as capsules, platforms and beams as boxes."""
        if getattr(self, "_solid_cache", None) is None:
            out = []
            for ob in self.env.obstacles:
                if ob.kind == "glyph":
                    out += [("seg", a, b, r, ob.id) for a, b, r, _ in structures.shape_tags(ob)]
                elif ob.kind in ("platform", "beam"):
                    cx, cy = ob.center
                    out.append(("box", (cx - ob.size[0] / 2, cy - ob.size[1] / 2), (cx + ob.size[0] / 2, cy + ob.size[1] / 2), 0.0, ob.id))
            self._solid_cache = out
        if self.world.collapsed:  # a structure that gave way is no longer solid
            return [s for s in self._solid_cache if s[4] not in self.world.collapsed]
        return self._solid_cache

    def _prop_in_structure(self, pid: str, c: Vec, ang: float, allow: float = 1.5) -> Optional[str]:
        """The structure a prop at this pose would sink into by more than `allow` (resting contact is fine)."""
        segs, r = self._prop_segs_at(pid, c, ang)
        for (a, b) in segs:
            for kind, p, q, rs, owner in self._solids():
                if kind == "seg":
                    if _seg_dist(a, b, p, q)[0] < r + rs - allow:
                        return owner
                else:
                    for k in range(9):
                        u = k / 8
                        x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u
                        if p[0] - r + allow < x < q[0] + r - allow and p[1] - r + allow < y < q[1] + r - allow:
                            return owner
        return None

    def _pose_prop(self, pid: str, c: Vec, ang: float, t: float) -> bool:
        """Move a held prop to a new pose unless that pose is inside a structure (then it stays, and the hands with it)."""
        hit = self._prop_in_structure(pid, c, ang)
        if hit is not None:
            if t - getattr(self, "_propbump_t", -1.0) > 0.4:
                from .controller import Event
                self.emit(Event(t, "prop_blocked", self.cid, {"prop": pid, "structure": hit, "point": c}))
            self._propbump_t = t
            return False
        self.world.set_kinematic(pid, c, ang)
        return True

    def _carried_front(self, d: float) -> float:
        """How far the carried prop reaches ahead of the body in direction d (beyond the body's own half thickness)."""
        pid = self.carrying
        if pid is None:
            return 0.0
        st = self.world.state(pid)
        segs, r = self._prop_segs_at(pid, st.pos, st.angle)
        x0 = self.frame.to_world(self.s, self.h)[0]
        return max(0.0, max(max((a[0] - x0) * d, (b[0] - x0) * d) for a, b in segs) + r)

    # ------------------------------------------------------------ bounded-force body vs dynamic props
    def _gone(self) -> bool:
        """Through an exit door: out of the level (no longer a body anyone or anything can touch)."""
        return bool(self.exit) and bool(self.exit.get("crossed"))

    def _proxy_active(self) -> bool:
        return self.mode in ("grounded", "landing") and self.posture == "stand" and self.ragdoll is None and not self._gone()

    def _proxy_sync(self, t: float) -> None:
        """Before the physics step: the body is solid while standing, pushes with at most the character's strength,
        and ignores the props this character is handling (carried, pushed, levered, just thrown)."""
        sd = getattr(self, "_sidestep", None)
        if sd is not None:  # stepped around a prop in depth: back to the own lane once past it and clear of it
            x = self.frame.to_world(self.s, self.h)[0]
            moving = self.cur is not None and self.cur.type in ("walk_to", "run_to") and self.cur.target_x is not None
            clear = True
            for pid in sd.get("props", (sd["prop"],)):
                if pid in self.world.inactive:
                    continue
                st = self.world.state(pid)
                sp = self.props[pid]
                ahead = moving and (st.pos[0] - x) * (self.cur.target_x - self.s) > 0
                if abs(x - st.pos[0]) <= max(sp.size) / 2 + 17.0 or ahead:
                    clear = False
                    break
            if clear:
                self.z_target = sd["home"]
                self._sidestep = None
        active = self._proxy_active()
        from .controller import KNEE_UP
        # the body's lower end: knee height above the floor; it rises as the body crouches, never reaches below a
        # standing body's knees (a climb or a jump raises the pelvis far above the floor)
        low = clamp(-self.h + KNEE_UP * self.stand_h, (KNEE_UP - 1.0) * self.stand_h, self.cap_b[1] - 20.0)
        self.world.proxy_set(self.cid, active, self.strength, low=low)
        fl = getattr(self, "_flight_reg", None)
        cur = self.thrown["prop"] if self.thrown else None
        if fl is not None and fl != cur:
            self.world.in_flight.discard(fl)
        if cur:
            self.world.in_flight.add(cur)
        self._flight_reg = cur
        mine = getattr(self, "_carried_reg", None)
        if mine is not None and mine != self.carrying:
            self.world.carried.discard(mine)
        if self.carrying:
            self.world.carried.add(self.carrying)
        self._carried_reg = self.carrying
        self.world.depth[self.cid] = (self.z, 14.0)
        ign = self.world.proxy_ignore
        for pair in [p for p in ign if p[0] == self.cid]:
            ign.discard(pair)
        handled = set()
        if self.carrying:
            handled.add(self.carrying)
        if self.thrown:
            handled.add(self.thrown["prop"])
        acts = [x for x in (self.cur, self.inter_action) if x is not None and self.cur is not None and self.cur.type in (
            "push", "lift", "use_lever", "pick_up", "throw")]
        for ref in [getattr(x, k, None) for x in acts for k in ("target", "tool", "fulcrum")]:
            if ref and ref.startswith("prop:"):
                handled.add(ref.split(":", 1)[1])
        if self.inter.get("bar"):
            handled.update(k for k in (self.inter.get("bar"), self.inter.get("ful")) if k)
        nxt = self.queue[0] if self.queue else None  # rolling or running in to pick something up: it is already in hand's reach
        if nxt is not None and nxt.type == "pick_up" and (nxt.target or "").startswith("prop:") and self.cur is not None and \
                self.cur.type in ("roll", "walk_to", "run_to"):
            handled.add(nxt.target.split(":", 1)[1])
        for pid in handled:
            ign.add((self.cid, pid))
        grace = frozenset(p for (o, p) in self.world.proxy_grace if o == self.cid)
        h = frozenset(handled) | grace
        log = self.__dict__.setdefault("handled_log", [])
        if not log or log[-1][1] != h:
            log.append((t, h))

    def _proxy_react(self, t: float) -> None:
        """After the physics step: if a prop held the body back while the character moved into it, the character is
        stopped there (blocked); if a prop pushed the body, the character is displaced with it, and a hard shove
        staggers him."""
        if not self._proxy_active():
            return
        prop = self.world.proxy_contact(self.cid)
        if prop is None:
            return
        (ox, oy), (vx, vy) = self.world.proxy_offset(self.cid)
        tan = self.frame.tangent
        off = ox * tan[0] + oy * tan[1]
        if abs(off) < 2.0:
            return
        from .controller import Event
        moved = self.s - (self._step_from if self._step_from is not None else self.s)
        last = getattr(self, "_proxy_ev_t", -1.0)
        if moved * off < 0:  # walking (or lunging) into it, and it did not give way: the character stops
            self.s += off
            self.v = 0.0
            if t - last > 0.5:
                self.emit(Event(t, "prop_block", self.cid, {"prop": prop, "point": self.frame.to_world(self.s, self.h)}))
                self._proxy_ev_t = t
            if self.cur is not None and self.cur.type in ("walk_to", "run_to") and getattr(self, "_sidestep", None) is None:
                # a walk blocked by something it cannot move: step around it in depth, if the room allows
                tgt = self.cur.target_x
                lo_s, hi_s = sorted((self.s, tgt))
                blockers = self._props_in_path(lo_s, hi_s)
                if not any(b[0] == prop for b in blockers):
                    blockers.append((prop, *self.world.depth.get(prop, (0.0, 30.0))))
                z = self._free_lane(blockers)
                if z is not None and abs(z - self.z) > 1e-6:
                    self._sidestep = {"prop": prop, "props": tuple(b[0] for b in blockers), "home": self.z}
                    self.z_target = z
                    self.emit(Event(t, "sidestep", self.cid, {"prop": prop, "props": list(self._sidestep["props"]),
                                                               "lane": round(z, 1)}))
        else:  # the prop pushed the body: the character is displaced with it
            self.s += off
            speed = abs(vx * tan[0] + vy * tan[1])
            if t - last > 0.5:
                self.emit(Event(t, "shoved", self.cid, {"prop": prop, "speed": round(speed, 1),
                                                        "point": self.frame.to_world(self.s, self.h)}))
                self._proxy_ev_t = t
                if speed > 160.0 and (self.cur is None or self.cur.type != "hurt"):
                    self._hurt(t, "stagger", 1.0 if off > 0 else -1.0, min(90.0, 20.0 + 0.12 * speed), part="body")
        if self.mode == "landing":
            self.land["s0"] = self.s
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.world.state(self.cid).angle)

    def _edge_check(self, t: float) -> bool:
        F = self.frame
        if not F.bounded or self.mode != "grounded" or self.posture != "stand" or \
                (self.cur is not None and self.cur.type in ("climb", "vault", "wall_kick")):
            return False
        if self.exit is not None and self.exit.get("crossed"):  # through a door: out of the level, not off a ledge
            return False
        if F.lo - 3.0 <= self.s <= F.hi + 3.0:
            return False
        nxt = self._continuing_top(F)
        if nxt is not None:  # the next top carries on at the same height (a bridge onto a ledge): walk straight across
            self.frame = nxt
            return False
        self._step_off(t)
        return True

    def _continuing_top(self, F):
        """A top that continues this one at the same height where the body has just walked off its end, if any."""
        p = F.to_world(self.s, 0.0)
        for G in self.frames.values():
            if G is F or G.owner is None or G.owner in self.world.collapsed or abs(G.normal[1] - 1.0) > 1e-6:
                continue
            if abs(G.origin[1] - F.origin[1]) <= 3.0 and G.lo - 4.0 <= p[0] <= G.hi + 4.0:
                return G
        return None

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
            self._carried = self.cur
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
            ex = glyphs.extent(getattr(self.world, "glyph_now", {}).get(rid, sp.glyph), sp.size, sp.weight or glyphs.default_weight(sp.size))
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
        if a.type not in ("throw", "pick_up", "place") and not self._upright():
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
        plant = (near + d * min(14.0, abs(far - near) / 3.0), y1 + 7.0)  # the palm on the top, not in it
        self.inter = {"t0": t, "s0": self.s, "s1": land, "top": y1 - fy, "T": T, "d": d, "plant": plant, "said": False}
        self._open("vault", t, s0=self.s, s1=land, plant=plant, top=y1, T=T, d=d, target=a.target, span=(min(x0, x1), max(x0, x1)))
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
        # Tempo is constrained for *this* physically staged action. Time-
        # scale the full reach/grab/pull/mantle path together, including IK
        # contact intervals and causal ledge_grab event. No key is removed,
        # so accelerating the actor does not jump or teleport over the ledge.
        tempo = clamp(a.tempo, 0.7, 1.35)
        times = [phase_t / tempo for phase_t in times]
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
        """A somersault by conservation of angular momentum. At takeoff the legs give the body an angular momentum L
        chosen so that, with the tuck the body will make (shared with the animation, `flip_tuck`), the rotation adds up
        to one full turn by the planned touchdown. In the air L is conserved: the spin rate is L / I(tuck), so it
        speeds up in the tuck and slows as the body opens out to land. Nothing steers the angle. A contact that
        changes the spin (a graze) changes L, and a landing earlier or later than planned lands under- or
        over-rotated."""
        A = self.air
        st = self.world.state(self.cid)
        T = A["T"]
        tau = t - A["t0"]
        if "L" not in A:
            n = 240
            integ = sum(1.0 / flip_inertia(flip_tuck((k + 0.5) * T / n, T)) for k in range(n)) * T / n
            A["L"] = A["sgn"] * 2 * math.pi / integ  # in units of the open body's moment of inertia
            A["w_set"] = st.angvel
        elif abs(st.angvel - A["w_set"]) > 0.5:  # something (a contact) changed the spin: the momentum changes with it
            A["L"] = st.angvel * flip_inertia(flip_tuck(max(0.0, tau - 1.0 / 240), T))
        w = A["L"] / flip_inertia(flip_tuck(tau, T))
        self.world.set_angular_velocity(self.cid, w)
        A["w_set"] = w
        A["flip_u"] = clamp(tau / T, 0.0, 1.0)

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
        ps, ph = self.frame.to_frame(self.world.state(pid).pos)
        side = 1.0 if self.s >= ps else -1.0
        high = ph > 0.45 * self.stand_h  # (height above the surface stood on) on a holder: stand back from what it sits on, reach out
        stand = ps + side * (0.74 if high else 0.42) * self.stand_h
        if self._go(t, a, stand) or self._face(t, a, -side):
            return
        st = self.world.state(pid)
        self.inter = {"t0": t, "pid": pid, "rest": (st.pos, st.angle), "grabbed": False}
        dip = 0.42 * clamp(1.0 - self.frame.to_frame(st.pos)[1] / (0.8 * self.stand_h), 0.08, 1.0)
        self._open("pick_up", t, prop=pid, T=PICK_T, dip=dip)

    def _pick_up_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        u = clamp((t - I["t0"]) / PICK_T, 0.0, 1.0)
        pid = I["pid"]
        # crouch only as low as the prop is: something on a holder at waist height is taken almost standing
        rest_h = self.frame.to_frame(I["rest"][0])[1]  # height above the surface stood on
        dip = 0.42 * clamp(1.0 - rest_h / (0.8 * self.stand_h), 0.08, 1.0)
        self.h = self.stand_h - dip * self.stand_h * math.sin(math.pi * min(1.0, u / 0.9))
        if u >= 0.45:
            if not I["grabbed"]:
                I["grabbed"] = True
                self.world.set_kinematic(pid, *I["rest"])
                self.carry_log.append([pid, t, math.inf])
                self.emit(Event(t, "pick_up", self.cid, {"prop": pid, "point": I["rest"][0]}))
            k = _smooth((u - 0.45) / 0.55)
            (cx, cy), ca = self._hold_pose(pid)
            (rx, ry), ra = I["rest"]
            self._pose_prop(pid, (rx + (cx - rx) * k, ry + (cy - ry) * k), ra + wrap_angle(ca - ra) * k, t)
        if u >= 1.0:
            self.h = self.stand_h
            self.carrying = pid
            self._next_action(t)

    # ------------------------------------------------------------ set a carried prop down (place), let go of it (drop, disarm)
    def _place_rest(self, ref: str) -> Vec:
        """Where a placed prop comes to rest: centred on a structure's top ("obstacle:<id>"), or at a point."""
        pid = self.carrying
        half = 0.5 * self.props[pid].size[1]
        kind, _, rid = ref.partition(":")
        if kind == "point":
            x, y = (float(v) for v in rid.split(","))
            return (x, y + half)
        ob = next(o for o in self.env.obstacles if o.id == rid)
        return (ob.center[0], ob.center[1] + 0.5 * ob.size[1] + half + 12.0)  # seated just clear of its top (a hand can take it without touching the holder)

    def _start_place(self, t: float, a: ActionSpec) -> None:
        if self.carrying is None:
            self._fail(f"{self.cid}: place needs a carried prop")
            self._next_action(t)
            return
        rest = self._place_rest(a.target)
        ps = self.frame.to_frame(rest)[0]
        side = 1.0 if self.s >= ps else -1.0
        off = 0.46 * self.stand_h
        kind, _, rid = a.target.partition(":")
        if kind == "obstacle":  # stop short of the holder: the carried prop reaches ahead of the body
            ob = next(o for o in self.env.obstacles if o.id == rid)
            off = max(off, 0.5 * ob.size[0] + max(10.0, self._carried_front(-side) + 2.0) + 6.0)
        stand = ps + side * off
        if self._go(t, a, stand) or self._face(t, a, -side):
            return
        pid = self.carrying
        st = self.world.state(pid)
        self.inter = {"t0": t, "pid": pid, "from": (st.pos, st.angle), "rest": rest, "placed": False}
        dip = 0.3 * clamp(1.0 - self.frame.to_frame(rest)[1] / (0.8 * self.stand_h), 0.08, 1.0)
        self._open("pick_up", t, prop=pid, T=PICK_T, place=True, dip=dip)

    def _place_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        u = clamp((t - I["t0"]) / PICK_T, 0.0, 1.0)
        pid = I["pid"]
        rest_h = self.frame.to_frame(I["rest"])[1]
        dip = 0.3 * clamp(1.0 - rest_h / (0.8 * self.stand_h), 0.08, 1.0)
        self.h = self.stand_h - dip * self.stand_h * math.sin(math.pi * min(1.0, u / 0.9))
        if not I["placed"]:
            k = _smooth(min(1.0, u / 0.55))
            (fx, fy), fa = I["from"]
            rx, ry = I["rest"]
            ra = 0.0
            self.world.set_kinematic(pid, (fx + (rx - fx) * k, fy + (ry - fy) * k), fa + wrap_angle(ra - fa) * k)
            if u >= 0.55:
                I["placed"] = True
                self._release_carry(t, why="place", data={"on": a.target, "point": I["rest"]})
                if a.target.startswith("obstacle:") or a.seat:
                    self.world.set_kinematic(pid, I["rest"], 0.0)
                    if a.seat:
                        for shape in self.world.shapes_of(pid):
                            shape.sensor = True
        if u >= 1.0:
            self.h = self.stand_h
            self._next_action(t)

    def _release_carry(self, t: float, vel: Vec = (0.0, 0.0), angvel: float = 0.0, why: str = "drop",
                       data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Let go of the carried prop: it becomes an ordinary dynamic body again (set down, dropped, or knocked loose)."""
        from .controller import Event
        pid = self.carrying
        if pid is None:
            return None
        self.carrying = None
        if self.carry_log and self.carry_log[-1][0] == pid and self.carry_log[-1][2] == math.inf:
            self.carry_log[-1][2] = t
        self.world.make_dynamic(pid, vel, angvel)
        d = {"prop": pid, "point": self.world.state(pid).pos}
        d.update(data or {})
        self.emit(Event(t, why, self.cid, d))
        return pid

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
        if sp.kind == "glyph" and sp.glyph[:1] in ("+", "-") and sp.glyph[1:].isdigit() and ang is None:
            wa = self.frame.body_angle  # keep the signed term legible while walking
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
        if kind == "prop":  # a prop (e.g. a creature's body): where it is at the release
            return tuple(self.world.state(rid).pos)
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
            self._pose_prop(pid, c, ang, t)
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
        segs = [(self._prop_point(pid, p), self._prop_point(pid, q))
                for p, q in glyphs.segments(getattr(self.world, "glyph_now", {}).get(pid, sp.glyph), sp.size)] if sp.kind == "glyph" \
            else [(self._prop_point(pid, (-sp.size[0] / 2, 0)), self._prop_point(pid, (sp.size[0] / 2, 0)))]
        r = wgt / 2 if sp.kind == "glyph" else sp.size[1] / 2
        # a symbol thrown into what another character holds knocks it out of their hands (a disarm)
        for cid, oc in self.others.items():
            hp = getattr(oc, "carrying", None)
            if cid == self.cid or cid in T["done"] or hp is None or self.props[hp].kind != "glyph":
                continue
            hsp = self.props[hp]
            hsegs = [(self._prop_point(hp, p), self._prop_point(hp, q))
                     for p, q in glyphs.segments(getattr(self.world, "glyph_now", {}).get(hp, hsp.glyph), hsp.size)]
            hr = (hsp.weight or glyphs.default_weight(hsp.size)) / 2
            best = min((_seg_dist(p, q, a_, b_) for p, q in segs for a_, b_ in hsegs), key=lambda x: x[0])
            if best[0] > r + hr + 3.0:
                continue
            T["done"].add(cid)
            point = best[1]
            hs = self.world.state(hp)
            m_p, m_h, e = sp.mass, hsp.mass + 6.0, RESTITUTION  # the held symbol, with the hands' grip behind it
            vrel = (st.vel[0] - hs.vel[0], st.vel[1] - hs.vel[1])
            n = (vrel[0] / max(1e-6, speed), vrel[1] / max(1e-6, speed))
            vn = -math.hypot(*vrel)
            J = -(1.0 + e) * vn * m_p * m_h / (m_p + m_h)
            self.world.make_dynamic(pid, (0.0, 60.0), 6.0 if st.vel[0] < 0 else -6.0)  # its energy spent on the weapon: it drops
            # knocked up and out of the hands, out in front of the body that held it (not back into it)
            fly = (oc.facing * (160.0 + 0.25 * abs(n[0]) * J / m_h), 480.0 + abs(n[1]) * J / m_h * 0.3)
            direction = 1.0 if st.vel[0] >= 0 else -1.0
            eff = clamp(J / IMPULSE_REF, 0.15, 1.9)
            oc._release_carry(t, fly, -oc.facing * 11.0, why="disarm", data={"by": self.cid, "with": pid, "impulse": round(J, 1)})
            self.emit(Event(t, "prop_hit", pid, {"prop": pid, "target": hp, "point": point, "normal_speed": -vn, "blocked": False,
                                                 "impulse": round(J, 1)}))
            if oc.mode in ("grounded", "landing") and not oc.lying:
                oc._receive(t, self.cid, "throw", "flinch", min(eff, 0.6), direction, "body", point)
            return
        for cid, oc in self.others.items():
            if cid == self.cid or cid in T["done"] or oc.mode not in ("grounded", "landing") or oc.lying:
                continue
            if abs(oc.z - self.z) >= BODY_PASS_Z:  # it flies along the thrower's lane: a body in another lane is passed by
                continue
            cs = self.world.state(cid)
            ca, sa = math.cos(cs.angle), math.sin(cs.angle)
            ends = [(cs.pos[0] - sa * y, cs.pos[1] + ca * y) for y in (oc.cap_a[1], oc.cap_b[1])]
            best = min((_seg_dist(p, q, ends[0], ends[1]) for p, q in segs), key=lambda x: x[0])
            if best[0] > r + CAPSULE_R + 2.0:
                continue
            T["done"].add(cid)
            point = best[1]
            # contact normal: from the nearest point of the body axis toward the prop's contact point
            axis_pt = _seg_dist(point, point, ends[0], ends[1])[1]
            nx, ny = point[0] - axis_pt[0], point[1] - axis_pt[1]
            nn = math.hypot(nx, ny)
            if nn < 1e-6:
                nx, ny, nn = -st.vel[0], -st.vel[1], max(1e-6, speed)
            n = (nx / nn, ny / nn)
            vrel = (st.vel[0] - cs.vel[0], st.vel[1] - cs.vel[1])
            vn = vrel[0] * n[0] + vrel[1] * n[1]
            if vn >= 0.0:  # already separating
                T["done"].discard(cid)
                continue
            fy = oc.frame.to_frame(point)[1]
            part = "head" if fy > oc.h + oc.shoulder_up - 4 else "body" if fy > 0.45 * oc.stand_h else "legs"
            direction = 1.0 if st.vel[0] >= 0 else -1.0
            guarded = oc.cur is not None and oc.cur.type == "guard" and oc.facing == -direction and part != "legs"
            # an impulse exchange along the normal: the prop against the part of the body that takes the blow (a braced
            # guard couples more of the body), with a restitution of a hard symbol on a body
            m_p, m_b, e = sp.mass, (BODY_MASS_GUARD if guarded else BODY_MASS_HIT), RESTITUTION
            J = -(1.0 + e) * vn * m_p * m_b / (m_p + m_b)
            v_before = st.vel
            self.world.apply_impulse_at(pid, (n[0] * J, n[1] * J), point)
            v_after = self.world.state(pid).vel
            eff = clamp(J / IMPULSE_REF, 0.15, 1.9)  # the blow is what the impulse was (power already set the throw speed)
            data = {"move": "throw", "target": cid, "part": part, "point": point, "dir": direction, "power": round(eff, 3), "prop": pid,
                    "impulse": round(J, 1), "normal": (round(n[0], 4), round(n[1], 4)), "prop_mass": m_p, "body_mass": m_b,
                    "v_before": (round(v_before[0], 1), round(v_before[1], 1)), "v_after": (round(v_after[0], 1), round(v_after[1], 1)),
                    "body_dv": round(J / m_b, 1)}
            if guarded:
                self.emit(Event(t, "blocked", self.cid, data))
                oc._receive(t, self.cid, "throw", "block", eff, direction, part, point)
            else:
                reaction = "flinch" if eff < 0.7 else "stagger" if eff < 1.1 else "knockdown"
                data["reaction"] = reaction
                self.emit(Event(t, "hit", self.cid, data))
                oc._receive(t, self.cid, "throw", reaction, eff, direction, part, point, (-n[0] * direction, max(0.1, -n[1])))
            self.emit(Event(t, "prop_hit", pid, {"prop": pid, "target": cid, "point": point, "normal_speed": -vn, "blocked": guarded,
                                                 "impulse": round(J, 1)}))
            break
