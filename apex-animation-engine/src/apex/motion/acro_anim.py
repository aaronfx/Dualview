"""Pose evaluation for acrobatics and symbol handling (animation side of acrobatics.py).

The simulation moves the pelvis and the body angle (records); these evaluators shape the limbs:
- **roll**: curl into a ball (chin tucked, knees to the chest, hands on the shins), unroll onto the feet;
- **vault**: the near hand plants on the top, the knees tuck as the legs swing over, the other arm balances;
- **climb**: reach up, hang from the edge (both hands locked to it), pull up, a knee onto the top, stand;
- **wall run**: two steps up the wall (feet on it), arms driving up, then the push-off (airborne);
- **flip** (airborne with `flip`): a tight tuck through the rotation, opening out before the landing;
- **pick up / throw**: crouch and grip the glyph; wind it back over the shoulder, throw, follow through;
- **flying kick**: off the floor, the rear leg tucked, the kicking leg chambered then snapped onto the target;
- while carrying a glyph, both hands hold it (any pose), including a weapon swing.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

from ..core.mathx import Vec, clamp, lerp, lerp_angle, smoothstep
from ..rig.stickman import PI, Pose, base_pose, set_arm, set_lean
from .controller import Segment


class AcroAnimMixin:
    # ------------------------------------------------------------ helpers
    def _free_pose(self, seg: Segment, t: float, state: str) -> Tuple[Pose, float]:
        tc = clamp(t, seg.t0, seg.t1)
        pose = Pose(local=base_pose(), facing=seg.facing, state=state)
        pose.root = (self._rec(self.PX, tc), self._rec(self.PY, tc))
        pose.body_angle = self._rec(self.ANG, tc)
        return pose, tc

    def _floor_legs(self, pose: Pose, F, w: float, spread: float = 9.0) -> None:
        """Blend the legs toward feet planted on surface F under the pelvis (weight w)."""
        if w <= 0.0:
            return
        keep = {k: pose.local[k] for k in ("thigh_n", "shin_n", "foot_n", "thigh_f", "shin_f", "foot_f")}
        s, _ = F.to_frame(pose.root)
        f = pose.facing
        for k, side in enumerate("nf"):
            self.rig.leg_ik(pose, side, F.to_world(s + f * (spread if k == 0 else -spread), self.p.ankle_height), 0.0, max_stretch=1.02)
        for k, v in keep.items():
            pose.local[k] = lerp_angle(v, pose.local[k], w)

    def _lift_clear(self, pose: Pose, F, margin: float = 1.0) -> None:
        """Raise the body (along the surface normal) so that no joint passes through surface F."""
        j = self.rig.world_joints(pose)
        low = min(F.to_frame(p)[1] for k, p in j.items())
        if low < margin:
            n = F.normal
            pose.root = (pose.root[0] + n[0] * (margin - low), pose.root[1] + n[1] * (margin - low))

    def _tuck(self, L: Dict[str, float], w: float) -> None:
        L["thigh_n"] = -PI / 2 + lerp(0.1, 2.35, w)
        L["shin_n"] = -lerp(0.1, 2.45, w)
        L["thigh_f"] = -PI / 2 + lerp(-0.05, 2.15, w)
        L["shin_f"] = -lerp(0.1, 2.35, w)
        L["foot_n"] = L["foot_f"] = PI / 2

    def _hands_on_shins(self, pose: Pose, w: float) -> None:
        """Hands travel (in position space, never whipping round through joint angles) from where the arms are to
        the shins as the tuck closes."""
        if w <= 0.2:
            return
        k = smoothstep(0.2, 0.85, w)
        j = self.rig.world_joints(pose)
        for side in "nf":
            kn, an, wr = j[f"knee_{side}"], j[f"ankle_{side}"], j[f"wrist_{side}"]
            tgt = ((kn[0] + an[0]) / 2, (kn[1] + an[1]) / 2)
            self.rig.arm_ik(pose, side, (wr[0] + (tgt[0] - wr[0]) * k, wr[1] + (tgt[1] - wr[1]) * k))
            pose.hands[side] = "fist"

    def _glyph_grips(self, pid: str, t: float) -> Tuple[Vec, Vec]:
        sp = self.prop_specs[pid]
        gx = -sp.size[0] / 2 + (sp.weight or 8.0)
        return self._prop_world(pid, t, (gx, 0.0)), self._prop_world(pid, t, (gx + 16.0, 0.0))

    def _carried_at(self, t: float):
        for pid, t0, t1 in getattr(self, "carry_spans", []):
            if t0 <= t < t1:
                return pid
        return None

    def _hold_carried(self, pose: Pose, t: float) -> None:
        """While carrying a glyph both hands hold it, whatever the body is doing."""
        if not self.prop_at or pose.state in ("throw",):
            return
        pid = self._carried_at(t)
        if pid is None or self.prop_specs[pid].kind != "glyph":
            return
        a, b = self._glyph_grips(pid, t)
        self.rig.arm_ik(pose, "n", a, fingertip=False)
        self.rig.arm_ik(pose, "f", b, fingertip=False)
        pose.hands["n"] = pose.hands["f"] = "fist"

    # ------------------------------------------------------------ roll
    def _eval_roll(self, seg: Segment, t: float) -> Pose:
        pose, tc = self._free_pose(seg, t, "roll")
        d = seg.data
        u = clamp((tc - seg.t0) / d["T"], 0.0, 1.0)
        w = smoothstep(0.0, 0.16, u) * (1.0 - smoothstep(0.84, 1.0, u))
        L = pose.local
        set_lean(L, lerp(0.25, 0.95, w), chest=0.3 * w, head=0.65 * w)
        self._tuck(L, w)
        set_arm(L, "n", lerp(1.1, 1.2, w), 0.6)
        set_arm(L, "f", lerp(0.9, 1.1, w), 0.7)
        self._floor_legs(pose, self.frames[seg.frame], 1.0 - smoothstep(0.0, 0.12, u) if u < 0.5 else smoothstep(0.86, 1.0, u))
        self._hands_on_shins(pose, w)
        self._lift_clear(pose, self.frames[seg.frame])
        pose.eye = 0.6 + 0.4 * (1 - w)
        return pose

    # ------------------------------------------------------------ vault
    def _eval_vault(self, seg: Segment, t: float) -> Pose:
        pose, tc = self._free_pose(seg, t, "vault")
        d = seg.data
        u = clamp((tc - seg.t0) / d["T"], 0.0, 1.0)
        L = pose.local
        w = math.sin(PI * clamp((u - 0.12) / 0.78, 0.0, 1.0))
        set_lean(L, 0.15 + 0.1 * w, chest=0.05, head=-0.25)
        L["thigh_n"] = -PI / 2 + lerp(0.2, 1.95, w)
        L["shin_n"] = -lerp(0.2, 2.0, w)
        L["thigh_f"] = -PI / 2 + lerp(-0.2, 1.6, w)
        L["shin_f"] = -lerp(0.3, 1.9, w)
        L["foot_n"] = L["foot_f"] = PI / 2
        set_arm(L, "n", 1.0, 0.3)
        set_arm(L, "f", lerp(0.4, 2.0, w), 0.45)
        F = self.frames[seg.frame]
        self._floor_legs(pose, F, 1.0 - smoothstep(0.0, 0.12, u) if u < 0.5 else smoothstep(0.9, 1.0, u) * 0.6)
        hw = smoothstep(0.1, 0.22, u) * (1.0 - smoothstep(0.56, 0.7, u))
        if hw > 0:
            keep = {k: L[k] for k in ("upper_arm_n", "forearm_n", "hand_n")}
            self.rig.arm_ik(pose, "n", d["plant"], fingertip=True)
            for k, v in keep.items():
                L[k] = lerp_angle(v, L[k], hw)
            pose.hands["n"] = "open"
        self._ground_clamp(pose, F)
        self._gaze(pose, (d["plant"][0] + d["d"] * 120.0, d["plant"][1] - 40.0), 0.6)
        pose.eye = 1.1
        return pose

    # ------------------------------------------------------------ ledge climb
    def _eval_climb(self, seg: Segment, t: float) -> Pose:
        pose, tc = self._free_pose(seg, t, "climb")
        d = seg.data
        tau = tc - seg.t0
        t1, t2, t3, t4, t5, T = d["times"][1:]
        E = d["edge"]
        f = d["d"]
        L = pose.local
        F0, Ft = self.frames[seg.frame], self.frames[d["top_frame"]]
        set_lean(L, 0.1, head=-0.35 if tau < t4 else -0.1)
        # legs: dangle while hanging, a knee comes up onto the top, then stand
        hangw = smoothstep(t1, t2, tau) * (1 - smoothstep(t4, t5, tau))
        sway = math.sin(2 * PI * (tau - t2) / 0.9) * hangw if d.get("hang") else 0.0
        L["thigh_n"] = -PI / 2 + 0.2 + 0.1 * sway + 0.9 * smoothstep(t3, t4, tau)
        L["shin_n"] = -0.35 - 1.2 * smoothstep(t3, t4, tau)
        L["thigh_f"] = -PI / 2 + 0.05 - 0.1 * sway + 0.4 * smoothstep(t3, t4, tau)
        L["shin_f"] = -0.25 - 0.5 * smoothstep(t3, t4, tau)
        L["foot_n"] = L["foot_f"] = PI / 2
        mant = smoothstep(t4, t5, tau)
        if mant > 0:  # mantle: the near knee folds onto the top, the far leg follows
            L["thigh_n"] = lerp(L["thigh_n"], -PI / 2 + 1.9, mant)
            L["shin_n"] = lerp(L["shin_n"], -2.2, mant)
        self._floor_legs(pose, F0, 1.0 - smoothstep(t1 * 0.6, t1 + 0.12, tau))  # feet leave the floor on the jump
        self._floor_legs(pose, Ft, smoothstep(t5, T, tau))  # and land on the top
        # arms: swing back in the crouch, reach for the edge, lock on while hanging and pulling, then push on the top
        set_arm(L, "n", lerp(-0.9, 2.8, smoothstep(t1 - 0.05, t2, tau)), 0.3)
        set_arm(L, "f", lerp(-0.8, 2.7, smoothstep(t1 - 0.05, t2, tau)), 0.35)
        grip = smoothstep(t2 - 0.08, t2, tau) * (1 - smoothstep(t5, t5 + 0.12, tau))
        if grip > 0:
            for side, tgt in (("n", (E[0] + f * (18.0 * mant), E[1])), ("f", E)):
                keep = {k: L[k] for k in (f"upper_arm_{side}", f"forearm_{side}", f"hand_{side}")}
                self.rig.arm_ik(pose, side, tgt)
                for k, v in keep.items():
                    L[k] = lerp_angle(v, L[k], grip)
                pose.hands[side] = "fist" if mant < 0.5 or side == "f" else "open"
        self._ground_clamp(pose, F0)
        self._gaze(pose, E if tau < t4 else (E[0] + f * 200.0, E[1] + 60.0), 0.8)
        pose.eye = 1.05
        return pose

    # ------------------------------------------------------------ wall run (two steps up, before the push-off)
    def _eval_wall_run(self, seg: Segment, t: float) -> Pose:
        pose, tc = self._free_pose(seg, t, "wall_run")
        d = seg.data
        tau = tc - seg.t0
        t_a, t_b, t_c = d["times"]
        F = self.frames[seg.frame]
        fy = F.origin[1]
        xw, f = d["xw"], d["d"]
        L = pose.local
        set_lean(L, 0.25 - 0.3 * smoothstep(t_a, t_c, tau), head=-0.3)
        up = smoothstep(0.0, t_c, tau)
        set_arm(L, "n", lerp(-0.6, 2.7, up), 0.4)
        set_arm(L, "f", lerp(0.9, 2.5, up), 0.5)
        if tau < t_a:  # the last running strides at the wall
            ph = tau / (t_a / 2.0)
            L["thigh_n"] = -PI / 2 + 0.7 * math.sin(PI * ph)
            L["shin_n"] = -0.4 - 0.8 * max(0.0, -math.sin(PI * ph))
            L["thigh_f"] = -PI / 2 - 0.7 * math.sin(PI * ph)
            L["shin_f"] = -0.4 - 0.8 * max(0.0, math.sin(PI * ph))
            L["foot_n"] = L["foot_f"] = PI / 2
        else:
            on = "n" if tau < t_b else "f"
            off = "f" if on == "n" else "n"
            h = d["contacts"][0 if on == "n" else 1]
            self.rig.leg_ik(pose, on, (xw - f * 4.0, fy + h), 1.25, max_stretch=1.06)
            L[f"thigh_{off}"] = -PI / 2 + 1.5
            L[f"shin_{off}"] = -1.7
            L[f"foot_{off}"] = PI / 2
        self._ground_clamp(pose, F)
        pose.eye = 1.1
        return pose

    # ------------------------------------------------------------ pick up, throw
    def _eval_pick_up(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        down = math.sin(PI * clamp(tau / (seg.data["T"] * 0.9), 0.0, 1.0))
        pose, F, s = self._stand_pose(seg, t, crouch=0.42 * self.stand_h * down, lean=0.15 + 0.5 * down, head=0.25 * down)
        self._stand_legs(pose, F, seg, t)
        pid = seg.data["prop"]
        if tau > 0.18 and self.prop_at:
            a, b = self._glyph_grips(pid, t)
            w = smoothstep(0.18, 0.32, tau)
            for side, tgt in (("n", a), ("f", b)):
                keep = {k: pose.local[k] for k in (f"upper_arm_{side}", f"forearm_{side}")}
                self.rig.arm_ik(pose, side, tgt)
                for k, v in keep.items():
                    pose.local[k] = lerp_angle(v, pose.local[k], w)
                pose.hands[side] = "fist"
        self._gaze(pose, self._prop_world(pid, t, (0.0, 0.0)) if self.prop_at else None, 0.9)
        return pose

    def _eval_throw(self, seg: Segment, t: float) -> Pose:
        tau = t - seg.t0
        rel = seg.data["release"]
        back = smoothstep(0.0, rel, tau) * (1 - smoothstep(rel, rel + 0.08, tau))
        fwd = smoothstep(rel - 0.06, rel + 0.1, tau) * (1 - smoothstep(rel + 0.18, seg.data["T"], tau))
        pose, F, s = self._stand_pose(seg, t, crouch=8.0 + 10.0 * fwd, lean=0.08 - 0.28 * back + 0.45 * fwd, head=-0.1)
        self._stand_legs(pose, F, seg, t)
        pose.twist = -0.6 * back + 0.7 * fwd
        pose.hip_twist = -0.3 * back + 0.4 * fwd
        pid = seg.data["prop"]
        if tau < rel and self.prop_at:
            a, b = self._glyph_grips(pid, t)
            self._hands_to(pose, [("n", a), ("f", b)], tip=False)
        else:  # follow-through: the throwing arm ends forward and low, the other swings back
            k = smoothstep(rel, rel + 0.2, tau)
            set_arm(pose.local, "n", lerp(2.4, 1.0, k), 0.2)
            set_arm(pose.local, "f", lerp(1.8, -0.4, k), 0.5)
            pose.hands["n"] = pose.hands["f"] = "open"
        pose.eye = 0.85
        return pose

    # ------------------------------------------------------------ flying kick (a strike move)
    def _eval_flying_kick(self, seg: Segment, t: float) -> Pose:
        from .combat import AIR_T
        d = seg.data
        tau = clamp(t, seg.t0, seg.t1) - seg.t0
        ta, tc = d["t_a"], d["t_c"]
        f = seg.facing
        t_up, t_dn = AIR_T[0] * ta, AIR_T[1]
        pose, F = self._base(seg, t)
        s, h = self._rec(self.S, t, seg), self._rec(self.H, t, seg)
        load = math.sin(PI * clamp(tau / t_up, 0.0, 1.0)) if tau < t_up else 0.0
        pose.root = F.to_world(s, h - 10.0 - 18.0 * load)
        if tau < tc:
            ext = clamp((tau - t_up) / (tc - t_up), 0.0, 1.0) ** 2
        else:
            ext = 1.0 - smoothstep(tc + 0.07, tc + 0.3, tau)
        set_lean(pose.local, 0.15 - 0.45 * ext, chest=-0.05, head=-0.15)
        self._guard_arms(pose, 1.0 - 0.5 * ext)
        set_arm(pose.local, "f", lerp(0.9, -0.7, ext), 0.6)
        air = smoothstep(t_up - 0.02, t_up + 0.08, tau) * (1 - smoothstep(t_dn - 0.1, t_dn, tau))
        L = pose.local
        L["thigh_f"], L["shin_f"], L["foot_f"] = -PI / 2 + 1.5, -1.9, PI / 2
        legu = self.p.thigh + self.p.shin
        j = self.rig.world_joints(pose)
        hip = j["hip_n"]
        aim = self._target_point(d["other"], t, d["height"], f)
        dx, dy = aim[0] - hip[0], aim[1] - hip[1]
        dist = math.hypot(dx, dy)
        if dist > legu * 1.05:
            aim = (hip[0] + dx / dist * legu * 1.04, hip[1] + dy / dist * legu * 1.04)
        knee = F.to_world(F.to_frame(hip)[0] + f * 0.3 * legu, F.to_frame(hip)[1] - 0.2 * legu)
        rest = F.to_world(F.to_frame(hip)[0] + f * 0.05 * legu, F.to_frame(hip)[1] - 0.75 * legu)
        u = ext
        tgt = ((1 - u) ** 2 * rest[0] + 2 * (1 - u) * u * knee[0] + u * u * aim[0], (1 - u) ** 2 * rest[1] + 2 * (1 - u) * u * knee[1] + u * u * aim[1])
        self.rig.leg_ik(pose, "n", tgt, -0.3, max_stretch=1.1)
        self._floor_legs(pose, F, 1.0 - air, spread=12.0)
        self._ground_clamp(pose, F)
        pose.twist, pose.hip_twist = -0.15, 0.4 * ext
        pose.eye = 0.7
        return pose
