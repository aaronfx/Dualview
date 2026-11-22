"""Combat for the character controller (simulation side): strikes, guards, dodges, hit reactions, knockdowns.

Outcomes are decided in the simulation at the moment of contact, from simple body geometry. The animator then makes
the contact exact at render time, with IK.

- `strike` (move = jab | cross | hook | uppercut | front_kick | side_kick | roundhouse | sweep): close to the move's
  range, wind up, snap, contact, recover. At contact:
  - **whiff** if the target is out of reach (it stepped back), ducked under a high strike, or is down;
  - **blocked** if the target is guarding and facing the attacker (sweeps go under a guard);
  - otherwise a **hit**, with the body part, power and direction.
- Reactions interrupt the target. They are chosen from the strike's effective power, or forced by `reaction`:
  - flinch: the head snaps back;
  - stagger: knocked back a few steps;
  - knockdown: the body becomes a ragdoll (motion/ragdoll.py), falls, and settles face up or face down.

  The target's own queued actions then resume. A pending `wait_for` is kept, and a knocked-down character gets up
  before its next standing action.
- `guard`: fighting stance with fists up (duration or `until`). `dodge`: `back` steps out of reach, `duck` drops under
  head height.

Events:
- attacker: `strike_start`, `swing`, `hit`, `blocked`, `whiff`;
- target: `hurt`, `block_hit`, `evaded`, `knockdown`, `body_fall` (ragdoll thud), `settled`.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from ..core.mathx import clamp
from ..scene.schema import ActionSpec
from .interaction import LIE_H, _smooth

COMBAT = ("strike", "guard", "dodge", "hurt")
LYING_POSTURES = ("prone", "supine")
# move -> limb, target height, timing (anticipation end, contact, end), reach multiplier, base power, push direction
MOVES: Dict[str, Dict[str, Any]] = {
    "jab": dict(limb="hand_n", height="head", t_a=0.10, t_c=0.19, dur=0.42, reach=1.0, power=0.5, push=(1.0, 0.05), lunge=24.0),
    "cross": dict(limb="hand_f", height="head", t_a=0.14, t_c=0.25, dur=0.55, reach=1.06, power=0.85, push=(1.0, 0.05), lunge=30.0),
    "hook": dict(limb="hand_n", height="head", t_a=0.16, t_c=0.30, dur=0.62, reach=0.92, power=0.95, push=(1.0, 0.1), lunge=20.0),
    "uppercut": dict(limb="hand_f", height="head", t_a=0.20, t_c=0.32, dur=0.68, reach=0.85, power=1.15, push=(0.45, 1.0), lunge=22.0),
    "front_kick": dict(limb="foot_n", height="body", t_a=0.16, t_c=0.32, dur=0.72, reach=1.0, power=0.9, push=(1.0, 0.15), lunge=14.0),
    "side_kick": dict(limb="foot_f", height="body", t_a=0.22, t_c=0.38, dur=0.82, reach=1.08, power=1.25, push=(1.0, 0.2), lunge=16.0),
    "roundhouse": dict(limb="foot_f", height="head", t_a=0.26, t_c=0.44, dur=0.9, reach=1.0, power=1.3, push=(1.0, 0.3), lunge=10.0),
    "sweep": dict(limb="foot_n", height="legs", t_a=0.20, t_c=0.36, dur=0.85, reach=1.05, power=1.1, push=(0.45, 0.35), lunge=8.0),
    # Milestone 2: a jumping kick (contact at the top of the arc) and a swing of a carried prop (glyph) as a weapon
    "flying_kick": dict(limb="foot_n", height="body", t_a=0.22, t_c=0.42, dur=0.95, reach=1.0, power=1.4, push=(1.0, 0.3), lunge=78.0,
                        air=0.48),
    "swing_weapon": dict(limb="hand_n", height="body", t_a=0.22, t_c=0.36, dur=0.78, reach=1.0, power=1.15, push=(1.0, 0.25), lunge=18.0,
                         weapon=True),
}
AIR_T = (0.7, 0.70)  # flying kick: takeoff at 0.7 x t_a, landing at this time (s)
HURT_T = {"flinch": 0.38, "stagger": 0.75, "block": 0.32}
DUCK_T, DODGE_BACK_T = 0.55, 0.38


class CombatMixin:
    # ------------------------------------------------------------ geometry
    def _strike_reach(self, move: str) -> float:
        m = MOVES[move]
        if m.get("weapon"):  # the arm and the prop held in the hands
            pid = getattr(self, "carrying", None)
            sp = self.props[pid] if pid else None
            L = (sp.size[0] - (sp.weight or 8.0)) if sp else 0.0  # from the grip to the far end
            return 20.0 + 0.5 * self.arm_reach + L + 8.0 + m["lunge"]
        if m["limb"].startswith("hand"):  # arm + forward lean + lunge + the target's body depth
            return self.arm_reach * m["reach"] + 34.0 + m["lunge"]
        # a kick reaches along the leg from the hip: the higher the target, the closer the kicker has to be
        hip = self.stand_h + (8.0 if move == "roundhouse" else -4.0) + m.get("air", 0.0) * self.stand_h
        dy = self._body_height(m["height"]) - hip
        L = self.p_leg * 1.04 * m["reach"]
        return math.sqrt(max(0.0, L * L - dy * dy)) + 9.0 + m["lunge"]

    def _body_height(self, part: str) -> float:
        p = self.rig.p
        if part == "head":
            return self.h + self.shoulder_up + p.neck + 0.5 * p.head
        if part == "body":
            return self.h + 0.8 * p.spine
        return self.rig.p.ankle_height + 8.0  # legs (the ankles)

    @property
    def lying(self) -> bool:
        return self.posture in LYING_POSTURES

    # ------------------------------------------------------------ action start
    def _start_combat(self, t: float, a: ActionSpec) -> None:
        self.fight_mode = True
        if self.lying:
            if getattr(self, "knocked", False):  # get up first, then do it
                self.queue.appendleft(a)
                self.cur = ActionSpec(type="get_up", character=self.cid)
                self.cur_t0 = t
                self.inter_action = self.cur
                self._start_interaction(t, self.cur)
                return
            raise ValueError(f"{self.cid}: '{a.type}' is not possible while lying down (use get_up first)")
        self.inter = {"t0": t}
        I = self.inter
        if a.type == "strike":
            other = self._pid(a.target)
            oc = self.others[other]
            d = oc.s - self.s
            direction = 1.0 if d >= 0 else -1.0
            want = a.distance if a.distance else 0.9 * self._strike_reach(a.move)  # `distance`: engage from further out
            if abs(d) > want + 14.0 or abs(d) < want - 48.0:
                if self._go(t, a, oc.s - direction * want):
                    return
            if self._face(t, a, direction):
                return
            m = MOVES[a.move]
            if m.get("weapon") and getattr(self, "carrying", None) is None:
                raise ValueError(f"{self.cid}: swing_weapon needs a carried prop (pick_up first)")
            I.update(other=other, move=a.move, dir=direction, s0=self.s, resolved=False)
            self._open("strike", t, move=a.move, other=other, dir=direction, t_a=m["t_a"], t_c=m["t_c"], dur=m["dur"],
                       limb=m["limb"], height=m["height"], weapon=getattr(self, "carrying", None) if m.get("weapon") else None)
            self.emit(self._ev(t, "strike_start", {"move": a.move, "target": other}))
            self.emit(self._ev(t + m["t_a"], "swing", {"move": a.move, "target": other}))
        elif a.type == "guard":
            I.update(phase="guard")
            self._open("guard", t)
        elif a.type == "dodge":
            I.update(kind=a.dodge, s0=self.s)
            dur = DUCK_T if a.dodge == "duck" else DODGE_BACK_T
            self.dodging = {"kind": a.dodge, "t0": t, "t1": t + dur}
            self._open("dodge", t, style=a.dodge, dur=dur, dir=-self.facing, s0=self.s)
            self.emit(self._ev(t, "dodge", {"kind": a.dodge}))

    # ------------------------------------------------------------ per step
    def _tick_combat(self, t: float, dt: float, a: ActionSpec) -> None:
        I = self.inter
        tau = t - self.cur_t0
        if a.type == "strike":
            m = MOVES[I["move"]]
            # the step-in starts in the wind-up (push off the rear foot) and lands with the blow, then steps back out
            t0 = 0.4 * m["t_a"]
            u = _smooth((tau - t0) / max(0.05, m["t_c"] - t0)) * (1.0 - _smooth((tau - m["t_c"] - 0.06) / 0.3))
            if m.get("air"):  # a jumping lunge: up and over, contact near the top of the arc, land in stance
                t_up, t_dn = AIR_T[0] * m["t_a"], AIR_T[1]
                ua = clamp((tau - t_up) / (t_dn - t_up), 0.0, 1.0)
                self.h = self.stand_h + m["air"] * self.stand_h * 4.0 * ua * (1.0 - ua)
                u = _smooth((tau - t_up) / (m["t_c"] - t_up))  # the forward travel ends as the foot arrives, then he drops
                if not I.get("up") and tau >= t_up:
                    I["up"] = True
                    self.emit(self._ev(t, "takeoff", {"surface": self.frame.tag, "speed": m["lunge"] / (t_dn - t_up), "apex": m["air"] * self.stand_h}))
                if not I.get("down") and tau >= t_dn:
                    I["down"] = True
                    self.h = self.stand_h
                    self.emit(self._ev(t, "impact", {"surface": self.frame.tag, "normal_speed": 420.0,
                                                     "point": self.frame.to_world(self.s, 0.0), "tangent_speed": 0.0}))
            self.s = I["s0"] + I["dir"] * m["lunge"] * u
            if I.get("recoil"):
                self.s -= I["dir"] * I["recoil"] * _smooth((tau - m["t_c"]) / 0.3)
            if m.get("weapon") and self.carrying is not None:  # the prop follows the swing (simulation-side pose)
                ext = clamp(1.0 - abs(tau - m["t_c"]) / 0.22, 0.0, 1.0)
                if not I.get("obstructed") and not self._pose_prop(self.carrying, *self._hold_pose(self.carrying, self._weapon_angle(tau, m), ext), t):
                    I["obstructed"] = True  # the swing is stopped by a structure: it cannot reach the target
            if not I["resolved"] and tau >= m["t_c"]:
                I["resolved"] = True
                self._resolve_strike(t, a, m)
            if tau >= m["dur"]:
                self._next_action(t)
        elif a.type == "guard":
            st = I.get("stun")
            if st is not None:  # pushed back by a blocked strike
                u = clamp((t - st[0]) / HURT_T["block"], 0.0, 1.0)
                self.s = st[3] + st[1] * st[2] * (1.0 - (1.0 - u) ** 2.4)
            if (a.until and self._event_seen(a.until, t)) or (a.duration and tau >= a.duration) or (not a.until and not a.duration and tau >= 1.0):
                self._next_action(t)
        elif a.type == "dodge":
            dur = DUCK_T if I["kind"] == "duck" else DODGE_BACK_T
            if I["kind"] == "back":
                self.s = I["s0"] - self.facing * 0.7 * self.stand_h * _smooth(tau / dur)
            else:
                down = _smooth(tau / 0.12) - _smooth((tau - dur + 0.2) / 0.2)
                self.h = self.stand_h - 0.46 * self.stand_h * down
                self.s = I["s0"] - self.facing * 0.3 * self.stand_h * down  # sit back, away from the blow
            if tau >= dur:
                self.h = self.stand_h
                self.dodging = None
                self._next_action(t)
        elif a.type == "hurt":
            dur = I["dur"]
            self.s = I["s0"] + I["dir"] * I["dist"] * (1.0 - (1.0 - clamp(tau / dur, 0.0, 1.0)) ** 2.4)
            if tau >= dur:
                self._next_action(t)

    @staticmethod
    def _weapon_angle(tau: float, m: Dict[str, Any]) -> float:
        """Swing angle of a wielded prop, relative to forward: raised back over the shoulder, cut down through the
        target level at contact, follow through low, then back to the carry angle."""
        ta, tc, dur = m["t_a"], m["t_c"], m["dur"]
        if tau < ta:
            return 0.35 + 1.75 * _smooth(tau / ta)
        if tau < tc:
            u = (tau - ta) / (tc - ta)
            return 2.1 - 2.1 * (1.0 - (1.0 - u) ** 3)
        if tau < tc + 0.16:
            return -0.55 * _smooth((tau - tc) / 0.16)
        return -0.55 + 0.9 * _smooth((tau - tc - 0.16) / max(0.1, dur - tc - 0.16))

    def _resolve_strike(self, t: float, a: ActionSpec, m: Dict[str, Any]) -> None:
        I = self.inter
        oc = self.others[I["other"]]
        direction = I["dir"]
        dx = (oc.s - self.s) * direction
        part = m["height"]
        point = self.frame.to_world(oc.s - direction * 8.0, oc._body_height(part) if not oc.lying else LIE_H)
        data = {"move": I["move"], "target": I["other"], "part": part, "point": point, "dir": direction}
        dodge = getattr(oc, "dodging", None)
        if oc.lying or oc.mode != "grounded" or I.get("obstructed"):
            outcome = "whiff"
        elif dx > self._strike_reach(I["move"]) - abs(self.s - I["s0"]) or dx < 0:  # reach from where the lunge has brought him
            outcome = "whiff"
        elif dodge and dodge["kind"] == "duck" and part == "head" and dodge["t0"] <= t <= dodge["t1"]:
            outcome = "whiff"
        elif oc.cur is not None and oc.cur.type == "roll" and part != "legs" and oc.h < 0.6 * oc.stand_h:
            outcome = "whiff"  # rolled under it
        elif (oc.cur is not None and oc.cur.type == "guard" and oc.facing == -direction and part != "legs"):
            outcome = "blocked"
        else:
            outcome = "hit"
        eff = a.power * m["power"] * (self.strength / 45000.0)
        data["power"] = round(eff, 3)
        if outcome == "whiff":
            self.emit(self._ev(t, "whiff", data))
            oc.emit(oc._ev(t, "evaded", {"by": self.cid, "move": I["move"]}))
            return
        if outcome == "blocked":
            I["recoil"] = 16.0 + 26.0 * min(1.5, eff)  # the attacker rebounds off the guard
            self.emit(self._ev(t, "blocked", data))
            oc._receive(t, self.cid, I["move"], "block", eff, direction, part, point)
            return
        reaction = a.reaction if a.reaction not in (None, "auto") else ("flinch" if eff < 0.7 else "stagger" if eff < 1.1 else "knockdown")
        if part == "legs":
            reaction = "knockdown" if a.reaction in (None, "auto") else reaction
        data["reaction"] = reaction
        self.emit(self._ev(t, "hit", data))
        if a.disarm and oc.carrying is not None:
            oc._release_carried(t, (direction * (120.0 + 50.0 * eff), 105.0), -direction * 5.0,
                                kind="disarmed", by=self.cid)
        oc._receive(t, self.cid, I["move"], reaction, eff, direction, part, point, m["push"])

    # ------------------------------------------------------------ receiving
    def _receive(self, t: float, by: str, move: str, reaction: str, eff: float, direction: float, part: str,
                 point, push=(1.0, 0.1)) -> None:
        if reaction == "block":
            self.emit(self._ev(t, "block_hit", {"by": by, "move": move, "point": point, "power": eff}))
            if self.cur is not None and self.cur.type == "guard":  # absorbed by the guard: recoil, keep guarding
                self.inter["stun"] = (t, direction, 8.0 + 22.0 * eff, self.s)
                self.seg.data.setdefault("blocks", []).append(t)
                return
            self._hurt(t, "block", direction, 8.0 + 22.0 * eff)
            return
        self.emit(self._ev(t, "hurt", {"by": by, "move": move, "part": part, "point": point, "reaction": reaction, "power": eff}))
        if reaction == "knockdown":
            self.emit(self._ev(t, "knockdown", {"point": point, "power": eff}))
        if self.cur is not None and self.cur.type == "wait_for" and not self._event_seen(self.cur.until, t):
            self.queue.appendleft(self.cur)  # still waiting for its event after the reaction (unless this hit was it)
        self.dodging = None
        if reaction == "knockdown":
            self._knockdown(t, direction, eff, part, point, push)
        elif reaction == "stagger":
            self._hurt(t, "stagger", direction, 40.0 + 45.0 * eff, part=part)
        else:
            self._hurt(t, "flinch", direction, 6.0 + 10.0 * eff, part=part)

    def _hurt(self, t: float, kind: str, direction: float, dist: float, part: str = "body") -> None:
        dur = HURT_T[kind]
        self.cur = ActionSpec.model_construct(type="hurt", character=self.cid, duration=dur, until=None, target=None)
        self.cur_t0 = t
        self.inter = {"t0": t, "dur": dur, "dir": direction, "dist": dist, "s0": self.s, "kind": kind}
        self.h = self.stand_h
        self._open("hurt", t, react=kind, dir=direction, dist=dist, part=part, dur=dur, s0=self.s)

    # ------------------------------------------------------------ knockdown: ragdoll
    def _knockdown(self, t: float, direction: float, eff: float, part: str, point, push) -> None:
        from ..physics.world import ALL, CAT_CHAR
        from ..rig.stickman import Pose, base_pose, set_arm, set_lean
        from .ragdoll import Ragdoll
        import pymunk
        L = base_pose()
        set_lean(L, -0.12 if part != "legs" else 0.05, head=0.15)
        set_arm(L, "n", 0.9, 1.4)
        set_arm(L, "f", 0.7, 1.5)
        pose = Pose(root=self.frame.to_world(self.s, self.h), body_angle=self.frame.body_angle, facing=self.facing, local=L)
        tan = self.frame.tangent
        vel = (tan[0] * self.v, tan[1] * self.v)
        from .ragdoll import RELAXED
        from .acrobatics import BODY_PASS_Z
        in_lane = any(c is not self and abs(c.z - self.z) < BODY_PASS_Z and not c.lying for c in self.others.values())
        rag = Ragdoll(self.world, self.rig, pose, f"{self.cid}~rag", vel=vel, relax=RELAXED, hit_characters=in_lane)
        # the whole body is launched (knockback), the struck part a little faster so the body tips over it
        px, py = push
        speed = 140.0 + 100.0 * min(1.8, eff)
        launch = (direction * px * speed, (0.35 + 0.65 * max(0.0, py)) * speed * 0.55)
        for name, body in rag.bodies.items():
            body.velocity = (body.velocity.x + launch[0], body.velocity.y + launch[1])
        if part == "legs":  # swept: the feet are taken out (up), the upper body drops back, away from the attacker
            for name in ("shin_n", "shin_f"):
                b = rag.bodies[name]
                b.velocity = (b.velocity.x - direction * 0.35 * speed, b.velocity.y + 0.75 * speed)
            for name in ("chest", "head"):
                b = rag.bodies[name]
                b.velocity = (b.velocity.x + direction * 0.7 * speed, b.velocity.y - 0.2 * speed)
        else:
            for name, k in (("head", 0.9 if part == "head" else 0.4), ("chest", 0.6), ("spine", 0.2)):
                b = rag.bodies[name]
                b.velocity = (b.velocity.x + direction * k * speed, b.velocity.y + 0.15 * k * speed)
        self.ragdoll = rag
        self.knocked = True
        self.cur = None
        self.queue_hold = True
        self.mode = "ragdoll"
        self.inter = {"t0": t, "thud": False}
        sh = self.world._shapes[self.cid]
        self._cap_filter = sh.filter
        sh.filter = pymunk.ShapeFilter(categories=CAT_CHAR, mask=0)  # the ragdoll is the body now
        self._open("ragdoll", t, samples=[], facing0=self.facing, half=dict(rag.half), foot_local=dict(rag.foot_local))
        self.seg.data["samples"].append((t, rag.sample()))

    def _ragdoll_after_step(self, t: float, contacts) -> None:
        rag = self.ragdoll
        self.seg.data["samples"].append((t, rag.sample()))
        pel, _ = rag.part_ends("spine")
        chest = rag.bodies["chest"]
        self.world.set_kinematic(self.cid, pel, chest.angle - math.pi / 2)
        if not self.inter.get("thud"):
            for c in contacts:
                if c.a.startswith(f"{self.cid}~rag:") and c.b in self.frames and c.normal_speed > 120.0 and \
                        c.a.split(":")[1] in ("spine", "chest", "head"):
                    self.inter["thud"] = True
                    self.emit(self._ev(t, "body_fall", {"point": c.point, "normal_speed": c.normal_speed}))
                    break
        v, _ = rag.max_speed()
        if t - self.inter["t0"] > 0.35 and v < 160.0:  # down and slowing: the body relaxes into its sprawl
            self.inter["slow_t"] = self.inter.get("slow_t") or t
            self.seg.data.setdefault("relax_t", t)  # the animation eases the limbs into a sprawl from here
            rag.set_tone(1.0 + 7.0 * min(1.0, (t - self.inter["slow_t"]) / 0.45))
        if t - self.inter["t0"] > 0.5 and (rag.settled(t) or t - self.inter["t0"] > 3.5):
            self._ragdoll_settle(t)

    def _ragdoll_settle(self, t: float) -> None:
        rag = self.ragdoll
        posture, facing, pel, chest_ang = rag.lying()
        rag.remove()
        self.ragdoll = None
        self.world._shapes[self.cid].filter = self._cap_filter
        s, _ = self.frame.to_frame(pel)
        self.s, self.h, self.v = s, LIE_H, 0.0
        self.facing = facing
        self.posture = posture
        self.body_tilt = math.pi / 2 if posture == "prone" else -math.pi / 2
        self.mode = "grounded"
        self.world.set_solid_to_props(self.cid, True)
        self.emit(self._ev(t, "settled", {"posture": posture, "point": pel}))
        self._open(posture, t, rest=True, from_ragdoll=True)
        self._place(t)
        self.cur = None
        self.queue_hold = False

    # ------------------------------------------------------------ getting up from the back
    def _getup_back_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        """Supine -> sit up -> squat over the feet -> stand (facing the feet)."""
        I = self.inter
        tau = t - self.cur_t0
        T = 1.5
        u = clamp(tau / T, 0.0, 1.0)
        pl = self.p_leg
        # uneven timing: a quick sit-up with momentum, a beat while a hand plants, the weight rocks forward over the
        # feet, the rise, then a small overshoot as the body steadies itself
        tilt_keys = [(0.0, -math.pi / 2), (0.22, -0.38), (0.36, -0.26), (0.58, 0.48), (0.8, 0.1), (0.9, -0.04), (1.0, 0.0)]
        h_keys = [(0.0, LIE_H), (0.22, LIE_H + 4.0), (0.36, LIE_H + 6.0), (0.58, 0.5 * pl), (0.8, 0.84 * pl),
                  (0.9, self.stand_h + 1.5), (1.0, self.stand_h)]
        fwd_keys = [(0.0, 0.0), (0.22, 0.07 * pl), (0.36, 0.11 * pl), (0.58, 0.48 * pl), (1.0, 0.53 * pl)]

        def interp(keys):
            for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
                if u <= u1:
                    return v0 + (v1 - v0) * _smooth((u - u0) / (u1 - u0))
            return keys[-1][1]

        self.body_tilt = interp(tilt_keys)
        self.h = interp(h_keys)
        self.s = I["s0"] + self.facing * interp(fwd_keys)
        self._place(t)
        if u >= 1.0:
            self.posture, self.body_tilt, self.h = "stand", 0.0, self.stand_h
            self.world.set_solid_to_props(self.cid, False)
            self.knocked = False
            self.emit(self._ev(t, "stood_up", {"helper": None, "from": "back"}))
            self._next_action(t)
