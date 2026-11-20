"""Animator: converts the recorded simulation (segments + per-step records) into poses at ANY time t.

Pose evaluation is a pure function of t (no hidden state), which gives arbitrary-timestamp evaluation,
deterministic re-rendering and lets QA sample the motion at any rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.mathx import clamp, lerp, lerp_angle, smoothstep
from ..core.timeline import Track
from ..rig.stickman import PI, Pose, StickmanRig, base_pose, blend_poses, set_arm, set_lean
from ..scene.schema import CharacterStyle
from .controller import PRESS_CONTACT_T, TURN_DURATION, Event, Segment, StepRecord
from .frames import GroundFrame
from .gait import Gait, GaitParams

BLEND_IN = {"airborne": 0.12, "landing": 0.12, "loco": 0.14, "idle": 0.16, "press": 0.14, "turn": 0.06}

# press action: hand target offsets relative to the button (ds toward the character, dh above), IK weight, body
PRESS = {
    "ik": Track.of((0.0, 0.0), (0.18, 0.0), (0.42, 1.0), (0.95, 1.0), (1.08, 0.0)),
    "ds": Track.of((0.18, 34.0), (0.45, 30.0), (0.62, 8.0), (0.72, 10.0, "in"), (PRESS_CONTACT_T, 0.0), (0.95, 0.0)),
    "dh": Track.of((0.18, 46.0), (0.45, 40.0), (0.62, 20.0), (0.72, 26.0, "in"), (PRESS_CONTACT_T, 0.0), (0.86, -3.0), (0.95, -3.0)),
    "lean": Track.of((0.0, 0.08), (0.2, -0.05), (0.45, 0.42), (0.72, 0.5), (PRESS_CONTACT_T, 0.62), (0.95, 0.6), (1.06, -0.32), (1.25, 0.05), (1.45, 0.18), (1.75, 0.12)),
    "crouch": Track.of((0.0, 0.0), (0.2, 2.0), (0.6, 14.0), (PRESS_CONTACT_T, 18.0), (0.95, 17.0), (1.06, -4.0), (1.3, 8.0), (1.75, 6.0)),
    "head": Track.of((0.0, 0.0), (0.4, 0.35), (0.8, 0.45), (0.95, 0.45), (1.06, -0.5), (1.25, -0.2), (1.45, -0.45), (1.75, 0.0)),
    "eye": Track.of((0.0, 1.0), (0.6, 1.1), (0.95, 1.0), (1.02, 1.8), (1.4, 1.4), (1.75, 1.25)),
    "sy": Track.of((0.95, 1.0), (1.04, 1.08), (1.14, 0.96), (1.24, 1.0)),
    "armN": Track.of((0.95, 0.0), (1.05, 2.7), (1.25, 1.2), (1.75, 0.9)),
    "armF": Track.of((0.0, 0.9), (0.4, 1.0), (0.95, 1.0), (1.05, 2.5), (1.25, 1.0), (1.75, 0.8)),
    "elbF": Track.of((0.0, 2.0), (0.4, 2.3), (0.95, 2.3), (1.05, 0.6), (1.25, 1.4), (1.75, 1.6)),
    "look": Track.of((1.3, 1.0), (1.42, -1.0, "hold"), (1.62, -1.0), (1.7, 1.0)),
}


@dataclass
class PlantedInterval:
    t0: float
    t1: float
    leg: str
    point: Tuple[float, float]
    reason: str


class Animator:
    def __init__(self, cid: str, rig: StickmanRig, style: CharacterStyle, segments: List[Segment], records: List[StepRecord],
                 frames: Dict[str, GroundFrame], events: List[Event]):
        self.cid, self.rig, self.style = cid, rig, style
        self.p = rig.p
        self.segments, self.frames = segments, frames
        self.stand_h = rig.p.stand_height
        self.T = np.array([r.t for r in records])
        self.PX = np.array([r.pos[0] for r in records])
        self.PY = np.array([r.pos[1] for r in records])
        self.ANG = np.unwrap(np.array([r.angle for r in records]))
        self.S = np.array([r.s for r in records])
        self.H = np.array([r.h for r in records])
        self.BR = np.array([r.brace for r in records])
        self.VX = np.array([r.vel[0] for r in records])
        self.VY = np.array([r.vel[1] for r in records])
        self.gait_params = GaitParams(cadence_scale=style.cadence_scale, stride_scale=style.stride_scale,
                                      leg_length=rig.p.thigh + rig.p.shin)
        self.footsteps: List[Event] = []
        self._prepare()

    # ------------------------------------------------------------ post-processing (plants, gaits)
    def _rec(self, arr: np.ndarray, t: float, seg: Optional[Segment] = None) -> float:
        if seg is not None:
            t = clamp(t, seg.t0, seg.t1)
        return float(np.interp(t, self.T, arr))

    def _prepare(self) -> None:
        plants: Optional[Tuple[float, float]] = None
        for seg in self.segments:
            F = self.frames[seg.frame]
            f = seg.facing
            if seg.kind == "airborne":
                plants = None
                continue
            if seg.kind == "landing":
                # feet stay exactly where they touched the surface (projected onto it)
                s0 = seg.data["s0"]
                prev = self.segments[self.segments.index(seg) - 1]
                j = self.rig.world_joints(self._eval(prev, seg.t0))
                ps = []
                for side, default in (("n", s0 + 12.0 * f), ("f", s0 - 10.0 * f)):
                    sa, _ = F.to_frame(j[f"ankle_{side}"])
                    ps.append(clamp(sa, s0 - 24.0, s0 + 24.0) if math.isfinite(sa) else default)
                if abs(ps[0] - ps[1]) < 10.0:  # keep a stable stance width
                    mid = (ps[0] + ps[1]) / 2
                    ps = [mid + 6.0 * f, mid - 6.0 * f]
                plants = (ps[0], ps[1])
                seg.data["plants"] = plants
                continue
            if plants is None:
                s0 = self._rec(self.S, seg.t0, seg)
                if seg.data.get("landing"):
                    plants = (s0 + 18.0 * f, s0 - 6.0 * f)
                else:
                    plants = (s0 + 9.0 * f, s0 - 9.0 * f)
            if seg.kind == "loco":
                m = (self.T >= seg.t0 - 1e-9) & (self.T <= seg.t1 + 1e-9)
                ts, ss = self.T[m], self.S[m]
                if len(ts) < 3:
                    seg.data["plants"] = plants
                    continue
                vs = np.gradient(ss, ts)
                direction = 1.0 if (ss[-1] - ss[0]) >= 0 else -1.0
                lead = 0 if plants[0] * direction < plants[1] * direction else 1
                gait = Gait(ts, ss, vs, self.gait_params, direction, plants, lead_leg=lead)
                seg.data["gait"] = gait
                seg.data["plants_in"] = plants
                for ff in gait.footfalls:
                    if ff.t > seg.t0 + 1e-6:
                        self.footsteps.append(Event(ff.t, "footstep", self.cid, {"surface": seg.frame, "leg": "nf"[ff.leg],
                                                                                 "speed": abs(gait.speed(ff.t))}))
                plants = gait.final_plants()
                seg.data["plants"] = plants
            else:
                seg.data["plants"] = plants
                if seg.kind == "idle" and not seg.data.get("settle"):
                    plants = self._settle(seg, F, plants)

    def _settle(self, seg: Segment, F: GroundFrame, plants: Tuple[float, float]) -> Tuple[float, float]:
        """After stopping, step any foot that ended far from the pelvis back under the body (balance correction)."""
        s = self._rec(self.S, seg.t0, seg)
        f = seg.facing
        want = (s + 9.0 * f, s - 9.0 * f)
        steps, t = [], seg.t0 + 0.04
        order = sorted((0, 1), key=lambda k: -abs(plants[k] - want[k]))
        cur = list(plants)
        for k in order:
            if abs(cur[k] - want[k]) > 14.0:
                steps.append((k, t, t + 0.26, cur[k], want[k]))
                cur[k] = want[k]
                t += 0.2
        seg.data["settle_steps"] = steps
        seg.data["plants_final"] = tuple(cur)
        return tuple(cur)

    def _settle_feet(self, seg: Segment, t: float) -> Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]]:
        plants = list(seg.data["plants"])
        lift, ang = [0.0, 0.0], [0.0, 0.0]
        for (k, a, b, s0, s1) in seg.data.get("settle_steps", []):
            if t >= b:
                plants[k] = s1
            elif t > a:
                u = (t - a) / (b - a)
                e = u * u * (3 - 2 * u)
                plants[k] = s0 + (s1 - s0) * e
                lift[k] = 10.0 * math.sin(math.pi * u)
                ang[k] = -0.35 * math.sin(math.pi * u)
        return (plants[0], plants[1]), (lift[0], lift[1]), (ang[0], ang[1])

    # ------------------------------------------------------------ evaluation
    def segment_at(self, t: float) -> int:
        for i, s in enumerate(self.segments):
            if s.t0 <= t < s.t1:
                return i
        return len(self.segments) - 1 if t >= self.segments[-1].t0 else 0

    def pose_at(self, t: float) -> Pose:
        i = self.segment_at(t)
        seg = self.segments[i]
        pose = self._eval(seg, t)
        if i > 0:
            bl = BLEND_IN.get(seg.kind, 0.15)
            u = (t - seg.t0) / bl
            if u < 1:
                prev = self._eval(self.segments[i - 1], t)
                pose = blend_poses(prev, pose, smoothstep(0, 1, u))
        return pose

    def _legs(self, pose: Pose, F: GroundFrame, plants: Tuple[float, float], lift: Tuple[float, float] = (0.0, 0.0),
              angles: Tuple[float, float] = (0.0, 0.0)) -> None:
        # reach constraint: a planted foot must stay within leg reach; lower the hips (as real walkers do in a
        # long stride or a deep landing) instead of letting the foot drag
        sp, hp = F.to_frame(pose.root)
        reach = 0.985 * (self.p.thigh + self.p.shin) * 1.06
        for k in (0, 1):
            if lift[k] < 0.5:
                d = abs(plants[k] - sp)
                if d < reach:
                    hmax = math.sqrt(reach * reach - d * d) + self.p.ankle_height
                    hp = min(hp, hmax)
        pose.root = F.to_world(sp, hp)
        # foot pitch is authored relative to the SURFACE; convert to the (possibly tilted) character frame
        tilt = (pose.body_angle - F.body_angle) * (1.0 if pose.facing >= 0 else -1.0)
        for k, side in enumerate("nf"):
            h = lift[k] + self.p.ankle_height
            # keep the toe above the surface: foot pitch may not point the toe below h=0
            min_ang = -math.asin(clamp(h / self.p.foot, 0.0, 1.0))
            ankle = F.to_world(plants[k], h)
            self.rig.leg_ik(pose, side, ankle, max(angles[k], min_ang) - tilt)

    def _base(self, seg: Segment, t: float) -> Tuple[Pose, GroundFrame]:
        F = self.frames[seg.frame]
        pose = Pose(local=base_pose(), facing=seg.facing, state=seg.kind)
        s, h = self._rec(self.S, t, seg), self._rec(self.H, t, seg)
        pose.root = F.to_world(s, h)
        pose.body_angle = F.body_angle
        return pose, F

    def _eval(self, seg: Segment, t: float) -> Pose:
        return getattr(self, f"_eval_{seg.kind}")(seg, t)

    # -- idle (with optional look-around)
    def _eval_idle(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tau = t - seg.t0
        s = self._rec(self.S, t, seg)
        breath = math.sin(2 * PI * tau / 3.2)
        pose.root = F.to_world(s, self.stand_h - 2.0 + 1.2 * breath)
        L = pose.local
        set_lean(L, 0.03 + 0.01 * breath)
        set_arm(L, "n", 0.12 + 0.03 * breath, 0.3)
        set_arm(L, "f", -0.1 - 0.03 * breath, 0.35)
        if seg.data.get("look"):
            look = Track.of((0.0, 1.0), (0.35, 1.0), (0.55, -1.0, "hold"), (1.15, -1.0), (1.3, 1.0))
            tilt = Track.of((0.0, 0.0), (0.3, -0.35), (0.55, -0.1), (1.15, -0.15), (1.4, 0.05))
            pose.head_facing = 1.0 if look(tau) > 0 else -1.0
            L["head"] = -tilt(tau)
        if seg.data.get("settle"):
            pose.eye = lerp(1.25, 1.0, smoothstep(0, 1.2, tau))
        plants, lift, ang = self._settle_feet(seg, t)
        self._legs(pose, F, plants, lift, ang)
        return pose

    # -- turn (2D snap turn with anticipation: head leads, body follows at mid-point)
    def _eval_turn(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tau = clamp(t - seg.t0, 0, TURN_DURATION)
        mid = TURN_DURATION * 0.5
        f0, f1 = seg.data["face_from"], seg.data["face_to"]
        pose.facing = f0 if tau < mid else f1
        pose.head_facing = -1.0 if tau > mid * 0.45 and tau < mid else 1.0
        s = self._rec(self.S, t, seg)
        dip = 5.0 * math.sin(PI * tau / TURN_DURATION)
        pose.root = F.to_world(s, self.stand_h - 2.0 - dip)
        L = pose.local
        set_lean(L, 0.08 + 0.1 * math.sin(PI * tau / TURN_DURATION))
        set_arm(L, "n", 0.4 * math.sin(PI * tau / TURN_DURATION), 0.6)
        set_arm(L, "f", -0.3 * math.sin(PI * tau / TURN_DURATION), 0.6)
        self._legs(pose, F, seg.data["plants"])
        return pose

    # -- locomotion
    def _eval_loco(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        gait: Optional[Gait] = seg.data.get("gait")
        if gait is None:
            self._legs(pose, F, seg.data["plants"])
            return pose
        tc = clamp(t, seg.t0, seg.t1)
        v, acc = gait.speed(tc), gait.accel(tc)
        rb = self.gait_params.run_blend(v)
        s, h_rec = self._rec(self.S, t, seg), self._rec(self.H, t, seg)
        overlay = min(0.0, h_rec - self.stand_h)
        crouch = lerp(2.0, 9.0, rb)
        dirn = gait.dir
        lean = (lerp(0.05, 0.26, rb) + clamp(acc * dirn * 0.00028, -0.32, 0.32)) * self.style.lean_scale
        prep = seg.data.get("prep")
        arm_back = 0.0
        if prep and prep[0] <= t <= prep[1] + 0.05:
            w = math.sin(PI * clamp((t - prep[0]) / (prep[1] - prep[0] + 0.05), 0, 1))
            crouch += 20.0 * w
            lean += 0.18 * w
            arm_back = 1.2 * w
        if overlay < 0:
            lean += clamp(-overlay / 60.0, 0, 0.6)
        bob = gait.pelvis_bob(tc, 0.0)
        pose.root = F.to_world(s, self.stand_h - crouch + overlay + bob)
        L = pose.local
        set_lean(L, lean, chest=-0.1 * lean, head=-0.65 * lean)
        c = gait.arm_phase(tc)
        A = lerp(0.35, 1.05, rb) * self.style.arm_swing_scale
        elbow = lerp(0.35, 1.55, rb)
        set_arm(L, "n", -A * c - arm_back, elbow + 0.25 * c)
        set_arm(L, "f", A * c - arm_back, elbow - 0.25 * c)
        lifts, angs, sss = [], [], []
        for leg in (0, 1):
            fs = gait.foot(tc, leg)
            sss.append(fs.s)
            lifts.append(fs.h)
            angs.append(fs.angle)
        self._legs(pose, F, (sss[0], sss[1]), (lifts[0], lifts[1]), (angs[0], angs[1]))
        pose.eye = 1.0 + 0.12 * rb
        return pose

    # -- press a physical button (anticipation -> reach -> contact -> recoil)
    def _eval_press(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tau = clamp(t - seg.t0, 0, 1.75)
        s = self._rec(self.S, t, seg)
        pose.root = F.to_world(s, self.stand_h - 2.0 - PRESS["crouch"](tau))
        L = pose.local
        set_lean(L, PRESS["lean"](tau), chest=-0.05, head=-PRESS["head"](tau))
        pose.eye = PRESS["eye"](tau)
        sy = PRESS["sy"](tau)
        pose.squash = (1.0 / math.sqrt(sy), sy)
        pose.pivot_y = -(self.stand_h - 2.0)
        set_arm(L, "f", PRESS["armF"](tau), PRESS["elbF"](tau))
        set_arm(L, "n", PRESS["armN"](tau), 0.4)
        w = PRESS["ik"](tau)
        if w > 0:
            fk = dict(L)
            bx, bh = seg.data["button"]
            target = F.to_world(bx + PRESS["ds"](tau) * (1 if s > bx else -1), bh + PRESS["dh"](tau))
            self.rig.arm_ik(pose, "n", target, fingertip=True)
            for k in ("upper_arm_n", "forearm_n", "hand_n"):
                L[k] = lerp_angle(fk.get(k, L[k]), L[k], w)
            pose.hands["n"] = "point"
        look = PRESS["look"](tau)
        pose.head_facing = 1.0 if look > 0 else -1.0
        self._legs(pose, F, seg.data["plants"])
        return pose

    # -- airborne (falling / tumbling / jump) with brace toward the predicted surface
    def _eval_airborne(self, seg: Segment, t: float) -> Pose:
        tc = clamp(t, seg.t0, seg.t1)
        pose = Pose(local=base_pose(), facing=seg.facing, state="airborne")
        pose.root = (self._rec(self.PX, tc), self._rec(self.PY, tc))
        pose.body_angle = self._rec(self.ANG, tc)
        tau = tc - seg.t0
        b = self._rec(self.BR, tc)
        L = pose.local
        if seg.data.get("intent") == "jump":
            tuck = smoothstep(0.0, 0.2, tau) * (1 - b)
            set_lean(L, 0.25 * tuck + 0.1, head=-0.2)
            set_arm(L, "n", lerp(0.5, 2.6, tuck) - 1.2 * b, 0.4)
            set_arm(L, "f", lerp(-0.4, 2.3, tuck) - 1.0 * b, 0.5)
            L["thigh_n"] = -PI / 2 + lerp(0.2, 1.4, tuck) + 0.35 * b
            L["shin_n"] = -lerp(0.2, 1.8, tuck) - 0.2 * b
            L["thigh_f"] = -PI / 2 + lerp(-0.4, 1.0, tuck) + 0.1 * b
            L["shin_f"] = -lerp(0.4, 1.6, tuck) - 0.15 * b
            pose.eye = 1.15
        else:
            fl = 1.0 - b
            w = 11.0
            set_lean(L, -0.25 * fl + 0.15 * b + 0.15 * math.sin(tau * 6) * fl, head=0.3 * fl - 0.35 * b)
            set_arm(L, "n", (2.3 + 0.6 * math.sin(tau * w)) * fl + 1.5 * b, 0.35 + 0.3 * abs(math.sin(tau * w + 1)) * fl)
            set_arm(L, "f", (-2.1 + 0.6 * math.sin(tau * w + 2.1)) * fl - 0.7 * b, 0.4 + 0.3 * abs(math.sin(tau * w + 3)) * fl)
            L["thigh_n"] = -PI / 2 + (0.5 + 0.55 * math.sin(tau * 9.0)) * fl + 0.15 * b
            L["shin_n"] = -(0.5 + 0.45 * abs(math.sin(tau * 9.0 + 1.2))) * fl - 0.12 * b
            L["thigh_f"] = -PI / 2 + (-0.2 + 0.55 * math.sin(tau * 9.0 + PI)) * fl - 0.1 * b
            L["shin_f"] = -(0.6 + 0.45 * abs(math.sin(tau * 9.0 + 4.3))) * fl - 0.15 * b
            pose.eye = 1.6
            pose.hands = {"n": "open", "f": "open"}
        L["foot_n"] = L["foot_f"] = PI / 2
        return pose

    # -- landing: compression, follow-through, balance wobble (feet stay planted)
    def _eval_landing(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tc = clamp(t, seg.t0, seg.t1)
        pose.body_angle = self._rec(self.ANG, tc)
        tau = tc - seg.t0
        h = self._rec(self.H, tc)
        c = clamp((self.stand_h - h) / 50.0, 0.0, 1.2)
        err = pose.body_angle - F.body_angle
        L = pose.local
        set_lean(L, 0.12 + 0.95 * c, chest=-0.15 * c, head=-0.55 * c)
        wind = clamp(abs(err) * 4.0, 0, 1)
        set_arm(L, "n", 0.5 + 1.5 * c + wind * 1.2 * math.sin(tau * 13), 0.5 + 0.4 * c)
        set_arm(L, "f", 0.3 + 1.2 * c - wind * 1.2 * math.sin(tau * 13 + 1.5), 0.6 + 0.4 * c)
        imp = smoothstep(0.0, 0.03, tau) * (1 - smoothstep(0.05, 0.16, tau))
        sy = 1.0 - 0.12 * imp
        pose.squash = (1.0 + 0.08 * imp, sy)
        pose.pivot_y = -h
        pose.eye = lerp(1.6, 1.15, smoothstep(0, 0.6, tau))
        pose.hands = {"n": "open", "f": "open"}
        self._legs(pose, F, seg.data["plants"])
        return pose

    # ------------------------------------------------------------ for QA
    def planted_intervals(self) -> List[PlantedInterval]:
        out: List[PlantedInterval] = []
        for seg in self.segments:
            F = self.frames[seg.frame]
            bl = BLEND_IN.get(seg.kind, 0.15) + 1e-3
            if seg.kind in ("idle", "turn", "press", "landing") and seg.data.get("plants"):
                a = seg.t0 + bl
                if seg.t1 - a > 0.05:
                    for k, side in enumerate("nf"):
                        steps = [st for st in seg.data.get("settle_steps", []) if st[0] == k]
                        if steps:  # planted before the corrective step (if any time remains) and after it
                            st = steps[0]
                            if st[1] - a > 0.03:
                                out.append(PlantedInterval(a, st[1], side, F.to_world(st[3], self.p.ankle_height), "pre-settle"))
                            out.append(PlantedInterval(st[2], seg.t1, side, F.to_world(st[4], self.p.ankle_height), "settled"))
                        else:
                            out.append(PlantedInterval(a, seg.t1, side, F.to_world(seg.data["plants"][k], self.p.ankle_height), seg.kind))
            elif seg.kind == "loco" and seg.data.get("gait"):
                g: Gait = seg.data["gait"]
                for k, side in enumerate("nf"):
                    for (a, b, s) in g.stance_intervals(k):
                        a = max(a, seg.t0 + bl)
                        if b - a > 0.03:
                            out.append(PlantedInterval(a, b, side, F.to_world(s, self.p.ankle_height), "stance"))
        return out
