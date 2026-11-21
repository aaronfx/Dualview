"""Animator: converts the recorded simulation (segments + per-step records) into poses at ANY time t.

Pose evaluation is a pure function of t (no hidden state), which gives arbitrary-timestamp evaluation,
deterministic re-rendering and lets QA sample the motion at any rate.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.mathx import Vec, clamp, damped_spring, lerp, lerp_angle, smoothstep, v_rot, wrap_angle
from ..core.timeline import Track
from ..rig.skeleton import to_character
from ..rig.stickman import PI, Pose, StickmanRig, base_pose, blend_poses, set_arm, set_lean
from ..scene.schema import CharacterStyle
from .controller import NOTICE_DOUBLE_TAKE, PRESS_CONTACT_T, PRESS_H_CONTACT_T, SLIDE_DROP, TURN_DURATION, Event, Segment, StepRecord
from .frames import GroundFrame
from .gait import Gait, GaitParams
from .acro_anim import AcroAnimMixin
from .combat_anim import FIGHT_STANCE, CombatAnimMixin
from .interaction_anim import LYING, MOVING_STANCE, STANCE, InteractionAnimMixin
from .library import NEUTRAL, MotionClip, Performance, get_clip, landing_clip


def _ramp(t: float, a: float, b: float, blend: float) -> float:
    if t < a or t > b:
        return 0.0
    return min(1.0, (t - a) / max(blend, 1e-6), (b - t) / max(blend, 1e-6))

KNEE_CLEARANCE = 2.0  # knee may rest on a surface (kneeling) but not pass through it

BLEND_IN = {"airborne": 0.16, "landing": 0.12, "loco": 0.18, "idle": 0.2, "press": 0.18, "turn": 0.06, "point": 0.12,
            "slide": 0.1, "crouch": 0.14, "swing": 0.08, "push": 0.28, "fall": 0.06, "prone": 0.22, "crawl": 0.2, "getup": 0.12,
            "lift": 0.25, "lever": 0.22, "offer": 0.25, "gesture": 0.2,
            "strike": 0.07, "guard": 0.14, "dodge": 0.06, "hurt": 0.03, "ragdoll": 0.06, "supine": 0.3,
            "roll": 0.08, "vault": 0.08, "climb": 0.1, "wall_run": 0.06, "pick_up": 0.18, "throw": 0.12}

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


# hesitant press: reach -> hover -> doubt (pull back, head cock) -> commit -> contact -> startle
H = PRESS_H_CONTACT_T
PRESS_H = {
    "ik": Track.of((0.0, 0.0), (0.22, 0.0), (0.55, 1.0), (H + 0.42, 1.0), (H + 0.55, 0.0)),
    "ds": Track.of((0.22, 42.0), (0.6, 15.0), (0.85, 19.0), (1.02, 36.0), (1.2, 31.0), (1.36, 17.0), (H - 0.1, 11.0, "in"), (H, 0.0), (H + 0.45, 0.0)),
    "dh": Track.of((0.22, 52.0), (0.6, 21.0), (0.85, 25.0), (1.02, 42.0), (1.2, 39.0), (1.36, 25.0), (H - 0.1, 28.0, "in"), (H, 0.0), (H + 0.07, -3.0), (H + 0.45, -3.0)),
    # startle (after contact) eased over ~0.2 s: the 1C version rose 22 u in 0.08 s and read as a pop
    "lean": Track.of((0.0, 0.08), (0.25, 0.3), (0.6, 0.52), (0.85, 0.5), (1.02, 0.28), (1.2, 0.3), (H - 0.1, 0.6), (H, 0.66), (H + 0.42, 0.62), (H + 0.62, -0.3), (H + 0.8, 0.02), (H + 0.9, 0.1)),
    "crouch": Track.of((0.0, 0.0), (0.6, 14.0), (1.02, 9.0), (H - 0.1, 17.0), (H, 19.0), (H + 0.42, 18.0), (H + 0.62, -4.0), (H + 0.8, 7.0), (H + 0.9, 7.0)),
    "cock": Track.of((0.0, 0.0), (0.8, 0.0), (0.95, 0.28), (1.25, 0.25), (1.38, 0.0)),  # doubtful head tilt
    "eye": Track.of((0.0, 1.0), (0.6, 1.1), (0.9, 0.8), (1.25, 0.82), (1.4, 1.05), (H + 0.42, 1.0), (H + 0.5, 1.9), (H + 0.9, 1.45)),
    "twist": Track.of((0.0, 0.0), (0.6, 0.7), (1.02, 0.25), (H, 0.8), (H + 0.45, 0.7), (H + 0.64, -0.4), (H + 0.9, 0.0)),
    "sy": Track.of((H + 0.44, 1.0), (H + 0.58, 1.06), (H + 0.72, 0.97), (H + 0.84, 1.0)),
    "armN": Track.of((H + 0.42, 0.0), (H + 0.6, 2.5), (H + 0.78, 1.3), (H + 0.9, 1.0)),
    "armF": Track.of((0.0, 0.7), (0.6, 0.9), (0.85, 1.05), (1.3, 1.05), (H + 0.42, 0.9), (H + 0.6, 2.3), (H + 0.78, 1.1), (H + 0.9, 0.9)),
    "elbF": Track.of((0.0, 1.8), (0.6, 2.2), (0.85, 2.55), (1.3, 2.5), (H + 0.42, 2.2), (H + 0.6, 0.7), (H + 0.78, 1.4), (H + 0.9, 1.6)),
    "gaze": Track.of((0.0, 0.0), (0.18, 1.0), (H + 0.44, 1.0), (H + 0.58, 0.0)),
    "lookup": Track.of((H + 0.45, 0.0), (H + 0.66, -0.5), (H + 0.9, -0.4)),
}
# post-landing recovery: relief slump (exhale, hands on knees) then straighten up (1C review: relief was missing)
RECOVER = {
    "crouch": Track.of((0.0, 3.0), (0.32, 17.0), (0.75, 14.0), (1.15, 0.0)),
    "lean": Track.of((0.0, 0.2), (0.32, 0.72), (0.75, 0.6), (1.15, 0.05)),
    "head": Track.of((0.0, 0.1), (0.35, 0.55), (0.8, 0.45), (1.1, 0.0)),
    "knees": Track.of((0.0, 0.0), (0.28, 1.0), (0.8, 1.0), (1.05, 0.0)),
    "sy": Track.of((0.3, 1.0), (0.5, 0.955), (0.78, 1.025), (0.95, 1.0)),
    "eye": Track.of((0.0, 1.35), (0.3, 1.1), (0.36, 0.25), (0.44, 0.9), (1.2, 1.0)),
}
NOTICE = {  # double-take: glance -> look away -> snap back with a startle
    "w": Track.of((0.0, 0.0), (0.1, 0.0), (0.18, 1.0, "out"), (0.26, 1.0), (0.38, 0.0), (NOTICE_DOUBLE_TAKE - 0.04, 0.0), (NOTICE_DOUBLE_TAKE + 0.05, 1.0, "out")),
    "eye": Track.of((0.0, 1.0), (NOTICE_DOUBLE_TAKE, 1.0), (NOTICE_DOUBLE_TAKE + 0.06, 1.75), (NOTICE_DOUBLE_TAKE + 0.5, 1.3)),
    "sy": Track.of((NOTICE_DOUBLE_TAKE, 1.0), (NOTICE_DOUBLE_TAKE + 0.06, 1.06), (NOTICE_DOUBLE_TAKE + 0.16, 0.97), (NOTICE_DOUBLE_TAKE + 0.26, 1.0)),
    "lean": Track.of((0.0, 0.03), (0.3, 0.06), (NOTICE_DOUBLE_TAKE, 0.05), (NOTICE_DOUBLE_TAKE + 0.07, -0.14), (NOTICE_DOUBLE_TAKE + 0.4, 0.08)),
    "armF": Track.of((NOTICE_DOUBLE_TAKE, -0.1), (NOTICE_DOUBLE_TAKE + 0.1, 0.9), (NOTICE_DOUBLE_TAKE + 0.5, 0.7)),
    "elbF": Track.of((NOTICE_DOUBLE_TAKE, 0.35), (NOTICE_DOUBLE_TAKE + 0.1, 2.3), (NOTICE_DOUBLE_TAKE + 0.5, 2.2)),
}


@dataclass
class PlantedInterval:
    t0: float
    t1: float
    leg: str
    point: Tuple[float, float]
    reason: str


FREE = ("roll", "vault", "climb", "wall_run")  # acrobatic moves: the feet are not planted on the segment's surface


class Animator(InteractionAnimMixin, CombatAnimMixin, AcroAnimMixin):
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
        self.shift_times = [e.t for e in events if e.type == "gravity_shift"]
        self.portals: List[Tuple[float, float, float, float]] = []  # open-doorway regions (set by the runtime)
        self.FAC = np.array([r.facing for r in records])
        self.prop_at = None  # set by the runtime: prop id, t -> (x, y, angle)
        self.others: Dict[str, "Animator"] = {}
        self.prop_specs: Dict[str, object] = {}
        self.shoulder_up_rest = rig.p.spine + 0.86 * rig.p.chest
        self._prepare()
        self._follow_through()

    # ------------------------------------------------------------ post-processing (plants, gaits)
    def _rec(self, arr: np.ndarray, t: float, seg: Optional[Segment] = None) -> float:
        if seg is not None:
            t = clamp(t, seg.t0, seg.t1)
        return float(np.interp(t, self.T, arr))

    def _prepare(self) -> None:
        plants: Optional[Tuple[float, float]] = None
        u = (self.p.thigh + self.p.shin) / 86.0  # stance widths are authored for the reference leg (44 + 42); scale per rig
        for seg in self.segments:
            F = self.frames[seg.frame]
            f = seg.facing
            if seg.kind in ("airborne", "swing", "slide") + FREE or seg.kind in LYING:
                plants = None
                continue
            if seg.kind == "landing":
                # feet stay exactly where they touched the surface (projected onto it)
                s0 = seg.data["s0"]
                prev = self.segments[self.segments.index(seg) - 1]
                j = self.rig.world_joints(self._eval(prev, seg.t0))
                ps = []
                for side, default in (("n", s0 + 12.0 * u * f), ("f", s0 - 10.0 * u * f)):
                    sa, _ = F.to_frame(j[f"ankle_{side}"])
                    ps.append(clamp(sa, s0 - 24.0 * u, s0 + 24.0 * u) if math.isfinite(sa) else default)
                if abs(ps[0] - ps[1]) < 10.0 * u:  # keep a stable stance width
                    mid = (ps[0] + ps[1]) / 2
                    ps = [mid + 6.0 * u * f, mid - 6.0 * u * f]
                plants = (ps[0], ps[1])
                seg.data["plants"] = plants
                continue
            if plants is None:
                s0 = self._rec(self.S, seg.t0, seg)
                if seg.data.get("landing") or seg.data.get("from_slide"):
                    plants = (s0 + 18.0 * u * f, s0 - 6.0 * u * f)
                else:
                    plants = (s0 + 9.0 * u * f, s0 - 9.0 * u * f)
            if seg.kind == "loco":
                m = (self.T >= seg.t0 - 1e-9) & (self.T <= seg.t1 + 1e-9)
                ts, ss = self.T[m], self.S[m]
                if len(ts) < 3:
                    seg.data["plants"] = plants
                    continue
                vs = np.gradient(ss, ts)
                direction = 1.0 if (ss[-1] - ss[0]) >= 0 else -1.0
                lead = 0 if plants[0] * direction < plants[1] * direction else 1
                gp = self.gait_params
                if seg.data.get("style") == "cautious":
                    from dataclasses import replace as _rep
                    gp = _rep(gp, stride_scale=gp.stride_scale * 0.78, cadence_scale=gp.cadence_scale * 0.9)
                gait = Gait(ts, ss, vs, gp, direction, plants, lead_leg=lead)
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
                if seg.kind == "idle" and seg.data.get("fight"):
                    plants = self._settle(seg, F, plants, FIGHT_STANCE)
                elif seg.kind == "idle" and not seg.data.get("settle"):
                    plants = self._settle(seg, F, plants)
                elif seg.kind in MOVING_STANCE:  # back-steps / staggers: the feet follow the pelvis to where it ends up
                    plants = self._settle(seg, F, plants, STANCE[seg.kind], at=max(seg.t0, seg.t1 - 0.02), step=0.2)
                elif seg.kind in STANCE:  # step into a working stance (push / lift / lever / offer / gesture)
                    plants = self._settle(seg, F, plants, STANCE[seg.kind])

    def _settle(self, seg: Segment, F: GroundFrame, plants: Tuple[float, float],
                stance: Tuple[float, float] = (9.0, -9.0), at: Optional[float] = None, step: float = 0.26) -> Tuple[float, float]:
        """After stopping, step any foot that ended far from the pelvis back under the body (balance correction), or
        into a working stance (e.g. the long rear leg of a push). `at`: settle around where the pelvis is at that time
        (a back-step or a stagger moves the pelvis during the segment)."""
        s = self._rec(self.S, seg.t0 if at is None else at, seg)
        f = seg.facing
        u = (self.p.thigh + self.p.shin) / 86.0
        want = (s + stance[0] * u * f, s + stance[1] * u * f)
        steps, t = [], seg.t0 + 0.04
        order = sorted((0, 1), key=lambda k: -abs(plants[k] - want[k]))
        cur = list(plants)
        for k in order:
            if abs(cur[k] - want[k]) > 14.0:
                steps.append((k, t, t + step, cur[k], want[k]))
                cur[k] = want[k]
                t += 0.77 * step
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

    def _follow_through(self) -> None:
        """Overlapping action: root acceleration (in the body frame) drives a lagged, under-damped response that
        swings arms/head/chest opposite to the acceleration and lets them settle after stops and impacts."""
        T = self.T
        n = len(T)
        self.FX = np.zeros(n)
        self.FY = np.zeros(n)
        if n < 3:
            return
        ax, ay = np.gradient(self.VX, T), np.gradient(self.VY, T)
        c, s_ = np.cos(self.ANG), np.sin(self.ANG)
        fwd = (ax * c + ay * s_) * np.where(self.FAC >= 0, 1.0, -1.0)
        up = ax * s_ - ay * c
        up = -up  # body-up axis is (sin a, -cos a) rotated; keep +up = toward the head
        fwd = np.clip(fwd, -6000, 6000)
        up = np.clip(up, -12000, 12000)
        w, z = 11.0, 0.42
        yx = vx = yy = vy = 0.0
        for i in range(1, n):
            dt = T[i] - T[i - 1]
            vx += (w * w * (fwd[i] - yx) - 2 * z * w * vx) * dt
            yx += vx * dt
            vy += (w * w * (up[i] - yy) - 2 * z * w * vy) * dt
            yy += vy * dt
            self.FX[i], self.FY[i] = yx, yy

    def _overlap(self, pose: Pose, t: float) -> None:
        if pose.state in ("airborne", "swing", "slide") + LYING + FREE:
            return
        fx, fy = float(np.interp(t, self.T, self.FX)), float(np.interp(t, self.T, self.FY))
        da = clamp(-0.00042 * fx, -0.75, 0.75)
        dn = clamp(-0.00009 * fy, -0.6, 0.45)
        L = pose.local
        for side in "nf":
            if pose.hands.get(side) == "point":
                continue
            L[f"upper_arm_{side}"] = L.get(f"upper_arm_{side}", 0.0) + da + 0.5 * dn
            L[f"forearm_{side}"] = clamp(L.get(f"forearm_{side}", 0.3) + 0.55 * abs(da) + 0.4 * max(0.0, -dn), -0.05, 2.75)
        L["chest"] = L.get("chest", 0.0) + 0.4 * dn
        L["head"] = L.get("head", 0.0) + 0.7 * dn + 0.25 * da

    # ------------------------------------------------------------ motion library (key-pose clips)
    def _apply(self, pose: Pose, F: GroundFrame, s: float, v: Dict[str, float], grounded: bool = True) -> None:
        """Apply character-agnostic channel values (see motion/library.py) to a pose."""
        g = lambda c: v.get(c, NEUTRAL[c])
        L = pose.local
        h = (self.stand_h - 2.0) * (1.0 - g("crouch"))
        if grounded:
            pose.root = F.to_world(s + g("shift") * self.stand_h * pose.facing, h)
        set_lean(L, g("lean"), chest=g("chest"), head=g("head"))
        set_arm(L, "n", g("arm_n"), g("elbow_n"))
        set_arm(L, "f", g("arm_f"), g("elbow_f"))
        pose.twist, pose.hip_twist = g("twist"), g("hip_twist")
        pose.eye = g("eye")
        sy = g("squash")
        if abs(sy - 1.0) > 1e-4:  # mostly vertical squash (horizontal squash would slide planted feet)
            pose.squash = (1.0 + 0.3 * (1.0 - sy), sy)
            pose.pivot_y = -h if grounded else 0.0
        if not grounded:
            for leg in ("thigh_n", "thigh_f"):
                L[leg] = -PI / 2 + g(leg)
            L["shin_n"], L["shin_f"] = g("shin_n"), g("shin_f")
            L["foot_n"] = L["foot_f"] = PI / 2

    def _contacts(self, pose: Pose, F: GroundFrame, clip: MotionClip, tc: float, s_mid: float) -> List[Tuple[str, float]]:
        """Enforce a clip's declared contacts with IK (blended in position space). Returns active (effector, weight)."""
        active = []
        for c in clip.contacts:
            w = _ramp(tc, c.t0, c.t1, c.blend)
            if w <= 0.0:
                continue
            side = c.effector[-1]
            j = self.rig.world_joints(pose)
            if c.on == "surface":
                tgt, tip = F.to_world(s_mid + pose.facing * c.s * self.stand_h, c.h * self.stand_h), True
            else:
                p0 = j[c.on.split(":", 1)[1]]
                if c.toward:
                    q = j[c.toward]
                    p0 = (p0[0] + (q[0] - p0[0]) * c.frac, p0[1] + (q[1] - p0[1]) * c.frac)
                tgt, tip = p0, False
            cur = j[f"hand_{side}"] if tip else j[f"wrist_{side}"]
            self.rig.arm_ik(pose, side, (cur[0] + (tgt[0] - cur[0]) * w, cur[1] + (tgt[1] - cur[1]) * w), fingertip=tip)
            pose.hands[side] = "open"
            active.append((c.effector, w))
        return active

    # ------------------------------------------------------------ gaze
    def _gaze(self, pose: Pose, target: Optional[Vec], w: float, extra_tilt: float = 0.0) -> None:
        """Turn neck + head toward a world point (weight w). Looking behind flips the head's facing."""
        if target is None or w <= 0.0:
            pose.local["head"] = pose.local.get("head", 0.0) + extra_tilt
            return
        ch = self.rig.fk(pose)
        neck = ch["neck"][0]
        tc = to_character(target, pose.root, pose.body_angle, pose.facing if abs(pose.facing) > 1e-6 else 1.0)
        dx, dy = tc[0] - neck[0], tc[1] - neck[1]
        behind = dx < -8.0
        if behind:
            dx = -dx
        a = clamp(math.atan2(dy, dx), -1.1, 1.0)
        chest_abs = pose.local.get("spine", PI / 2) + pose.local.get("chest", 0.0)
        neck_l = 0.3 * a * (-1 if behind else 1)
        head_abs = PI / 2 + (a if not behind else -a) * 0.8
        head_l = wrap_angle(head_abs - chest_abs - neck_l)
        L = pose.local
        L["neck"] = lerp_angle(L.get("neck", 0.0), neck_l, w)
        L["head"] = lerp_angle(L.get("head", 0.0), head_l, w) + extra_tilt
        if behind and w > 0.5:
            pose.head_facing = -1.0

    def _seg_gaze(self, seg: Segment, t: float) -> Tuple[Optional[Vec], float]:
        g = self._dyn_gaze(seg.data.get("gaze_ref"), t) if seg.data.get("gaze_ref") and self.prop_at else seg.data.get("gaze")
        if g is None:
            return None, 0.0
        tau = t - seg.t0
        if seg.data.get("gaze_mode") == "notice":
            return g, NOTICE["w"](tau)
        return g, smoothstep(0.0, 0.22, tau)

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
                if seg.kind == "swing":  # the grip is a hard constraint: re-solve the arms after blending
                    for side in "nf":
                        self.rig.arm_ik(pose, side, seg.data["anchor"])
                elif seg.kind not in ("airborne",) + LYING + FREE and self.segments[i - 1].kind not in LYING + FREE:
                    # blended legs may not dip through the support surface
                    self._ground_clamp(pose, self.frames[seg.frame])
                elif seg.kind in ("getup", "crawl", "prone", "supine"):  # blending between lying poses: feet stay above the floor
                    self._ground_clamp(pose, self.frames[seg.frame])
        self._overlap(pose, t)
        if pose.state in ("ragdoll", "getup", "prone", "supine", "crawl", "fall"):
            self._limbs_above_floor(pose, self.frames[seg.frame])
        self._hold_carried(pose, t)
        self._hands_in_room(pose)
        return pose

    def _hands_in_room(self, pose: Pose) -> None:
        """Limb-environment constraint: a hand that would pass through a room surface is placed on it instead
        (it reads as bracing against the wall)."""
        if pose.state == "swing" or pose.state in LYING:  # lying poses place their hands on the floor themselves
            return
        hw, rh = self.frames["wall_right"].origin[0], self.frames["ceiling"].origin[1]
        j = None
        for side in "nf":
            j = j or self.rig.world_joints(pose)
            hx, hy = j[f"hand_{side}"]
            if self.portals and any(x0 <= hx <= x1 and y0 <= hy <= y1 for (x0, y0, x1, y1) in self.portals):
                continue
            cx, cy = clamp(hx, -hw + 3.0, hw - 3.0), clamp(hy, 3.0, rh - 3.0)
            if abs(cx - hx) > 0.5 or abs(cy - hy) > 0.5:
                self.rig.arm_ik(pose, side, (cx, cy), fingertip=True)
                pose.hands[side] = "open"
                j = None

    def _ground_clamp(self, pose: Pose, F: GroundFrame) -> None:
        j = self.rig.world_joints(pose)
        for side in "nf":
            sa, ha = F.to_frame(j[f"ankle_{side}"])
            st, ht = F.to_frame(j[f"toe_{side}"])
            if ha < self.p.ankle_height - 0.5 or ht < -0.5:
                ang = -math.asin(clamp(self.p.ankle_height / self.p.foot, 0.0, 1.0)) if ht < -0.5 else None
                tilt = (pose.body_angle - F.body_angle) * (1.0 if pose.facing >= 0 else -1.0)
                self.rig.leg_ik(pose, side, F.to_world(sa, max(ha, self.p.ankle_height)), None if ang is None else max(0.0, ang) - tilt)

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
        # foot pitch is authored relative to the SURFACE; convert to the (possibly tilted) character frame
        tilt = (pose.body_angle - F.body_angle) * (1.0 if pose.facing >= 0 else -1.0)
        for _ in range(4):
            pose.root = F.to_world(sp, hp)
            for k, side in enumerate("nf"):
                h = lift[k] + self.p.ankle_height
                # keep the toe above the surface: foot pitch may not point the toe below h=0
                min_ang = -math.asin(clamp(h / self.p.foot, 0.0, 1.0))
                ankle = F.to_world(plants[k], h)
                self.rig.leg_ik(pose, side, ankle, max(angles[k], min_ang) - tilt)
            # joint-level collision constraint: a knee may touch the surface (kneeling) but never pass through it;
            # lift the pelvis by the deficit and re-solve the legs
            j = self.rig.world_joints(pose)
            low = min(F.to_frame(j["knee_n"])[1], F.to_frame(j["knee_f"])[1])
            if low >= KNEE_CLEARANCE - 0.05:
                break
            hp += (KNEE_CLEARANCE - low) * 1.2

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
        if seg.data.get("fight"):  # between combat moves: the fighting stance
            return self._eval_guard(seg, t)
        pose, F = self._base(seg, t)
        tau = t - seg.t0
        s = self._rec(self.S, t, seg)
        breath = math.sin(2 * PI * tau / 3.2)
        sway = math.sin(2 * PI * tau / 4.4)  # slow weight shift between the feet
        pose.root = F.to_world(s + 2.5 * sway * seg.facing, self.stand_h - 2.0 + 1.2 * breath - 0.8 * abs(sway))
        L = pose.local
        set_lean(L, 0.03 + 0.01 * breath, chest=0.02 * sway)
        pose.hip_twist = 0.25 * sway
        pose.twist = -0.15 * sway
        set_arm(L, "n", 0.12 + 0.03 * breath - 0.05 * sway, 0.3)
        set_arm(L, "f", -0.1 - 0.03 * breath + 0.05 * sway, 0.35)
        if seg.data.get("gaze_mode") == "notice":
            set_lean(L, NOTICE["lean"](tau))
            set_arm(L, "f", NOTICE["armF"](tau), NOTICE["elbF"](tau))
            pose.eye = NOTICE["eye"](tau)
            sy = NOTICE["sy"](tau)
            pose.squash = (1.0 / math.sqrt(sy), sy)
            pose.pivot_y = -(self.stand_h - 2.0)
        if seg.data.get("look"):
            look = Track.of((0.0, 1.0), (0.35, 1.0), (0.55, -1.0, "hold"), (1.15, -1.0), (1.3, 1.0))
            tilt = Track.of((0.0, 0.0), (0.3, -0.35), (0.55, -0.1), (1.15, -0.15), (1.4, 0.05))
            pose.head_facing = 1.0 if look(tau) > 0 else -1.0
            L["head"] = -tilt(tau)
        clip, ctau = None, 0.0
        if seg.data.get("settle"):  # relief after a hard landing (motion library; second relief = head-shake variant)
            clip = get_clip("recover_relief_shake" if seg.data.get("variant", 0) % 2 == 1 else "recover_relief")
            perf = Performance(intensity=seg.data.get("settle_k", 1.0), emotion="relieved")
            ctau = tau * perf.effective()[0]
            v = clip.sample(tau, perf)
            self._apply(pose, F, s + 2.5 * sway * seg.facing * smoothstep(0.9, 1.2, tau), v)
        if seg.data.get("tense"):  # braced, eyes on what is coming; when the floor tilts away: lose balance
            lb = get_clip("lose_balance")
            ts_hit = max((ts for ts in self.shift_times if seg.t0 <= ts <= t), default=None)
            v = lb.sample(0.0 if ts_hit is None else t - ts_hit)
            v["crouch"] = v.get("crouch", 0.0) - 0.017 * math.sin(2 * PI * tau / 1.1)  # tense breathing
            self._apply(pose, F, s, v)
            if ts_hit is not None and t - ts_hit > 0.12:
                pose.hands = {"n": "open", "f": "open"}
        if seg.data.get("look_back"):  # last look at the room from the doorway
            lb = smoothstep(0.0, 0.3, tau) * (1 - smoothstep(seg.data.get("pause", 1.0) - 0.25, seg.data.get("pause", 1.0), tau))
            pose.twist = -0.6 * lb
            set_lean(L, 0.02, chest=0.1 * lb)
            set_arm(L, "n", 0.1, 0.4)
            set_arm(L, "f", -0.15, 0.4)
            pose.eye = 1.0 + 0.2 * lb
        plants, lift, ang = self._settle_feet(seg, t)
        self._legs(pose, F, plants, lift, ang)
        if clip is not None and clip.contacts:  # hands on the knees etc. (declared clip contacts)
            self._contacts(pose, F, clip, ctau, (plants[0] + plants[1]) / 2)
        g, w = self._seg_gaze(seg, t)
        self._gaze(pose, g, w)
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
        cautious = seg.data.get("style") == "cautious"
        if cautious:
            crouch += 9.0
            lean += 0.22
        bob = gait.pelvis_bob(tc, 0.0)
        pose.root = F.to_world(s, self.stand_h - crouch + overlay + bob)
        L = pose.local
        set_lean(L, lean, chest=-0.1 * lean, head=-0.65 * lean + (0.12 if cautious else 0.0))
        c = gait.arm_phase(tc)
        A = lerp(0.35, 1.05, rb) * self.style.arm_swing_scale * (0.3 if cautious else 1.0)
        elbow = lerp(0.35, 1.55, rb)
        if cautious:  # hands raised near the chest, careful
            set_arm(L, "n", 0.75 - A * c, 1.9 + 0.15 * c)
            set_arm(L, "f", 0.45 + A * c, 2.15 - 0.15 * c)
            pose.eye = 1.15
        else:
            set_arm(L, "n", -A * c - arm_back, elbow + 0.25 * c)
            set_arm(L, "f", A * c - arm_back, elbow - 0.25 * c)
        # shoulders counter-rotate against the hips (torso twist), stronger when running
        tw = lerp(0.35, 0.9, rb) * (0.4 if cautious else 1.0)
        pose.twist = -tw * c
        pose.hip_twist = 0.8 * tw * c
        lifts, angs, sss = [], [], []
        for leg in (0, 1):
            fs = gait.foot(tc, leg)
            sss.append(fs.s)
            lifts.append(fs.h)
            angs.append(fs.angle)
        self._legs(pose, F, (sss[0], sss[1]), (lifts[0], lifts[1]), (angs[0], angs[1]))
        if not cautious:
            pose.eye = 1.0 + 0.12 * rb
        g, w = self._seg_gaze(seg, t)
        self._gaze(pose, g, 0.75 * w)
        if seg.data.get("carry") and self.prop_at:  # carrying a bar: both hands on it
            a, b = self._bar_grips(seg.data["carry"], t, "carry")
            self._hands_to(pose, [("n", a), ("f", b)])
        return pose

    # -- press a physical button (anticipation -> reach -> contact -> recoil)
    def _eval_press(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        hes = bool(seg.data.get("hesitate"))
        P = PRESS_H if hes else PRESS
        tau = clamp(t - seg.t0, 0, 2.45 if hes else 1.75)
        s = self._rec(self.S, t, seg)
        pose.root = F.to_world(s, self.stand_h - 2.0 - P["crouch"](tau))
        L = pose.local
        set_lean(L, P["lean"](tau), chest=-0.05)
        pose.eye = P["eye"](tau)
        sy = P["sy"](tau)
        pose.squash = (1.0 / math.sqrt(sy), sy)
        pose.pivot_y = -(self.stand_h - 2.0)
        pose.twist = P["twist"](tau) if hes else 0.6 * P["ik"](tau)
        set_arm(L, "f", P["armF"](tau), P["elbF"](tau))
        set_arm(L, "n", P["armN"](tau), 0.4)
        w = P["ik"](tau)
        if w > 0:
            fk = dict(L)
            bx, bh = seg.data["button"]
            target = F.to_world(bx + P["ds"](tau) * (1 if s > bx else -1), bh + P["dh"](tau))
            self.rig.arm_ik(pose, "n", target, fingertip=True)
            for k in ("upper_arm_n", "forearm_n", "hand_n"):
                L[k] = lerp_angle(fk.get(k, L[k]), L[k], w)
            pose.hands["n"] = "point"
        self._legs(pose, F, seg.data["plants"])
        if hes:
            self._gaze(pose, seg.data.get("gaze"), P["gaze"](tau), extra_tilt=P["cock"](tau) + P["lookup"](tau))
            if tau > H + 0.62 and tau < H + 0.8:
                pose.head_facing = -1.0  # startled glance around the room
        else:
            set_lean(L, P["lean"](tau), chest=-0.05, head=-P["head"](tau))
            pose.head_facing = 1.0 if P["look"](tau) > 0 else -1.0
        return pose

    # -- point at a target (anticipation dip, snap, excited hold)
    def _eval_point(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tau = t - seg.t0
        s = self._rec(self.S, t, seg)
        dip = Track.of((0.0, 0.0), (0.18, 7.0), (0.3, -3.0, "out"), (0.5, 0.0))(tau)
        bounce = 1.5 * math.sin(tau * 9.0) * smoothstep(0.4, 0.6, tau)
        pose.root = F.to_world(s, self.stand_h - 2.0 - dip + bounce)
        L = pose.local
        snap = smoothstep(0.2, 0.32, tau)
        set_lean(L, 0.05 + 0.12 * snap)
        pose.twist = 0.9 * snap
        pose.eye = 1.0 + 0.45 * snap
        sy = Track.of((0.2, 1.0), (0.3, 1.06), (0.42, 0.98), (0.55, 1.0))(tau)
        pose.squash = (1.0 / math.sqrt(sy), sy)
        pose.pivot_y = -(self.stand_h - 2.0)
        # far arm: anticipation swing back, then a small fist pump
        pump = math.sin(PI * clamp((tau - 0.55) / 0.35, 0, 1))
        set_arm(L, "f", -0.4 * (1 - snap) + 0.6 * snap + 1.0 * pump, 1.6 + 0.7 * pump)
        set_arm(L, "n", -0.7 * (1 - snap), 0.4)
        tgt = seg.data.get("gaze")
        if tgt is not None and snap > 0:
            ch = self.rig.fk(pose)
            sh = ch["upper_arm_n"][0]
            tc = to_character(tgt, pose.root, pose.body_angle, pose.facing)
            aim = math.atan2(tc[1] - sh[1], tc[0] - sh[0])
            chest_abs = L["spine"] + L.get("chest", 0.0)
            L["upper_arm_n"] = lerp_angle(L["upper_arm_n"], wrap_angle(aim - chest_abs), snap)
            L["forearm_n"] = lerp(L["forearm_n"], 0.05, snap)
            L["hand_n"] = 0.0
            pose.hands["n"] = "point"
        self._legs(pose, F, seg.data["plants"])
        g, w = self._seg_gaze(seg, t)
        self._gaze(pose, g, w)
        return pose

    # -- duck slide (feet first, torso laid back, trailing hand on the surface)
    def _eval_slide(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tc = clamp(t, seg.t0, seg.t1)
        tau = tc - seg.t0
        d = seg.data["dir"]
        s, h = self._rec(self.S, tc), self._rec(self.H, tc)
        pose.root = F.to_world(s, h)
        e = smoothstep(0.0, SLIDE_DROP + 0.05, tau)
        L = pose.local
        set_lean(L, lerp(0.3, -1.22, e), chest=-0.12 * e, head=0.8 * e)
        lead = s + d * lerp(30.0, 80.0, e)
        trail = s - d * lerp(12.0, 3.0, e)
        self._legs(pose, F, (lead, trail), (0.0, 0.0), (0.55 * e, -0.15))
        set_arm(L, "f", lerp(0.6, 1.0, e), 0.7)
        pose.hands = {"n": "open", "f": "fist"}
        if e > 0:
            fk = {k: L[k] for k in ("upper_arm_n", "forearm_n")}
            self.rig.arm_ik(pose, "n", F.to_world(s - d * 46.0, 7.0))  # trailing hand skims the surface
            for k, v in fk.items():
                L[k] = lerp_angle(v, L[k], e)
        pose.eye = 1.25
        return pose

    # -- standing jump anticipation (crouch, arms swing back, eyes on the target)
    def _eval_crouch(self, seg: Segment, t: float) -> Pose:
        pose, F = self._base(seg, t)
        tau = clamp(t - seg.t0, 0.0, seg.data.get("dur", 0.26))
        dur = seg.data.get("dur", 0.26)
        u = tau / dur
        e = smoothstep(0.0, 1.0, u)
        s = self._rec(self.S, t, seg)
        pose.root = F.to_world(s, self.stand_h - 2.0 - 26.0 * math.sin(PI * 0.5 * min(1.0, u * 1.25)))
        L = pose.local
        set_lean(L, 0.12 + 0.38 * e, chest=-0.1 * e)
        set_arm(L, "n", -1.25 * e, 0.3)
        set_arm(L, "f", -1.05 * e, 0.35)
        pose.eye = 1.25
        self._legs(pose, F, seg.data["plants"])
        g = seg.data.get("gaze")
        self._gaze(pose, g, 1.0 if g else 0.0)
        return pose

    # -- hanging / swinging from a bar: wrists locked to the grip, legs trail the swing
    def _eval_swing(self, seg: Segment, t: float) -> Pose:
        tc = clamp(t, seg.t0, seg.t1)
        pose = Pose(local=base_pose(), facing=seg.facing, state="swing")
        pose.root = (self._rec(self.PX, tc), self._rec(self.PY, tc))
        pose.body_angle = self._rec(self.ANG, tc)
        tau = tc - seg.t0
        w = (self._rec(self.ANG, min(tc + 0.02, seg.t1)) - self._rec(self.ANG, max(tc - 0.02, seg.t0))) / 0.04
        L = pose.local
        set_lean(L, 0.0, head=-0.25)  # straight torso: the grip geometry is the rigid body's
        lag = clamp(-0.11 * w * seg.facing, -0.85, 0.85)
        catch = math.exp(-tau * 7.0)  # legs kick through on the catch, then trail
        kick = 0.0
        for (p0, p1) in seg.data.get("pumps", []):  # pumping: pike the legs through the bottom of the arc
            if p0 - 0.12 <= tc <= p1 + 0.15:
                kick = max(kick, math.sin(PI * clamp((tc - p0 + 0.12) / (p1 - p0 + 0.27), 0, 1)))
        catch += 0.9 * kick
        L["thigh_n"] = -PI / 2 + 0.25 + lag + 0.5 * catch
        L["shin_n"] = -(0.45 + 0.25 * abs(lag)) - 0.4 * catch
        L["thigh_f"] = -PI / 2 + 0.05 + 0.8 * lag + 0.2 * catch
        L["shin_f"] = -(0.3 + 0.2 * abs(lag))
        L["foot_n"] = L["foot_f"] = PI / 2
        B = seg.data["anchor"]
        L["head"] = L.get("head", 0.0) - 0.45 * catch * (1 - kick)  # head snaps with the jolt of the catch
        for side in "nf":
            self.rig.arm_ik(pose, side, B)
        pose.hands = {"n": "fist", "f": "fist"}
        hang = seg.data.get("hang", 0.0)
        pose.eye = lerp(1.8, 1.25, smoothstep(0.0, 0.6, tau))
        if hang > 0.4:
            # dangle: look down at the drop (wide eyes), then at the door (determined), then pump
            down = smoothstep(0.15, 0.4, tau) * (1 - smoothstep(hang - 0.55, hang - 0.3, tau))
            ahead = smoothstep(hang - 0.55, hang - 0.3, tau)
            r = (pose.root[0] - B[0], pose.root[1] - B[1])
            n = math.hypot(*r) or 1.0
            below = (pose.root[0] + r[0] / n * 400, pose.root[1] + r[1] / n * 400)
            if down > 0:
                self._gaze(pose, below, down)
                pose.eye = max(pose.eye, 1.0 + 0.75 * down)
            if ahead > 0 and seg.data.get("look_to") is not None:
                self._gaze(pose, seg.data["look_to"], ahead)
                pose.eye = lerp(pose.eye, 1.1, ahead)
            if tau < hang:  # small dangling leg kicks (not pumping)
                L["thigh_n"] += 0.18 * math.sin(tau * 9.0) * down
                L["thigh_f"] -= 0.15 * math.sin(tau * 9.0 + 1.3) * down
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
            if seg.data.get("flip"):  # somersault: a tight tuck through the rotation, opening out to land
                from .acrobatics import flip_tuck
                wf = flip_tuck(tau, seg.data.get("T", 0.8))  # the same tuck the physics spins with
                set_lean(L, lerp(0.1, 0.85, wf), chest=0.25 * wf, head=lerp(-0.2, 0.6, wf))
                self._tuck(L, max(wf, 0.25 * tuck))
                set_arm(L, "n", lerp(2.4, 1.2, wf) - 1.0 * b, 0.4)
                set_arm(L, "f", lerp(2.2, 1.1, wf) - 0.9 * b, 0.5)
                self._hands_on_shins(pose, wf)
            btn, pt = seg.data.get("button"), seg.data.get("press_t")
            if btn is not None:
                self._gaze(pose, btn, smoothstep(0.0, 0.15, tau))
                if pt is not None:  # mid-air slap: near hand IK onto the button around the contact instant
                    w = smoothstep(pt - 0.24, pt - 0.03, tc) * (1 - smoothstep(pt + 0.08, pt + 0.26, tc))
                    if w > 0:
                        fk = {k: L[k] for k in ("upper_arm_n", "forearm_n", "hand_n")}
                        self.rig.arm_ik(pose, "n", btn, fingertip=True)
                        for k, v in fk.items():
                            L[k] = lerp_angle(v, L[k], w)
                        pose.hands["n"] = "open"
                        pose.eye = 1.15 + 0.5 * w
        else:
            # key-posed fall (motion library): balance lost -> irregular flail (reach / windmill / kick / scramble)
            # -> brace toward the predicted landing as the surface approaches
            lose = get_clip("lose_balance").sample(0.24 + 0.6 * tau)
            fall = get_clip("fall_flail").sample(tau, Performance(emotion="afraid"))
            k = smoothstep(0.06, 0.34, tau)
            v = {c: lerp(lose.get(c, NEUTRAL[c]), fall.get(c, NEUTRAL[c]), k) for c in set(lose) | set(fall)}
            if b > 0:
                br = get_clip("brace").sample(0.3 * b)
                wb = smoothstep(0.0, 1.0, b)
                v = {c: lerp(v.get(c, NEUTRAL[c]), br.get(c, NEUTRAL[c]), wb) for c in set(v) | set(br)}
            self._apply(pose, None, 0.0, v, grounded=False)
            pose.hands = {"n": "open", "f": "open"}
            bp = seg.data.get("brace_point")
            if bp is not None and b > 0:
                self._gaze(pose, bp, clamp(b * 1.5, 0, 1))
            bar = seg.data.get("reach_bar")
            if bar is not None:  # reaching for the bar on the way past
                j = self.rig.world_joints(pose)
                dist = math.dist(j["shoulder"], bar)
                w = 1 - smoothstep(70.0, 260.0, dist)
                self._gaze(pose, bar, clamp(w * 1.6, 0, 1))
                if w > 0:  # blend in position space (angle blends can flip direction across half a turn)
                    for side in "nf":
                        wp = j[f"wrist_{side}"]
                        self.rig.arm_ik(pose, side, (wp[0] + (bar[0] - wp[0]) * w, wp[1] + (bar[1] - wp[1]) * w))
        L["foot_n"] = L["foot_f"] = PI / 2
        return pose

    # -- landing: compression, follow-through, balance wobble (feet stay planted)
    def _eval_landing(self, seg: Segment, t: float) -> Pose:
        """Landing as a key-pose performance (motion library) chosen and scaled by impact speed; the physics supplies
        the contact point, planted feet and the balance wobble of the body angle."""
        pose, F = self._base(seg, t)
        tc = clamp(t, seg.t0, seg.t1)
        pose.body_angle = self._rec(self.ANG, tc)
        tau = tc - seg.t0
        name, perf = landing_clip(seg.data.get("approach", 600.0))
        clip = get_clip(name)
        v = clip.sample(tau, perf)
        s = self._rec(self.S, tc)
        self._apply(pose, F, s, v)
        err = pose.body_angle - F.body_angle
        wind = clamp(abs(err) * 4.0, 0, 1)  # balance: arms counter the body's wobble
        pose.twist += 0.35 * wind * math.sin(tau * 13)
        pose.hands = {"n": "open", "f": "open"}
        self._legs(pose, F, seg.data["plants"])
        plants = seg.data["plants"]
        self._contacts(pose, F, clip, tau * perf.effective()[0], (plants[0] + plants[1]) / 2)
        return pose

    # ------------------------------------------------------------ for QA
    def planted_intervals(self) -> List[PlantedInterval]:
        out: List[PlantedInterval] = []
        for seg in self.segments:
            F = self.frames[seg.frame]
            bl = BLEND_IN.get(seg.kind, 0.15) + 1e-3
            if seg.kind in ("idle", "turn", "press", "landing", "point", "crouch") + tuple(STANCE) and seg.data.get("plants"):
                a = seg.t0 + bl
                if seg.t1 - a > 0.05:
                    for k, side in enumerate("nf"):
                        if seg.kind == "strike" and seg.data.get("limb", "").endswith("_" + side) and seg.data["limb"].startswith("foot"):
                            continue  # the kicking foot leaves the floor
                        if seg.kind == "strike" and seg.data.get("move") == "flying_kick":
                            continue  # both feet leave the floor
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
