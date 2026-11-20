"""Articulated stickman rig: skeleton definition, pose container, IK helpers and world-space evaluation."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Tuple

from ..core.mathx import Vec, clamp, lerp, lerp_angle, v_rot, wrap_angle
from .ik import TwoBoneSolution, solve_two_bone
from .skeleton import Bone, Skeleton, to_character, to_world

PI = math.pi
SIDES = ("n", "f")  # near / far limb (drawing order + shading)


@dataclass(frozen=True)
class Proportions:
    spine: float = 30.0
    chest: float = 28.0
    neck: float = 7.0
    head: float = 24.0
    upper_arm: float = 32.0
    forearm: float = 29.0
    hand: float = 9.0
    thigh: float = 44.0
    shin: float = 42.0
    foot: float = 15.0
    ankle_height: float = 4.0  # ankle above ground when the foot is flat

    @property
    def stand_height(self) -> float:
        """Pelvis height above ground with nearly straight legs."""
        return (self.thigh + self.shin) * 0.985 + self.ankle_height


def build_stickman(p: Proportions = Proportions()) -> Skeleton:
    bones = [
        Bone("spine", None, p.spine, PI / 2, limits=(PI / 2 - 1.5, PI / 2 + 1.0)),
        Bone("chest", "spine", p.chest, 0.0, limits=(-1.0, 0.8)),
        Bone("neck", "chest", p.neck, 0.0, limits=(-1.0, 1.0)),
        Bone("head", "neck", p.head, 0.0, limits=(-0.9, 0.9)),
    ]
    for s in SIDES:
        bones += [
            Bone(f"upper_arm_{s}", "chest", p.upper_arm, -PI + (0.12 if s == "n" else -0.1), attach=0.86),
            Bone(f"forearm_{s}", f"upper_arm_{s}", p.forearm, 0.3, limits=(-0.05, 2.8)),
            Bone(f"hand_{s}", f"forearm_{s}", p.hand, 0.0, limits=(-1.2, 1.2)),
        ]
    for s in SIDES:
        bones += [
            Bone(f"thigh_{s}", None, p.thigh, -PI / 2, limits=(-PI / 2 - 1.1, -PI / 2 + 2.4)),
            Bone(f"shin_{s}", f"thigh_{s}", p.shin, -0.05, limits=(-2.75, 0.03)),
            Bone(f"foot_{s}", f"shin_{s}", p.foot, PI / 2, limits=(PI / 2 - 1.2, PI / 2 + 0.9)),
        ]
    return Skeleton(bones)


@dataclass
class Pose:
    """Complete character state for one instant (everything needed to draw and to inspect)."""

    root: Vec = (0.0, 0.0)  # pelvis, world
    body_angle: float = 0.0  # rotation of the character frame relative to world-up
    facing: float = 1.0  # +1 facing the frame's +x; animated through 0 for turns
    local: Dict[str, float] = field(default_factory=dict)
    stretch: Dict[str, float] = field(default_factory=dict)
    squash: Tuple[float, float] = (1.0, 1.0)
    pivot_y: float = 0.0
    head_facing: float = 1.0  # relative look direction of the head (+1 same as body, -1 looking back)
    eye: float = 1.0  # expression: visor/eye opening
    hands: Dict[str, str] = field(default_factory=lambda: {"n": "fist", "f": "fist"})
    state: str = ""
    twist: float = 0.0  # torso twist: + brings the near shoulder forward (side-view counter-rotation)
    hip_twist: float = 0.0  # pelvis twist: + brings the near hip forward

    def copy(self) -> "Pose":
        return replace(self, local=dict(self.local), stretch=dict(self.stretch), hands=dict(self.hands))


def blend_poses(a: Pose, b: Pose, w: float) -> Pose:
    """Angle-aware blend. Discrete fields (hand shapes, state) switch at w=0.5."""
    w = clamp(w, 0.0, 1.0)
    keys = set(a.local) | set(b.local)
    local = {k: lerp_angle(a.local.get(k, b.local.get(k, 0.0)), b.local.get(k, a.local.get(k, 0.0)), w) for k in keys}
    sk = set(a.stretch) | set(b.stretch)
    stretch = {k: lerp(a.stretch.get(k, 1.0), b.stretch.get(k, 1.0), w) for k in sk}
    return Pose(
        root=(lerp(a.root[0], b.root[0], w), lerp(a.root[1], b.root[1], w)),
        body_angle=lerp_angle(a.body_angle, b.body_angle, w),
        facing=lerp(a.facing, b.facing, w),
        local=local,
        stretch=stretch,
        squash=(lerp(a.squash[0], b.squash[0], w), lerp(a.squash[1], b.squash[1], w)),
        pivot_y=lerp(a.pivot_y, b.pivot_y, w),
        head_facing=lerp(a.head_facing, b.head_facing, w),
        eye=lerp(a.eye, b.eye, w),
        hands=dict(b.hands if w >= 0.5 else a.hands),
        state=b.state if w >= 0.5 else a.state,
        twist=lerp(a.twist, b.twist, w),
        hip_twist=lerp(a.hip_twist, b.hip_twist, w),
    )


class StickmanRig:
    """Skeleton + proportions + kinematic helpers. One instance per character (identity is kept by the spec)."""

    def __init__(self, proportions: Proportions = Proportions()):
        self.p = proportions
        self.skeleton = build_skeleton_cached(proportions)

    # ------------------------------------------------------------- evaluation
    SHOULDER_SPREAD = 4.5
    HIP_SPREAD = 3.0

    def offsets(self, pose: Pose) -> Dict[str, Tuple[float, float]]:
        ts, hs = pose.twist * self.SHOULDER_SPREAD, pose.hip_twist * self.HIP_SPREAD
        return {"upper_arm_n": (ts, 0.0), "upper_arm_f": (-ts, 0.0), "thigh_n": (hs, 0.0), "thigh_f": (-hs, 0.0)}

    def fk(self, pose: Pose):
        return self.skeleton.fk_character(pose.local, pose.stretch, self.offsets(pose))

    def world_joints(self, pose: Pose) -> Dict[str, Vec]:
        """Named world-space joint positions (pelvis, neck, head centre, shoulder, elbows, hands, knees, ankles, toes...)."""
        ch = self.fk(pose)
        W = lambda q: to_world(q, pose.root, pose.body_angle, pose.facing, pose.squash, pose.pivot_y)
        j: Dict[str, Vec] = {"pelvis": W(ch["spine"][0]), "spine_mid": W(ch["spine"][1]), "neck_base": W(ch["chest"][1]),
                             "neck_top": W(ch["neck"][1]), "head_top": W(ch["head"][1])}
        hs, he, _ = ch["head"]
        j["head_center"] = W(((hs[0] + he[0]) / 2, (hs[1] + he[1]) / 2))
        sn, sf = ch["upper_arm_n"][0], ch["upper_arm_f"][0]
        j["shoulder"] = W(((sn[0] + sf[0]) / 2, (sn[1] + sf[1]) / 2))
        for s in SIDES:
            j[f"shoulder_{s}"] = W(ch[f"upper_arm_{s}"][0])
            j[f"elbow_{s}"] = W(ch[f"upper_arm_{s}"][1])
            j[f"wrist_{s}"] = W(ch[f"forearm_{s}"][1])
            j[f"hand_{s}"] = W(ch[f"hand_{s}"][1])
            j[f"hip_{s}"] = W(ch[f"thigh_{s}"][0])
            j[f"knee_{s}"] = W(ch[f"thigh_{s}"][1])
            j[f"ankle_{s}"] = W(ch[f"shin_{s}"][1])
            j[f"toe_{s}"] = W(ch[f"foot_{s}"][1])
        return j

    def head_frame(self, pose: Pose) -> Tuple[Vec, Vec, Vec]:
        """(centre, up, forward) of the head in world space; forward honours head_facing."""
        j = self.world_joints(pose)
        c, top = j["head_center"], j["head_top"]
        up = (top[0] - c[0], top[1] - c[1])
        n = math.hypot(*up) or 1.0
        up = (up[0] / n, up[1] / n)
        # forward is perpendicular to up (clockwise from up for facing +1), flipped by facing * head_facing
        perp = (up[1], -up[0])
        sgn = 1.0 if pose.facing * pose.head_facing >= 0 else -1.0
        fwd = (perp[0] * sgn, perp[1] * sgn)
        return c, up, fwd

    # ------------------------------------------------------------- IK
    def leg_ik(self, pose: Pose, side: str, ankle_world: Vec, foot_world_angle: Optional[float] = None,
               max_stretch: float = 1.08) -> TwoBoneSolution:
        """Place the ankle at a world target. `foot_world_angle` is the foot direction relative to the character
        frame's +x (0 = flat, pointing forward)."""
        tgt = to_character(ankle_world, pose.root, pose.body_angle, pose.facing if abs(pose.facing) > 1e-6 else 1.0)
        hip = self.offsets(pose)[f"thigh_{side}"]
        sol = solve_two_bone(hip, tgt, self.p.thigh, self.p.shin, bend=+1, max_stretch=max_stretch)
        pose.local[f"thigh_{side}"] = sol.a1
        pose.local[f"shin_{side}"] = wrap_angle(sol.a2 - sol.a1)
        fa = 0.0 if foot_world_angle is None else foot_world_angle
        pose.local[f"foot_{side}"] = wrap_angle(fa - sol.a2)
        if sol.stretch != 1.0:
            pose.stretch[f"thigh_{side}"] = pose.stretch[f"shin_{side}"] = sol.stretch
        else:
            pose.stretch.pop(f"thigh_{side}", None)
            pose.stretch.pop(f"shin_{side}", None)
        return sol

    def arm_ik(self, pose: Pose, side: str, target_world: Vec, fingertip: bool = False) -> TwoBoneSolution:
        """Place the wrist (or the fingertip with a straight hand) at a world target. Elbow bends backward/down."""
        ch = self.fk(pose)
        shoulder = ch[f"upper_arm_{side}"][0]
        chest_abs = ch["chest"][2]
        tgt = to_character(target_world, pose.root, pose.body_angle, pose.facing if abs(pose.facing) > 1e-6 else 1.0)
        l2 = self.p.forearm + (self.p.hand if fingertip else 0.0)
        sol = solve_two_bone(shoulder, tgt, self.p.upper_arm, l2, bend=-1)
        pose.local[f"upper_arm_{side}"] = wrap_angle(sol.a1 - chest_abs)
        pose.local[f"forearm_{side}"] = wrap_angle(sol.a2 - sol.a1)
        if fingertip:
            pose.local[f"hand_{side}"] = 0.0
        return sol


_SKEL_CACHE: Dict[Proportions, Skeleton] = {}


def build_skeleton_cached(p: Proportions) -> Skeleton:
    if p not in _SKEL_CACHE:
        _SKEL_CACHE[p] = build_stickman(p)
    return _SKEL_CACHE[p]


# ---------------------------------------------------------------- pose library (character-frame local angles)
def base_pose(**over: float) -> Dict[str, float]:
    d = {
        "spine": PI / 2 - 0.04, "chest": 0.04, "neck": 0.0, "head": 0.05,
        "upper_arm_n": -PI + 0.15, "forearm_n": 0.3, "hand_n": 0.0,
        "upper_arm_f": -PI - 0.12, "forearm_f": 0.35, "hand_f": 0.0,
        "thigh_n": -PI / 2 + 0.05, "shin_n": -0.08, "foot_n": PI / 2,
        "thigh_f": -PI / 2 - 0.04, "shin_f": -0.06, "foot_f": PI / 2,
    }
    d.update(over)
    return d


def set_lean(local: Dict[str, float], lean: float, chest: float = 0.0, head: float = 0.0) -> None:
    """lean > 0 tips the torso forward (toward the facing direction)."""
    local["spine"] = PI / 2 - lean
    local["chest"] = -chest
    local["head"] = -head


def set_arm(local: Dict[str, float], side: str, swing: float, elbow: float) -> None:
    """Arm swing measured from hanging straight down (+ = forward), elbow flexion (+ = forward)."""
    chest_abs = local.get("spine", PI / 2) + local.get("chest", 0.0)
    local[f"upper_arm_{side}"] = wrap_angle(-PI / 2 + swing - chest_abs)
    local[f"forearm_{side}"] = elbow
