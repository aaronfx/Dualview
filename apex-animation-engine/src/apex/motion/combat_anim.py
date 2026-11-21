"""Pose evaluation for combat (animation side of combat.py).

- **Fighting stance:** crouched, chin down, fists up, staggered feet, a slight bob.
- **Strikes:** anticipation (wind-up and dip), a snap with a fast-out curve, a short hold on contact, then a return
  to guard. The striking fist or foot is solved with IK onto the *target's* body point at that instant, so the
  contact is exact. A whiff extends to full reach through empty space.
- **Kicks:** the support leg stays planted, the kicking leg chambers the knee and extends, and the torso leans
  away as a counterweight.
- **Reactions:** a flinch snaps the head back, a stagger is knocked back with stepping feet, a blocked strike pushes
  the guard back.
- **Dodges:** a back-step with a lean, or a deep duck under the strike.
- **Ragdoll:** the simulated fall replayed from samples (motion/ragdoll.py).
- **Lying face up (supine):** a relaxed pose with a little breathing.
- **Getting up from the back:** sit up with the hands behind, then squat over the planted feet, then stand.
"""
from __future__ import annotations

import bisect
import math
from typing import Optional, Tuple

from ..core.mathx import Vec, clamp, lerp, smoothstep, wrap_angle
from ..rig.stickman import PI, Pose, base_pose, set_arm, set_lean
from .combat import MOVES
from .controller import Segment
from .ragdoll import pose_from_sample

FIGHT_STANCE = (16.0, -18.0)


def _snap(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return 1.0 - (1.0 - u) ** 3


class CombatAnimMixin:
    # ------------------------------------------------------------ helpers
    def _target_point(self, other: str, t: float, height: str, toward: float) -> Vec:
        """A point on the other character's body at time t (head / body / legs), on the side facing the attacker."""
        an = self.others[other]
        import numpy as np
        rx, ry = an.root_at(t)
        ang = float(np.interp(t, an.T, an.ANG))
        up = (-math.sin(ang), math.cos(ang))
        p = an.p
        if height == "head":
            d = p.spine + p.chest + p.neck + 0.5 * p.head - 4.0
        elif height == "body":
            d = 0.8 * p.spine
        else:  # legs: the ankles, just above the floor (what a sweep takes out)
            return rx - toward * 9.0, p.ankle_height + 8.0
        return rx + up[0] * d - toward * 9.0, ry + up[1] * d

    def _guard_arms(self, pose: Pose, w: float = 1.0, bob: float = 0.0) -> None:
        L = pose.local
        set_arm(L, "n", lerp(0.15, 1.3 + 0.05 * bob, w), lerp(0.3, 1.95, w))
        set_arm(L, "f", lerp(-0.1, 0.95 - 0.05 * bob, w), lerp(0.35, 2.35, w))
        pose.hands["n"] = pose.hands["f"] = "fist"

    def _fight_base(self, seg: Segment, t: float, crouch: float = 10.0, lean: float = 0.12) -> Tuple[Pose, object, float]:
        pose, F = self._base(seg, t)
        s = self._rec(self.S, t, seg)
        h = self._rec(self.H, t, seg)
        pose.root = F.to_world(s, min(h, self.stand_h) - 2.0 - crouch)
        set_lean(pose.local, lean, chest=-0.05, head=-0.1)
        return pose, F, s

    # ------------------------------------------------------------ stance / guard
    def _eval_guard(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        bob = math.sin(2 * PI * tau / 0.9)
        recoil = max([math.exp(-(t - tb) * 9.0) * smoothstep(0.0, 0.03, t - tb) for tb in seg.data.get("blocks", []) if t >= tb] or [0.0])
        pose, F, s = self._fight_base(seg, t, crouch=10.0 + 2.0 * bob + 4.0 * recoil, lean=0.12 + 0.01 * bob - 0.2 * recoil)
        self._stand_legs(pose, F, seg, t)
        self._guard_arms(pose, 1.0, bob)
        pose.twist = -0.15
        pose.eye = 0.85 - 0.5 * recoil
        return pose

    # ------------------------------------------------------------ strikes
    def _eval_strike(self, seg: Segment, t: float) -> Pose:
        d = seg.data
        tau = t - seg.t0
        ta, tc, dur = d["t_a"], d["t_c"], d["dur"]
        move, limb, f = d["move"], d["limb"], seg.facing
        kick = limb.startswith("foot")
        side = limb[-1]
        wind = math.sin(PI * clamp(tau / ta, 0.0, 1.0))  # anticipation
        if tau < ta:
            ext = -0.15 * wind
        elif tau < tc:
            ext = _snap((tau - ta) / (tc - ta))
        elif tau < tc + 0.07:
            ext = 1.0
        else:
            ext = 1.0 - smoothstep(tc + 0.07, dur, tau)
        ext_pos = max(0.0, ext)
        crouch = 10.0 + 6.0 * wind + (12.0 * ext_pos if move == "sweep" else 0.0) - (8.0 * ext_pos if move == "roundhouse" else 0.0)
        if move == "uppercut":
            crouch += 10.0 * wind - 6.0 * ext_pos
        lean = 0.12 + (0.22 * ext_pos if not kick else -0.32 * ext_pos) - 0.05 * wind
        pose, F, s = self._fight_base(seg, t, crouch=crouch, lean=lean)
        self._stand_legs(pose, F, seg, t)
        self._guard_arms(pose, 1.0)
        twist = {"jab": 0.25, "cross": -0.6, "hook": 0.45, "uppercut": -0.4}.get(move, 0.0)
        pose.twist = -0.15 + twist * ext_pos
        pose.hip_twist = 0.3 * twist * ext_pos
        pose.eye = 0.7
        # where the blow lands (the target's body now), or full reach into empty space
        aim = self._target_point(d["other"], t, d["height"], f)
        j = self.rig.world_joints(pose)
        if not kick:
            sh = j[f"shoulder_{side}"]
            chamber = (sh[0] - f * 4.0, sh[1] - (22.0 if move == "uppercut" else 8.0))
            reach = self.p.upper_arm + self.p.forearm
            dx, dy = aim[0] - sh[0], aim[1] - sh[1]
            dist = math.hypot(dx, dy)
            if dist > reach * 1.02:  # out of range: a full extension toward it (a whiff)
                aim = (sh[0] + dx / dist * reach * 0.99, sh[1] + dy / dist * reach * 0.99)
            arc = {"hook": 14.0, "uppercut": -18.0}.get(move, 0.0) * math.sin(PI * clamp(ext_pos, 0.0, 1.0))
            if ext <= 0.0:  # winding up: pull the fist back
                tgt = (chamber[0] - f * 10.0 * wind, chamber[1])
            else:
                tgt = (lerp(chamber[0], aim[0], ext_pos), lerp(chamber[1], aim[1], ext_pos) + arc)
            self.rig.arm_ik(pose, side, tgt, fingertip=False)
            pose.hands[side] = "fist"
            other = "f" if side == "n" else "n"
            set_arm(pose.local, other, 1.1, 2.3)  # the other hand stays up guarding the face
        else:
            hip = j[f"hip_{side}"]
            legu = self.p.thigh + self.p.shin
            knee_up = F.to_world(F.to_frame(hip)[0] + f * 0.35 * legu, F.to_frame(hip)[1] - 0.35 * legu)
            if move == "sweep":
                knee_up = F.to_world(F.to_frame(hip)[0] + f * 0.2 * legu, self.p.ankle_height + 10.0)
            dx, dy = aim[0] - hip[0], aim[1] - hip[1]
            dist = math.hypot(dx, dy)
            if dist > legu * 1.06:
                aim = (hip[0] + dx / dist * legu * 1.05, hip[1] + dy / dist * legu * 1.05)
            rest = F.to_world(F.to_frame(j[f"ankle_{side}"])[0], self.p.ankle_height)
            if ext <= 0.0:
                tgt = (lerp(rest[0], knee_up[0], wind * 0.6), lerp(rest[1], knee_up[1], wind * 0.6))
            elif ext_pos < 1.0 and tau < tc:  # chamber -> extend
                u = ext_pos
                mid = knee_up
                tgt = ((1 - u) ** 2 * rest[0] + 2 * (1 - u) * u * mid[0] + u * u * aim[0],
                       (1 - u) ** 2 * rest[1] + 2 * (1 - u) * u * mid[1] + u * u * aim[1])
            else:  # hold, then retract through the chamber back to the floor
                u = ext_pos
                tgt = ((1 - u) ** 2 * rest[0] + 2 * (1 - u) * u * knee_up[0] + u * u * aim[0],
                       (1 - u) ** 2 * rest[1] + 2 * (1 - u) * u * knee_up[1] + u * u * aim[1])
            ang = 0.0 if move in ("front_kick", "sweep") else -0.5
            self.rig.leg_ik(pose, side, tgt, ang, max_stretch=1.1)
        return pose

    # ------------------------------------------------------------ reactions and dodges
    def _eval_hurt(self, seg: Segment, t: float) -> Pose:
        d = seg.data
        tau = t - seg.t0
        k = d["react"]
        dur = d["dur"]
        hit = math.exp(-tau * (9.0 if k == "flinch" else 5.0)) * smoothstep(0.0, 0.04, tau)
        rec = smoothstep(0.0, dur, tau)
        if k == "block":
            pose, F, s = self._fight_base(seg, t, crouch=10.0, lean=0.12 - 0.18 * hit)
            self._stand_legs(pose, F, seg, t)
            self._guard_arms(pose, 1.0)
            pose.eye = 0.6
            return pose
        body = d.get("part") == "body"
        lean = (0.4 * hit if body else -0.35 * hit) * (1.0 if k == "flinch" else 1.5) + 0.12 * rec
        pose, F, s = self._fight_base(seg, t, crouch=6.0 + 8.0 * hit, lean=lean)
        L = pose.local
        set_lean(L, lean, chest=(-0.2 * hit if not body else 0.15 * hit), head=(-0.7 * hit if not body else 0.4 * hit))
        self._stand_legs(pose, F, seg, t)
        flail = math.sin(2 * PI * tau / 0.35) * hit
        set_arm(L, "n", lerp(1.3, 0.6 + 0.6 * flail, hit), lerp(1.9, 0.6, hit))
        set_arm(L, "f", lerp(0.95, 1.4 - 0.6 * flail, hit), lerp(2.3, 0.8, hit))
        pose.hands["n"] = pose.hands["f"] = "open" if hit > 0.4 else "fist"
        pose.eye = 0.2 + 0.6 * rec
        return pose

    def _eval_dodge(self, seg: Segment, t: float) -> Pose:
        d = seg.data
        tau = t - seg.t0
        if d["style"] == "duck":
            down = smoothstep(0.0, 0.12, tau) * (1 - smoothstep(d["dur"] - 0.2, d["dur"], tau))
            pose, F, s = self._fight_base(seg, t, crouch=4.0, lean=0.12 + 0.22 * down)
            set_lean(pose.local, 0.12 + 0.22 * down, chest=0.12 * down, head=-0.35 * down)
        else:
            back = math.sin(PI * clamp(tau / d["dur"], 0.0, 1.0))
            pose, F, s = self._fight_base(seg, t, crouch=10.0 + 4.0 * back, lean=0.12 - 0.3 * back)
        self._stand_legs(pose, F, seg, t)
        self._guard_arms(pose, 1.0)
        pose.eye = 0.9
        return pose

    # ------------------------------------------------------------ ragdoll and lying face up
    def _eval_ragdoll(self, seg: Segment, t: float) -> Pose:
        d = seg.data
        S = d["samples"]
        if "_ts" not in d:
            d["_ts"] = [x[0] for x in S]
        ts = d["_ts"]
        i = bisect.bisect_right(ts, t) - 1
        i = max(0, min(i, len(S) - 1))
        a = S[i][1]
        if i + 1 < len(S) and ts[i + 1] > ts[i]:
            b = S[i + 1][1]
            w = clamp((t - ts[i]) / (ts[i + 1] - ts[i]), 0.0, 1.0)
            out = a.copy()
            for k in range(0, len(a), 3):
                out[k] = lerp(a[k], b[k], w)
                out[k + 1] = lerp(a[k + 1], b[k + 1], w)
                out[k + 2] = a[k + 2] + wrap_angle(b[k + 2] - a[k + 2]) * w
            a = out
        pose = pose_from_sample(self.rig, a, d["facing0"], d["foot_local"], d["half"])
        pose.state = "ragdoll"
        return pose

    def _eval_supine(self, seg: Segment, t: float) -> Pose:
        pose, F = self._lying_base(seg, t)
        tau = t - seg.t0
        breath = math.sin(2 * PI * tau / 2.2)
        L = pose.local
        set_lean(L, 0.0, chest=0.03 * breath, head=0.05)
        L["thigh_n"], L["shin_n"], L["foot_n"] = -PI / 2 + 0.14, -0.3, PI / 2 - 0.25
        L["thigh_f"], L["shin_f"], L["foot_f"] = -PI / 2 + 0.04, -0.1, PI / 2 - 0.35
        set_arm(L, "n", 0.08, 0.25)
        set_arm(L, "f", 0.04, 0.2)
        pose.hands["n"] = pose.hands["f"] = "open"
        pose.eye = 0.35 + 0.1 * breath
        self._ground_clamp(pose, F)
        return pose

    def _eval_getup_back(self, seg: Segment, t: float) -> Pose:
        pose, F = self._lying_base(seg, t)
        f = pose.facing
        tilt = -f * wrap_angle(pose.body_angle - F.body_angle)  # -pi/2 lying on the back -> 0 standing
        s, h = F.to_frame(pose.root)
        legu = self.p.thigh + self.p.shin
        s0 = seg.data.get("s0", s)
        L = pose.local
        sit = smoothstep(-PI / 2, -0.4, tilt)  # 0 lying -> 1 sitting up
        set_lean(L, 0.15 * sit, chest=-0.05, head=-0.2 * sit)
        for k, side in enumerate("nf"):
            ank = F.to_world(s0 + f * (0.62 - 0.15 * k) * legu, self.p.ankle_height)
            self.rig.leg_ik(pose, side, ank, 0.0, max_stretch=1.04)
        self._knees_above_floor(pose, F)
        self._ground_clamp(pose, F)
        if tilt < -0.25:  # sitting up: hands behind on the floor, pushing
            j = self.rig.world_joints(pose)
            for k, side in enumerate("nf"):
                ss, _ = F.to_frame(j[f"shoulder_{side}"])
                self._arm_floor_safe(pose, side, F.to_world(ss - f * (14.0 + 6.0 * k), 3.0), F)
                pose.hands[side] = "open"
        else:  # arms forward for balance, then back to guard
            w = smoothstep(0.1, 0.4, tilt)
            set_arm(L, "n", 1.2 - 0.0 * w, 0.6 + 1.2 * w)
            set_arm(L, "f", 1.0, 0.8 + 1.4 * w)
        pose.eye = 0.8
        return pose
