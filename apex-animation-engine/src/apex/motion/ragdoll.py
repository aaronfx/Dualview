"""Physics-driven fall: an 11-part articulated ragdoll built from a character's pose.

When a character is knocked down, its kinematic body is replaced by linked rigid bodies (pymunk):
pelvis-spine, chest, head (neck + head), upper arms, forearms (with hands), thighs, shins (with feet).
- Joints are pivots at the rig's joint positions.
- Each joint has rotation limits taken from the rig's bone limits, so elbows and knees only bend the right way.
- A weak damped spring holds each joint toward the pose it started in ("muscle tone"), so the body does not fold
  like cloth.

The hit's impulse and the body's own velocity start the fall. Gravity, the floor, the walls and the props decide the
rest: the tumble, where it lands, and whether it ends up face up or face down.

The fall is sampled at a fixed rate; `pose_from_sample` turns a sample back into a rig pose (local joint angles), so
the animator and the renderer draw the simulated fall with the same rig as every other motion.
"""
from __future__ import annotations

import itertools
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pymunk

from ..core.mathx import Vec, wrap_angle
from ..physics.world import ALL, CAT_CHAR, CT_PROP, PhysicsWorld
from ..rig.skeleton import to_world
from ..rig.stickman import Pose, StickmanRig

CAT_RAG = 0b1000  # collision category of ragdoll parts (props and statics collide with them, standing characters do not)
_GROUPS = itertools.count(1001)

# part -> (bone at its start, bone at its end, parent part, mass fraction)
PARTS: Dict[str, Tuple[str, str, Optional[str], float]] = {
    "spine": ("spine", "spine", None, 0.16),
    "chest": ("chest", "chest", "spine", 0.22),
    "head": ("neck", "head", "chest", 0.09),
    "upper_arm_n": ("upper_arm_n", "upper_arm_n", "chest", 0.03), "upper_arm_f": ("upper_arm_f", "upper_arm_f", "chest", 0.03),
    "forearm_n": ("forearm_n", "hand_n", "upper_arm_n", 0.025), "forearm_f": ("forearm_f", "hand_f", "upper_arm_f", 0.025),
    "thigh_n": ("thigh_n", "thigh_n", "spine", 0.1), "thigh_f": ("thigh_f", "thigh_f", "spine", 0.1),
    "shin_n": ("shin_n", "shin_n", "thigh_n", 0.06), "shin_f": ("shin_f", "shin_f", "thigh_f", 0.06),
}
ORDER = list(PARTS)
# a loose sprawl (relative joint angles, character frame): knees and elbows a little bent, arms slightly forward
RELAXED: Dict[str, float] = {
    "chest": 0.05, "head": 0.1, "upper_arm_n": -math.pi + 0.5, "upper_arm_f": -math.pi + 0.25, "forearm_n": 0.7, "forearm_f": 0.5,
    "thigh_n": -math.pi + 0.45, "thigh_f": -math.pi + 0.15, "shin_n": -0.8, "shin_f": -0.35,
}
# relative rotation limits (child vs parent, character frame, radians); thighs are relative to the spine
LIMITS: Dict[str, Tuple[float, float]] = {
    "chest": (-0.9, 0.7), "head": (-0.9, 0.9), "forearm_n": (-0.05, 2.6), "forearm_f": (-0.05, 2.6),
    "thigh_n": (-math.pi - 1.0, -math.pi + 2.2), "thigh_f": (-math.pi - 1.0, -math.pi + 2.2),
    "shin_n": (-2.6, 0.03), "shin_f": (-2.6, 0.03),
    "upper_arm_n": (-math.pi - 1.2, -math.pi + 3.2), "upper_arm_f": (-math.pi - 1.2, -math.pi + 3.2),
}


class Ragdoll:
    def __init__(self, world: PhysicsWorld, rig: StickmanRig, pose: Pose, tag: str, mass: float = 70.0,
                 vel: Vec = (0.0, 0.0), tone: float = 4.5, limb_radius: float = 4.5, relax: Optional[Dict[str, float]] = None):
        """`relax`: joint angles (character-frame, relative to the parent part) the muscle tone pulls toward, e.g. a
        loose sprawl with bent knees and elbows; by default the pose the fall started from."""
        self.world, self.rig, self.tag = world, rig, tag
        self.facing = 1.0 if pose.facing >= 0 else -1.0
        self.group = next(_GROUPS)
        ch = rig.fk(pose)
        W = lambda q: to_world(q, pose.root, pose.body_angle, pose.facing)
        self.ends: Dict[str, Tuple[Vec, Vec]] = {}
        for part, (b0, b1, _, _) in PARTS.items():
            self.ends[part] = (W(ch[b0][0]), W(ch[b1][1]))
        self.foot_local = {s: pose.local.get(f"foot_{s}", math.pi / 2) for s in "nf"}
        self.bodies: Dict[str, pymunk.Body] = {}
        self.half: Dict[str, float] = {}
        self.constraints: List[pymunk.Constraint] = []
        flt = pymunk.ShapeFilter(group=self.group, categories=CAT_RAG, mask=ALL ^ CAT_CHAR)
        for part, (_, _, _, frac) in PARTS.items():
            a, b = self.ends[part]
            L = max(4.0, math.dist(a, b))
            m = mass * frac
            body = pymunk.Body(m, pymunk.moment_for_segment(m, (-L / 2, 0), (L / 2, 0), limb_radius))
            body.position = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            body.angle = math.atan2(b[1] - a[1], b[0] - a[0])
            body.velocity = vel
            shapes = [pymunk.Segment(body, (-L / 2, 0), (L / 2, 0), limb_radius)]
            if part == "head":  # the head is a ball at the end of the neck
                r = rig.p.head * 0.55
                shapes.append(pymunk.Circle(body, r, (L / 2 - r * 0.8, 0)))
            if part.startswith("shin"):  # the foot
                fa = self.foot_local[part[-1]] * self.facing
                shapes.append(pymunk.Segment(body, (L / 2, 0), (L / 2 + math.cos(fa) * rig.p.foot, math.sin(fa) * rig.p.foot), 3.0))
            for sh in shapes:
                sh.friction, sh.elasticity, sh.filter, sh.collision_type = 0.85, 0.05, flt, CT_PROP
                world._tags[sh] = f"{tag}:{part}"
            world.space.add(body, *shapes)
            self.bodies[part] = body
            self.half[part] = L / 2
        for part, (_, _, parent, _) in PARTS.items():
            if parent is None:
                continue
            pa, ch_b = self.bodies[parent], self.bodies[part]
            j = pymunk.PivotJoint(pa, ch_b, self.ends[part][0])
            j.collide_bodies = False
            self.constraints.append(j)
            rel0 = ch_b.angle - pa.angle
            lo, hi = LIMITS.get(part, (-math.pi, math.pi))
            if self.facing < 0:
                lo, hi = -hi, -lo
            # the joint's raw angle difference may be offset by whole turns from the character-frame value
            k = round((rel0 - (lo + hi) / 2) / (2 * math.pi))
            lo, hi = lo + 2 * math.pi * k, hi + 2 * math.pi * k
            rest = rel0
            if relax is not None and part in relax:
                r = self.facing * relax[part]
                rest = r + 2 * math.pi * round((rel0 - r) / (2 * math.pi))  # the same turn as the joint now
            rest = min(max(rest, lo + 0.02), hi - 0.02)
            self.constraints.append(pymunk.RotaryLimitJoint(pa, ch_b, lo, hi))
            I = ch_b.moment
            stiff = I * tone * tone
            self.constraints.append(pymunk.DampedRotarySpring(pa, ch_b, rest, stiff, 2 * 0.7 * math.sqrt(stiff * I)))
        world.space.add(*self.constraints)
        self.still_since: Optional[float] = None

    # ------------------------------------------------------------ driving
    def apply_impulse(self, part: str, impulse: Vec, point: Optional[Vec] = None) -> None:
        b = self.bodies[part]
        b.apply_impulse_at_world_point(impulse, point or b.position)

    def part_ends(self, part: str) -> Tuple[Vec, Vec]:
        b = self.bodies[part]
        h = self.half[part]
        return tuple(b.local_to_world((-h, 0))), tuple(b.local_to_world((h, 0)))

    def sample(self) -> np.ndarray:
        """One sample: x, y, angle for every part (in ORDER)."""
        return np.array([v for p in ORDER for v in (self.bodies[p].position.x, self.bodies[p].position.y, self.bodies[p].angle)])

    def max_speed(self) -> Tuple[float, float]:
        v = max(b.velocity.length for b in self.bodies.values())
        w = max(abs(b.angular_velocity) for b in self.bodies.values())
        return v, w

    def settled(self, t: float, v_thr: float = 14.0, w_thr: float = 0.8, hold: float = 0.3) -> bool:
        v, w = self.max_speed()
        if v < v_thr and w < w_thr:
            self.still_since = self.still_since if self.still_since is not None else t
            return t - self.still_since >= hold
        self.still_since = None
        return False

    def remove(self) -> None:
        for b in self.bodies.values():
            for sh in list(b.shapes):
                self.world._tags.pop(sh, None)
        self.world.space.remove(*self.constraints)
        for b in self.bodies.values():
            self.world.space.remove(b, *b.shapes)
        self.bodies.clear()
        self.constraints.clear()

    # ------------------------------------------------------------ reading poses back
    def lying(self) -> Tuple[str, float, Vec, float]:
        """How the body came to rest: ('prone' | 'supine', facing for that lying posture, pelvis, spine angle)."""
        pel, _ = self.part_ends("spine")
        _, top = self.part_ends("head")
        head_dir = 1.0 if top[0] >= pel[0] else -1.0
        # the body's front: the character's forward axis carried along with the chest's rotation
        chest = self.bodies["chest"]
        up = (math.cos(chest.angle), math.sin(chest.angle))  # along the chest, toward the neck
        front = (up[1] * self.facing, -up[0] * self.facing)  # forward = up rotated clockwise (mirrored by facing)
        if front[1] < 0:  # face down
            return "prone", head_dir, pel, chest.angle
        return "supine", -head_dir, pel, chest.angle


def pose_from_sample(rig: StickmanRig, sample: np.ndarray, facing: float, foot_local: Dict[str, float],
                     half: Dict[str, float]) -> Pose:
    """Rebuild a rig pose from one ragdoll sample (positions and angles of the parts)."""
    f = 1.0 if facing >= 0 else -1.0
    P = {p: (sample[3 * i], sample[3 * i + 1], sample[3 * i + 2]) for i, p in enumerate(ORDER)}

    def ends(p):
        x, y, a = P[p]
        h = half[p]
        return (x - math.cos(a) * h, y - math.sin(a) * h), (x + math.cos(a) * h, y + math.sin(a) * h)

    def cabs(p):  # absolute angle in the character frame (body_angle 0, mirrored by facing)
        a, b = ends(p)
        return math.atan2(b[1] - a[1], (b[0] - a[0]) * f)

    A = {p: cabs(p) for p in ORDER}
    L = {
        "spine": A["spine"], "chest": wrap_angle(A["chest"] - A["spine"]),
        "neck": wrap_angle(A["head"] - A["chest"]), "head": 0.0,
    }
    for s in "nf":
        L[f"upper_arm_{s}"] = wrap_angle(A[f"upper_arm_{s}"] - A["chest"])
        L[f"forearm_{s}"] = wrap_angle(A[f"forearm_{s}"] - A[f"upper_arm_{s}"])
        L[f"hand_{s}"] = 0.0
        L[f"thigh_{s}"] = A[f"thigh_{s}"]
        L[f"shin_{s}"] = wrap_angle(A[f"shin_{s}"] - A[f"thigh_{s}"])
        L[f"foot_{s}"] = foot_local[s]
    root, _ = ends("spine")
    return Pose(root=root, body_angle=0.0, facing=f, local=L, state="ragdoll", eye=0.55)
