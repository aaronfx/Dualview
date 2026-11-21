"""Experimental jointed fall limb simulation with a decoupled physics space.

The story's authoritative torso and all props stay in PhysicsWorld.  A
kinematic proxy mirrors the torso in this auxiliary Pymunk space; dynamic
head/arm/leg segments respond to gravity, joint limits and floor contact.
This prevents limb impacts from changing pinned/load/lever story events.
This is an opt-in prototype, not a bidirectionally coupled final ragdoll.
"""
from __future__ import annotations

import math
from typing import Dict, List

import pymunk

from ..rig.stickman import Pose, StickmanRig, base_pose
from .world import PhysicsWorld


class ArticulatedFall:
    """Temporary articulated overlay for an already dynamic character torso."""

    def __init__(self, world: PhysicsWorld, tag: str, rig: StickmanRig, facing: float):
        self.world, self.tag, self.rig, self.facing = world, tag, rig, facing
        self.space = pymunk.Space()
        self.space.iterations = 25
        self.space.gravity = world.space.gravity
        self.parts: Dict[str, pymunk.Body] = {}
        self.shapes: List[pymunk.Shape] = []
        self.constraints: List[pymunk.Constraint] = []
        self.samples: list[dict] = []
        self.last_t: float | None = None

        # Copy only real static surfaces; changes to the interactive prop
        # contacts must not leak from the overlay into the authoritative scene.
        for _, a, b, radius in world.static_segments():
            shape = pymunk.Segment(self.space.static_body, a, b, radius)
            shape.friction = 0.95
            self.space.add(shape)

        state = world.state(tag)
        self.proxy = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.proxy.position = state.pos
        self.proxy.angle = state.angle
        self.proxy.velocity = state.vel
        self.proxy.angular_velocity = state.angvel
        self.space.add(self.proxy)
        pose = Pose(root=state.pos, body_angle=state.angle, facing=facing, local=base_pose())
        joints = rig.world_joints(pose)

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
        group = 20000 + sum((i + 1) * ord(ch) for i, ch in enumerate(tag))
        parents: Dict[str, pymunk.Body] = {"torso": self.proxy}
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
            shape.filter = pymunk.ShapeFilter(group=group)
            self.space.add(part, shape)
            self.parts[name] = part
            self.shapes.append(shape)

            parent = parents[parent_name]
            pivot = pymunk.PivotJoint(parent, part, a)
            pivot.collide_bodies = False
            delta = math.atan2(math.sin(part.angle - parent.angle), math.cos(part.angle - parent.angle))
            limit = pymunk.RotaryLimitJoint(parent, part, delta - freedom, delta + freedom)
            spring = pymunk.DampedRotarySpring(parent, part, delta, 1200.0, 220.0)
            self.space.add(pivot, limit, spring)
            self.constraints.extend([pivot, limit, spring])
            parents[name] = part

    def record(self, t: float) -> None:
        """Step the limb-only simulation to fixed t and store playback angles."""
        torso = self.world.state(self.tag)
        self.proxy.position = torso.pos
        self.proxy.angle = torso.angle
        self.proxy.velocity = torso.vel
        self.proxy.angular_velocity = torso.angvel
        self.space.gravity = self.world.space.gravity
        if self.last_t is not None:
            dt = t - self.last_t
            if dt < -1e-9:
                raise ValueError("ragdoll samples must be recorded in ascending time")
            if dt > 0:
                self.space.step(dt)
        self.last_t = t
        self.samples.append({"t": float(t), "angles": {name: float(body.angle) for name, body in self.parts.items()}})

    def cleanup(self) -> None:
        """The auxiliary solver can be discarded without touching real props."""
        self.space.remove(*self.constraints)
        self.space.remove(*self.shapes)
        self.space.remove(*self.parts.values())
        self.space.remove(self.proxy)
