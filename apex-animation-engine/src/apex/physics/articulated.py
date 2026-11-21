"""Experimental articulated character fall; no changes to the default APEX simulation.

Each segment is an independent dynamic Chipmunk body connected by a pivot,
rotation limits and a damped spring.  Samples are stored for deterministic
render-time pose reconstruction; the renderer never resimulates physics.
"""
from __future__ import annotations

import math
from typing import Dict, List

import pymunk

from ..rig.stickman import Pose, StickmanRig, base_pose
from .world import ALL, CAT_CHAR, CT_CHARACTER, PhysicsWorld


class ArticulatedFall:
    """Temporary falling-body rig attached to an existing dynamic character torso.

    Not used unless APEX_EXPERIMENTAL_JOINTED_FALL=1.  The original
    character and its state machine remain authoritative.
    """

    def __init__(self, world: PhysicsWorld, tag: str, rig: StickmanRig, facing: float):
        self.world, self.tag, self.rig, self.facing = world, tag, rig, facing
        self.space = world.space
        self.parts: Dict[str, pymunk.Body] = {}
        self.shapes: List[pymunk.Shape] = []
        self.constraints: List[pymunk.Constraint] = []
        self.samples: list[dict] = []
        self.original_filter = world._shapes[tag].filter
        state = world.state(tag)
        pose = Pose(root=state.pos, body_angle=state.angle, facing=facing, local=base_pose())
        joints = rig.world_joints(pose)

        # Named anatomical endpoint pairs and approximate masses (total < 70).
        specs = [
            ("head", "torso", "neck_top", "head_top", 5.0, 7.0, 0.7),
            ("upper_arm_n", "torso", "shoulder_n", "elbow_n", 2.5, 3.7, 1.8),
            ("forearm_n", "upper_arm_n", "elbow_n", "wrist_n", 1.7, 3.0, 2.2),
            ("upper_arm_f", "torso", "shoulder_f", "elbow_f", 2.5, 3.7, 1.8),
            ("forearm_f", "upper_arm_f", "elbow_f", "wrist_f", 1.7, 3.0, 2.2),
            ("thigh_n", "torso", "hip_n", "knee_n", 6.0, 4.6, 1.5),
            ("shin_n", "thigh_n", "knee_n", "ankle_n", 4.0, 3.8, 1.8),
            ("thigh_f", "torso", "hip_f", "knee_f", 6.0, 4.6, 1.5),
            ("shin_f", "thigh_f", "knee_f", "ankle_f", 4.0, 3.8, 1.8),
        ]

        old_mass, old_moment = world._mass_moment[tag]
        limb_mass = sum(item[5 - 1] for item in specs)
        if limb_mass >= old_mass:
            raise ValueError("ragdoll limb mass must be less than body mass")
        torso = world._bodies[tag]
        if torso.body_type != pymunk.Body.DYNAMIC:
            raise ValueError("ragdoll requires a simulated dynamic torso")
        torso.mass = old_mass - limb_mass
        torso.moment = old_moment * (torso.mass / old_mass)

        # Group suppresses intra-character collision while allowing floor and
        # heavy-prop contact. Distinct group per character avoids cross-talk.
        group = 20000 + sum((i + 1) * ord(ch) for i, ch in enumerate(tag))
        world.set_group([tag], group)
        parents: Dict[str, pymunk.Body] = {"torso": torso}
        for name, parent_name, start, end, mass, radius, freedom in specs:
            a, b = joints[start], joints[end]
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = math.hypot(dx, dy)
            if length <= 1.0:
                raise ValueError(f"invalid bone length: {name}")
            moment = pymunk.moment_for_segment(mass, (-length / 2.0, 0), (length / 2.0, 0), radius)
            part = pymunk.Body(mass, moment)
            part.position = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            part.angle = math.atan2(dy, dx)
            ox, oy = part.position.x - state.pos[0], part.position.y - state.pos[1]
            part.velocity = (state.vel[0] - state.angvel * oy, state.vel[1] + state.angvel * ox)
            part.angular_velocity = state.angvel
            shape = pymunk.Segment(part, (-length / 2.0, 0), (length / 2.0, 0), radius)
            shape.friction = 0.9
            shape.elasticity = 0.0
            shape.collision_type = CT_CHARACTER
            shape.filter = pymunk.ShapeFilter(group=group, categories=CAT_CHAR, mask=ALL)
            self.space.add(part, shape)
            self.parts[name] = part
            self.shapes.append(shape)
            world._tags[shape] = f"{tag}:ragdoll:{name}"
            parent = parents[parent_name]
            # World-coordinate anchor at a shared anatomical joint.
            pivot = pymunk.PivotJoint(parent, part, a)
            pivot.collide_bodies = False
            delta = math.atan2(math.sin(part.angle - parent.angle), math.cos(part.angle - parent.angle))
            limit = pymunk.RotaryLimitJoint(parent, part, delta - freedom, delta + freedom)
            spring = pymunk.DampedRotarySpring(parent, part, delta, 1200.0, 220.0)
            self.space.add(pivot, limit, spring)
            self.constraints.extend([pivot, limit, spring])
            parents[name] = part

    def record(self, t: float) -> None:
        """Save angular motion once per fixed physics step for pure pose evaluation."""
        self.samples.append({"t": float(t), "angles": {name: float(body.angle) for name, body in self.parts.items()}})

    def cleanup(self) -> None:
        """Remove temporary limbs when returning to established prone interactions."""
        self.space.remove(*self.constraints)
        for shape in self.shapes:
            self.world._tags.pop(shape, None)
        self.space.remove(*self.shapes)
        self.space.remove(*self.parts.values())
        self.world._shapes[self.tag].filter = self.original_filter
        mass, moment = self.world._mass_moment[self.tag]
        torso = self.world._bodies[self.tag]
        torso.mass, torso.moment = mass, moment
