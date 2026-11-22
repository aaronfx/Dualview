"""Pose evaluation for physical interaction (animation side of interaction.py).

Hands are solved with IK onto the *simulated* positions of props (grips on a container, a post's end, a lever's
handle) and of the other character (a shared hand-grab point, a shoulder). Contacts therefore follow the physics
exactly. Bodies lying down are the same rig rotated about the pelvis (`body_angle`), so every standing tool keeps
working: legs, arm IK and gaze.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

from ..core.mathx import Vec, clamp, lerp, lerp_angle, smoothstep
from ..rig.stickman import PI, Pose, base_pose, set_arm, set_lean
from .controller import Segment
from .interaction import CRAWL_SPEED, GESTURE_CONTACT, LIE_H, PRESS_T

STANCE = {  # (front foot, rear foot) as multiples of the leg-length unit, relative to the pelvis, along facing
    "push": (8.0, -36.0), "lift": (16.0, -20.0), "lever": (10.0, -26.0), "offer": (12.0, -16.0), "gesture": (9.0, -9.0),
    # combat: a staggered fighting stance
    "strike": (16.0, -18.0), "guard": (16.0, -18.0), "dodge": (16.0, -18.0), "hurt": (16.0, -18.0),
    # symbols (Milestone 2)
    "pick_up": (14.0, -20.0), "throw": (22.0, -24.0),
}
LYING = ("fall", "prone", "crawl", "getup", "ragdoll", "supine")
MOVING_STANCE = ("dodge", "hurt")  # the feet step to follow the pelvis (back-steps, staggers)


class InteractionAnimMixin:
    # ------------------------------------------------------------ shared helpers
    def root_at(self, t: float) -> Vec:
        import numpy as np
        return float(np.interp(t, self.T, self.PX)), float(np.interp(t, self.T, self.PY))

    def _prop_world(self, pid: str, t: float, local: Vec) -> Vec:
        x, y, a = self.prop_at(pid, t)
        ca, sa = math.cos(a), math.sin(a)
        return x + local[0] * ca - local[1] * sa, y + local[0] * sa + local[1] * ca

    def _dyn_gaze(self, ref: Optional[str], t: float) -> Optional[Vec]:
        if not ref:
            return None
        kind, _, rid = ref.partition(":")
        if kind == "prop":
            x, y, _ = self.prop_at(rid, t)
            return (x, y)
        if kind == "char" and rid in self.others:
            o = self.others[rid]
            rx, ry = o.root_at(t)
            return (rx, ry + 0.9 * o.stand_h)
        return None

    def _link_point(self, other: str, t: float) -> Vec:
        """Shared hand-grab point between this character and `other` (both hands IK to it: they really touch)."""
        o = self.others[other]
        a, b = self.root_at(t), o.root_at(t)
        F = self.frames["floor"]
        h = 0.5 * (self.stand_h + o.stand_h) * 0.95
        return ((a[0] + b[0]) / 2, F.to_world(0.0, h)[1])

    def _held_grip(self, other: str, g: Vec, t: float, t_grab: float) -> Vec:
        """Once two hands have taken hold, both go to one grip point between the real shoulders (so they stay together
        while one pulls the other up), blended in from the meeting point `g`."""
        if getattr(self, "_no_grip", False) or getattr(self.others[other], "_no_grip", False):
            return g
        from .rescue import grip_point
        G = grip_point(self, self.others[other], t)
        w = smoothstep(t_grab, t_grab + 0.12, t)
        return (lerp(g[0], G[0], w), lerp(g[1], G[1], w))

    def _shoulder_of(self, other: str, t: float) -> Vec:
        o = self.others[other]
        rx, ry = o.root_at(t)
        return (rx, ry + o.p.spine + 0.86 * o.p.chest)

    def _stand_pose(self, seg: Segment, t: float, crouch: float, lean: float, chest: float = 0.0, head: float = 0.0) -> Tuple[Pose, object, float]:
        pose, F = self._base(seg, t)
        s = self._rec(self.S, t, seg)
        pose.root = F.to_world(s, self.stand_h - 2.0 - crouch)
        set_lean(pose.local, lean, chest=chest, head=head)
        return pose, F, s

    def _stand_legs(self, pose: Pose, F, seg: Segment, t: float) -> None:
        plants, lift, ang = self._settle_feet(seg, t)
        self._legs(pose, F, plants, lift, ang)

    def _hands_to(self, pose: Pose, targets, tip: bool = True, shape: str = "fist") -> None:
        for side, tgt in targets:
            if tgt is None:
                continue
            self.rig.arm_ik(pose, side, tgt, fingertip=tip)
            pose.hands[side] = shape

    # ------------------------------------------------------------ push
    def _eval_push(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        ts = seg.data["t_strain"] - seg.t0
        strain = smoothstep(ts, ts + 0.8, tau) * seg.data.get("effort", 1.0)
        trem = math.sin(2 * PI * 7.5 * tau) * strain
        pose, F, s = self._stand_pose(seg, t, crouch=8.0 + 10.0 * strain + 0.8 * trem, lean=0.32 + 0.38 * strain + 0.01 * trem,
                                      chest=-0.05, head=-0.25 - 0.1 * strain)
        pose.eye = 1.0 - 0.45 * strain
        self._stand_legs(pose, F, seg, t)
        g = self._prop_world(seg.data["prop"], t, seg.data["grip_local"])
        tan = F.tangent
        self._hands_to(pose, [("n", (g[0] - tan[0] * 2 * seg.facing, g[1] + 7)), ("f", (g[0], g[1] - 9))], shape="open")
        pose.twist = 0.12 * strain
        return pose

    # ------------------------------------------------------------ falling, lying, crawling, getting up
    def _lying_base(self, seg: Segment, t: float) -> Tuple[Pose, object]:
        F = self.frames[seg.frame]
        pose = Pose(local=base_pose(), facing=seg.facing, state=seg.kind)
        pose.root = (self._rec(self.PX, t, seg), self._rec(self.PY, t, seg))
        pose.body_angle = self._rec(self.ANG, t, seg)
        return pose, F

    def _arm_floor_safe(self, pose: Pose, side: str, tgt: Vec, F, tip: bool = True) -> None:
        """Arm IK for a body lying down: of the two elbow solutions, keep the one whose elbow stays above the floor."""
        best = None
        for bend in (-1, 1):
            self.rig.arm_ik(pose, side, tgt, fingertip=tip, bend=bend)
            eh = F.to_frame(self.rig.world_joints(pose)[f"elbow_{side}"])[1]
            if best is None or eh > best[0]:
                best = (eh, bend)
        self.rig.arm_ik(pose, side, tgt, fingertip=tip, bend=best[1])

    def _floor_hands(self, pose: Pose, F, ahead: Tuple[float, float], lift: Tuple[float, float] = (0.0, 0.0)) -> None:
        ch = self.rig.world_joints(pose)
        for k, side in enumerate("nf"):
            sh = ch[f"shoulder_{side}"]
            ss, _ = F.to_frame(sh)
            tgt = F.to_world(ss + pose.facing * ahead[k], 3.0 + lift[k])
            self._arm_floor_safe(pose, side, tgt, F)
            pose.hands[side] = "open"

    def _eval_fall(self, seg: Segment, t: float) -> Pose:
        pose, F = self._lying_base(seg, t)
        u = clamp((t - seg.t0) / 0.62, 0.0, 1.0)
        L = pose.local
        set_lean(L, 0.15 * u, chest=-0.1, head=-0.5 * u)
        L["thigh_n"], L["shin_n"] = -PI / 2 + 0.25 - 0.2 * u, -0.5 + 0.4 * u
        L["thigh_f"], L["shin_f"] = -PI / 2 - 0.15, -0.15
        pose.eye = 1.0 + 0.4 * smoothstep(0.0, 0.3, u)
        if u < 0.55:
            set_arm(L, "n", 1.2 + 0.8 * u, 0.5)
            set_arm(L, "f", 0.6 + 1.2 * u, 0.6)
        else:  # hands reach for the floor to break the fall
            w = smoothstep(0.55, 0.9, u)
            set_arm(L, "n", 1.65, 0.4)
            set_arm(L, "f", 1.3, 0.5)
            if w > 0.5:
                self._floor_hands(pose, F, (30.0, 22.0))
        self._ground_clamp(pose, F)  # toes never dig into the floor while falling
        return pose

    def _prone_limbs(self, pose: Pose, F, tau: float, struggle: float, pinned: bool, chest_up: float = 1.0) -> None:
        L = pose.local
        heave = math.sin(2 * PI * tau / (0.9 if struggle > 0.5 else 2.6))
        set_lean(L, -0.22 * chest_up - 0.06 * heave * struggle, chest=-0.12 * chest_up, head=-0.55 * chest_up)
        kick = 0.0 if pinned else 0.35 * struggle
        L["thigh_n"] = -PI / 2 + 0.06
        L["thigh_f"] = -PI / 2 - 0.04
        L["shin_n"] = -0.08 - kick * max(0.0, math.sin(2 * PI * tau / 0.7))
        L["shin_f"] = -0.08 - kick * max(0.0, math.sin(2 * PI * tau / 0.7 + PI))
        L["foot_n"] = L["foot_f"] = PI / 2 + 0.6
        claw = struggle * math.sin(2 * PI * tau / 0.8)
        self._floor_hands(pose, F, (24.0 + 14.0 * claw, 30.0 - 14.0 * claw), (4.0 * max(0.0, claw), 4.0 * max(0.0, -claw)))
        pose.eye = 1.0 - 0.35 * struggle * (0.5 + 0.5 * heave)

    def _eval_prone(self, seg: Segment, t: float) -> Pose:
        pose, F = self._lying_base(seg, t)
        tau = t - seg.t0
        struggle = 1.0 if seg.data.get("struggle") else 0.0
        pinned = bool(seg.data.get("pinned")) or bool(seg.data.get("gaze_prop"))
        self._prone_limbs(pose, F, tau, struggle, pinned)
        # look: a dynamic target (prop / character), or back at the load now and then while struggling
        g = self._dyn_gaze(seg.data.get("gaze_ref"), t) or seg.data.get("gaze")
        if g is None and struggle and seg.data.get("gaze_prop"):
            if (tau % 2.4) > 1.4:
                g = self._dyn_gaze("prop:" + seg.data["gaze_prop"], t)
        if g is not None:
            self._gaze(pose, g, smoothstep(0.0, 0.25, tau))
        return pose

    def _eval_crawl(self, seg: Segment, t: float) -> Pose:
        pose, F = self._lying_base(seg, t)
        tau = t - seg.t0
        s = self._rec(self.S, t, seg)
        d = abs(s - seg.data["s0"])
        stride = 30.0
        L = pose.local
        set_lean(L, -0.28, chest=-0.12, head=-0.55)
        ch = self.rig.world_joints(pose)
        for k, side in enumerate("nf"):
            ph = d / stride + 0.5 * k
            n, frac = math.floor(ph), ph - math.floor(ph)
            sh_s, _ = F.to_frame(ch[f"shoulder_{side}"])
            base = seg.data["s0"] + pose.facing * (n * stride)
            lead = 34.0
            plant = base + pose.facing * (lead + 14.0)
            if frac < 0.35:  # reach forward to the next hand plant
                w = smoothstep(0.0, 0.35, frac)
                prev = base + pose.facing * (lead + 14.0 - stride)
                tgt_s, lift = lerp(prev, plant, w), 9.0 * math.sin(PI * w)
            else:
                tgt_s, lift = plant, 0.0
            tgt_s = sh_s + clamp(tgt_s - sh_s, -10.0, 52.0) if pose.facing > 0 else sh_s - clamp(sh_s - tgt_s, -10.0, 52.0)
            self._arm_floor_safe(pose, side, F.to_world(tgt_s, 3.0 + lift), F)
            pose.hands[side] = "open"
            knee = max(0.0, math.sin(2 * PI * (ph + 0.25)))
            L[f"thigh_{side}"] = -PI / 2 + 0.15 * knee
            L[f"shin_{side}"] = -0.15 - 1.1 * knee
            L[f"foot_{side}"] = PI / 2 + 0.5
        pose.eye = 0.85
        return pose

    def _eval_getup(self, seg: Segment, t: float) -> Pose:
        if seg.data.get("back"):
            return self._eval_getup_back(seg, t)
        pose, F = self._lying_base(seg, t)
        f = pose.facing
        tilt = abs(math.atan2(math.sin(pose.body_angle - F.body_angle), math.cos(pose.body_angle - F.body_angle)))
        s, h = F.to_frame(pose.root)
        u = 1.0 - tilt / (PI / 2)  # 0 prone -> 1 upright
        L = pose.local
        set_lean(L, -0.2 * (1 - u) + 0.15 * math.sin(PI * u), chest=-0.1 * (1 - u), head=-0.4 * (1 - u))
        legu = self.p.thigh + self.p.shin
        if tilt > 1.05:  # push-up: the legs stay on the floor behind (IK to ankle points along the floor)
            reach = 0.97 * legu
            back = math.sqrt(max(1.0, reach * reach - max(0.0, h - self.p.ankle_height) ** 2))
            for k, side in enumerate("nf"):
                self.rig.leg_ik(pose, side, F.to_world(s - f * (back - 3.0 * k), self.p.ankle_height + 1.0), None)
            self._knees_above_floor(pose, F, max_raise=8.0)
            self._ground_clamp(pose, F)
        elif h < 0.8 * legu:  # on the knees: knees on the floor, shins behind
            for k, side in enumerate("nf"):
                lunge = side == "n" and h > 0.6 * legu
                if lunge:
                    ank = F.to_world(s + f * 0.42 * legu, self.p.ankle_height)
                else:
                    ank = F.to_world(s - f * (self.p.shin * 0.92 - 4.0 * k), self.p.ankle_height + 1.0)
                self.rig.leg_ik(pose, side, ank, None)
        else:
            u2 = smoothstep(0.8 * legu, self.stand_h, h)
            front = F.to_world(s + f * lerp(0.42 * legu, 9.0, u2), self.p.ankle_height)
            rear = F.to_world(s - f * lerp(self.p.shin * 0.9, 9.0, u2), self.p.ankle_height)
            self.rig.leg_ik(pose, "n", front, 0.0)
            self.rig.leg_ik(pose, "f", rear, 0.0)
        if tilt <= 1.05:  # kneeling / rising: knees and toes stay above the floor
            self._knees_above_floor(pose, F)
            self._ground_clamp(pose, F)
        helper = seg.data.get("helper")
        grab_t = seg.data.get("grab_t")
        if tilt > 0.75:  # push-up: hands on the floor under the shoulders
            self._floor_hands(pose, F, (8.0, 4.0))
        elif helper:  # reach up for the helping hand, then hold it
            g = self._link_point(helper, t)
            if grab_t is None or t < grab_t:
                reach = smoothstep(0.75, 0.3, tilt)
                ch = self.rig.world_joints(pose)
                sh = ch["shoulder_n"]
                tgt = (lerp(sh[0], g[0], reach), lerp(sh[1] + 10, g[1], reach))
            else:
                tgt = self._held_grip(helper, g, t, grab_t)
            self.rig.arm_ik(pose, "n", tgt, fingertip=True)
            pose.hands["n"] = "fist"
            set_arm(L, "f", 0.25, 0.6)
        else:  # hand on the front knee to push up
            j = self.rig.world_joints(pose)
            self.rig.arm_ik(pose, "n", j["knee_n"], fingertip=False)
            set_arm(L, "f", 0.2, 0.5)
        pose.eye = 0.9
        return pose

    def _limbs_above_floor(self, pose: Pose, F) -> None:
        """A body on the floor: no hand, elbow or knee may sink into the surface. A hand below it is placed on it
        (elbow kept above), and knees are lifted by re-solving the legs."""
        j = self.rig.world_joints(pose)
        for side in "nf":
            hs, hh = F.to_frame(j[f"hand_{side}"])
            es, eh = F.to_frame(j[f"elbow_{side}"])
            if hh < 1.0 or eh < 1.0:
                self._arm_floor_safe(pose, side, F.to_world(hs, 2.0), F)
                pose.hands[side] = "open"
        j = self.rig.world_joints(pose)
        if pose.state in ("ragdoll", "prone", "supine") and min(F.to_frame(j["knee_n"])[1], F.to_frame(j["knee_f"])[1]) < 1.0:
            # a body at rest: knees (and toes) never under the floor (getting-up poses solve their own legs)
            self._knees_above_floor(pose, F, max_raise=40.0)

    def _knees_above_floor(self, pose: Pose, F, max_raise: float = 1e9) -> None:
        """Joint-level collision for kneeling: knees may rest on the floor, never sink into it. Raise the pelvis by the
        deficit and re-solve the legs toward the same ankle positions."""
        from .animator import KNEE_CLEARANCE
        for _ in range(4):
            j = self.rig.world_joints(pose)
            low = min(F.to_frame(j["knee_n"])[1], F.to_frame(j["knee_f"])[1], F.to_frame(j["toe_n"])[1] + 1.0,
                      F.to_frame(j["toe_f"])[1] + 1.0)
            if low >= KNEE_CLEARANCE - 0.05:
                return
            ank = {sd: j[f"ankle_{sd}"] for sd in "nf"}
            nx, ny = F.normal
            dh = min((KNEE_CLEARANCE - low) * 1.15, max_raise)
            max_raise -= dh
            if dh <= 1e-6:
                return
            pose.root = (pose.root[0] + nx * dh, pose.root[1] + ny * dh)
            for sd in "nf":
                sa, ha = F.to_frame(ank[sd])
                self.rig.leg_ik(pose, sd, F.to_world(sa, max(ha, self.p.ankle_height)), None)

    # ------------------------------------------------------------ lift by hand
    def _eval_lift(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        dur = seg.data.get("dur", 2.4)
        down = smoothstep(0.0, 0.45, tau) * (1 - smoothstep(dur - 0.4, dur, tau))
        strain = smoothstep(0.45, 1.05, tau) * (1 - smoothstep(dur - 0.45, dur - 0.2, tau))
        trem = math.sin(2 * PI * 8.5 * tau) * strain
        pose, F, s = self._stand_pose(seg, t, crouch=48.0 * down - 10.0 * strain + 1.2 * trem, lean=0.5 * down - 0.22 * strain,
                                      chest=-0.18 * strain, head=-0.35 * strain)
        pose.eye = 1.0 - 0.55 * strain
        self._stand_legs(pose, F, seg, t)
        if down > 0.25:
            g = self._prop_world(seg.data["prop"], t, seg.data["grip_local"])
            tan = F.tangent
            self._hands_to(pose, [("n", (g[0] + tan[0] * 5, g[1] - 2)), ("f", (g[0] - tan[0] * 9, g[1] - 2))], shape="fist")
        else:  # after letting go: shake the hands out
            set_arm(pose.local, "n", 0.4 + 0.2 * math.sin(2 * PI * 4 * tau), 1.2)
            set_arm(pose.local, "f", 0.2 - 0.2 * math.sin(2 * PI * 4 * tau), 1.4)
        g = self._dyn_gaze("prop:" + seg.data["prop"], t)
        self._gaze(pose, g, 0.6)
        return pose

    # ------------------------------------------------------------ lever: pick up, carry, place, press, hold, release
    def _bar_grips(self, bar: str, t: float, mode: str) -> Tuple[Vec, Vec]:
        L = self.prop_specs[bar].size[0]
        if mode == "carry":
            return self._prop_world(bar, t, (12.0, 0.0)), self._prop_world(bar, t, (-12.0, 0.0))
        return self._prop_world(bar, t, (L / 2 - 6.0, 0.0)), self._prop_world(bar, t, (L / 2 - 24.0, 0.0))

    def _eval_lever(self, seg: Segment, t: float) -> Pose:
        ph = seg.data.get("phase", "pickup")
        tau = t - seg.data.get("t_phase", seg.t0)
        bar = seg.data["bar"]
        if ph == "pickup":
            down = math.sin(PI * clamp(tau / 0.8, 0, 1))
            pose, F, s = self._stand_pose(seg, t, crouch=46.0 * down, lean=0.15 + 0.55 * down, head=0.2 * down)
            self._stand_legs(pose, F, seg, t)
            if tau > 0.25:
                a, b = self._bar_grips(bar, t, "carry")
                self._hands_to(pose, [("n", a), ("f", b)])
        elif ph == "place":
            u = clamp(tau / 0.75, 0, 1)
            pose, F, s = self._stand_pose(seg, t, crouch=26.0 * math.sin(PI * u), lean=0.25 + 0.3 * math.sin(PI * u))
            self._stand_legs(pose, F, seg, t)
            a, b = self._bar_grips(bar, t, "carry" if u < 0.5 else "handle")
            self._hands_to(pose, [("n", a), ("f", b)])
        else:
            F = self.frames[seg.frame]
            a, b = self._bar_grips(bar, t, "handle")
            hh = F.to_frame(a)[1]
            press = smoothstep(0.0, 0.4, tau) if ph == "press" else (1.0 if ph == "hold" else 1 - smoothstep(0.0, 0.4, tau))
            # bring the shoulders over the handle: lower the pelvis as the handle goes down
            reach_h = hh + 0.55 * self.shoulder_up_rest
            crouch = clamp(self.stand_h - 2.0 - (reach_h - 6.0), 0.0, 60.0) * press
            trem = math.sin(2 * PI * 9.0 * tau) * press
            pose, F, s = self._stand_pose(seg, t, crouch=crouch + 0.8 * trem, lean=0.25 + 0.4 * press, head=0.1)
            pose.eye = 1.0 - 0.4 * press
            self._stand_legs(pose, F, seg, t)
            if ph != "release" or tau < 0.2:
                self._hands_to(pose, [("n", a), ("f", b)])
        g = self._dyn_gaze("prop:" + seg.data["load"], t)
        self._gaze(pose, g, 0.5)
        return pose

    # ------------------------------------------------------------ helping hand, gestures
    def _eval_offer(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        pull = smoothstep(0.0, 0.5, t - seg.data["pull_t"]) if seg.data.get("pull_t") else 0.0
        pose, F, s = self._stand_pose(seg, t, crouch=10.0 + 8.0 * pull, lean=0.3 - 0.45 * pull, chest=0.05, head=0.15 - 0.2 * pull)
        self._stand_legs(pose, F, seg, t)
        g = self._link_point(seg.data["other"], t)
        ch = self.rig.world_joints(pose)
        sh = ch["shoulder_n"]
        reach = smoothstep(0.0, 0.5, tau)
        o = self.others[seg.data["other"]]
        if not getattr(self, "_no_grip", False) and not getattr(o, "_no_grip", False):
            o._no_grip = True  # reach for where the other's hand really is (its pose does not depend on ours here)
            try:
                g = o.rig.world_joints(o.pose_at(t))["hand_n"]
            finally:
                o._no_grip = False
        tgt = (lerp(sh[0], g[0], reach), lerp(sh[1] - 20, g[1], reach))
        if seg.data.get("pull_t") is not None and t >= seg.data["pull_t"]:
            tgt = self._held_grip(seg.data["other"], tgt, t, seg.data["pull_t"])
        self.rig.arm_ik(pose, "n", tgt, fingertip=True)
        pose.hands["n"] = "open" if pull == 0 else "fist"
        set_arm(pose.local, "f", -0.2 - 0.3 * pull, 0.5)
        self._gaze(pose, self._dyn_gaze("char:" + seg.data["other"], t), 0.8)
        return pose

    def _eval_rescue(self, seg: Segment, t: float) -> Pose:
        """Kneel at the edge, reach down, catch the hanging character's hand, lean back and pull (Milestone 6)."""
        d = seg.data
        tau = t - seg.t0
        k, r, p = d["times"]
        kneel = smoothstep(0.0, k, tau)
        pull = smoothstep(r, p, tau)
        rise = smoothstep(r + 0.35 * (p - r), p + 0.3, tau)
        crouch = 0.6 * self.stand_h * kneel * (1.0 - 0.8 * rise)
        lean = 1.05 * kneel * (1.0 - pull) - 0.22 * pull * (1.0 - smoothstep(p, p + 0.4, tau))
        pose, F, s = self._stand_pose(seg, t, crouch=crouch, lean=lean, head=0.45 * kneel * (1.0 - pull))
        if "settle_steps" not in d and "plants" in d:  # two steps back with the pull (the body moves back as it pulls)
            from .rescue import STEP_BACK, STEP_WIN
            sh = d["dc"] * STEP_BACK * self.stand_h
            a0 = seg.t0 + r + STEP_WIN[0] * (p - r)
            mid = seg.t0 + r + 0.5 * (STEP_WIN[0] + STEP_WIN[1]) * (p - r)
            b0 = seg.t0 + r + STEP_WIN[1] * (p - r)
            back = 0 if (d["plants"][0] - d["plants"][1]) * d["dc"] > 0 else 1  # the foot nearer the move goes first
            d["settle_steps"] = [(back, a0, mid, d["plants"][back], d["plants"][back] + sh),
                                 (1 - back, mid, b0, d["plants"][1 - back], d["plants"][1 - back] + sh)]
        self._stand_legs(pose, F, seg, t)
        L = pose.local
        set_arm(L, "f", -0.6 * kneel + 0.4 * pull, 1.2)  # the far arm braces back for balance
        from .rescue import HOLD_T, grip_point
        reach = smoothstep(k * 0.6, r, tau) * (1.0 - smoothstep(r + HOLD_T, r + HOLD_T + 0.3, tau))
        if reach > 0:
            if tau < r:
                tgt = d["M"]
            elif getattr(self, "_no_grip", False):
                tgt = d["M"]
            else:  # holding on: the two hands share one grip point as the other comes up
                w = smoothstep(r, r + 0.12, tau)
                G = grip_point(self, self.others[d["other"]], t)
                tgt = (lerp(d["M"][0], G[0], w), lerp(d["M"][1], G[1], w))
            keep = {k_: L[k_] for k_ in ("upper_arm_n", "forearm_n", "hand_n")}
            self.rig.arm_ik(pose, "n", tgt, fingertip=True)
            for k_, v in keep.items():
                L[k_] = lerp_angle(v, L[k_], reach)
            pose.hands["n"] = "fist" if tau >= r else "open"
            if pull > 0.05:  # both hands on the pull
                keep = {k_: L[k_] for k_ in ("upper_arm_f", "forearm_f", "hand_f")}
                self.rig.arm_ik(pose, "f", (tgt[0], tgt[1] + 6.0))
                for k_, v in keep.items():
                    L[k_] = lerp_angle(v, L[k_], pull * reach)
                pose.hands["f"] = "fist"
        pose.eye = 1.2 + 0.5 * smoothstep(r - 0.15, r, tau) * (1 - pull)
        self._gaze(pose, d["M"] if tau < p else (d["E"][0] - d["dc"] * 40.0, d["E"][1] + 100.0), 0.9)
        return pose

    def _eval_gesture(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        kind = seg.data["gesture"]
        other = seg.data["other"]
        pose, F, s = self._stand_pose(seg, t, crouch=2.0, lean=0.06)
        self._stand_legs(pose, F, seg, t)
        out = smoothstep(0.15, GESTURE_CONTACT, tau) * (1 - smoothstep(GESTURE_CONTACT + 0.45, GESTURE_CONTACT + 0.85, tau))
        ch = self.rig.world_joints(pose)
        sh = ch["shoulder_n"]
        if kind == "fist_bump":
            g = self._link_point(other, t)
            g = (g[0], g[1] + 0.25 * self.stand_h)
            self.rig.arm_ik(pose, "n", (lerp(sh[0], g[0], out), lerp(sh[1] - 25, g[1], out)), fingertip=False)
            pose.hands["n"] = "fist"
        elif kind == "shoulder_pat":
            g = self._shoulder_of(other, t)
            pat = 3.0 * math.sin(2 * PI * 3.0 * max(0.0, tau - GESTURE_CONTACT)) * out
            self.rig.arm_ik(pose, "n", (lerp(sh[0], g[0], out), lerp(sh[1] - 25, g[1] + 4 + pat, out)), fingertip=True)
            pose.hands["n"] = "open"
        elif kind == "nudge":  # a playful elbow into the other's side: lean in, bump, rock back grinning
            g = self._shoulder_of(other, t)
            bump = math.sin(PI * clamp((tau - 0.25) / 0.5, 0.0, 1.0))
            set_lean(pose.local, 0.06 + 0.22 * bump, chest=-0.05)
            pose.hip_twist = 0.5 * bump
            pose.twist = -0.4 * bump
            self.rig.arm_ik(pose, "n", (lerp(sh[0], g[0] - 4 * math.copysign(1, g[0] - sh[0]), out * 0.8), lerp(sh[1] - 30, g[1] - 22, out)),
                            fingertip=False)
            pose.hands["n"] = "fist"
            pose.eye = 1.25
        else:  # wave
            set_arm(pose.local, "n", 2.6 * out, 0.4 + 0.5 * math.sin(2 * PI * 2.5 * tau) * out)
            pose.hands["n"] = "open"
        pose.eye = 1.0 + 0.15 * out
        self._gaze(pose, self._dyn_gaze("char:" + other, t), 0.9)
        return pose
