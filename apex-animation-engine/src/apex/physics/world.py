"""Physics interface owned by the engine, with a pymunk (Chipmunk2D) implementation.

Animation code only talks to `PhysicsWorld`; swapping the backend (e.g. Box2D, a 3D engine) means
re-implementing this class, not the character or scene code.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import pymunk

from ..core.mathx import Vec

CT_STATIC, CT_CHARACTER, CT_PROP = 1, 2, 3


@dataclass
class ContactEvent:
    t: float
    a: str  # tag of the moving body
    b: str  # tag of the other shape
    point: Vec
    normal: Vec  # surface normal pointing away from `b` toward `a`
    normal_speed: float  # approach speed along the normal (>0 = moving into the surface)


@dataclass
class RayHit:
    point: Vec
    normal: Vec
    fraction: float
    tag: str


@dataclass
class BodyState:
    pos: Vec
    angle: float
    vel: Vec
    angvel: float


class PhysicsWorld:
    """Deterministic fixed-step rigid-body world."""

    def __init__(self, gravity: Vec = (0.0, -1568.0), iterations: int = 20):
        self.space = pymunk.Space()
        self.space.iterations = iterations
        self.space.gravity = gravity
        self.t = 0.0
        self._tags: Dict[pymunk.Shape, str] = {}
        self._bodies: Dict[str, pymunk.Body] = {}
        self._static_shapes: List[Tuple[str, Vec, Vec, float]] = []
        self.events: List[ContactEvent] = []
        self._pending: List[ContactEvent] = []
        self.space.on_collision(None, None, begin=self._on_begin)

    # ------------------------------------------------------------ construction
    def add_static_segment(self, tag: str, a: Vec, b: Vec, radius: float = 1.0, friction: float = 0.9) -> None:
        s = pymunk.Segment(self.space.static_body, a, b, radius)
        s.friction, s.collision_type, s.elasticity = friction, CT_STATIC, 0.0
        self.space.add(s)
        self._tags[s] = tag
        self._static_shapes.append((tag, a, b, radius))

    def add_box(self, tag: str, pos: Vec, size: Vec, mass: float, angle: float = 0.0, friction: float = 0.6,
                elasticity: float = 0.15) -> None:
        body = pymunk.Body(mass, pymunk.moment_for_box(mass, size))
        body.position, body.angle = pos, angle
        shape = pymunk.Poly.create_box(body, size, radius=1.0)
        shape.friction, shape.elasticity, shape.collision_type = friction, elasticity, CT_PROP
        self.space.add(body, shape)
        self._tags[shape] = tag
        self._bodies[tag] = body

    def add_capsule(self, tag: str, pos: Vec, a: Vec, b: Vec, radius: float, mass: float, kinematic: bool = True) -> None:
        moment = pymunk.moment_for_segment(mass, a, b, radius)
        body = pymunk.Body(mass, moment, body_type=pymunk.Body.KINEMATIC if kinematic else pymunk.Body.DYNAMIC)
        body.position = pos
        shape = pymunk.Segment(body, a, b, radius)
        shape.friction, shape.elasticity, shape.collision_type = 0.9, 0.0, CT_CHARACTER
        self.space.add(body, shape)
        self._tags[shape] = tag
        self._bodies[tag] = body

    # ------------------------------------------------------------ control
    def set_gravity(self, g: Vec) -> None:
        self.space.gravity = g

    def state(self, tag: str) -> BodyState:
        b = self._bodies[tag]
        return BodyState((b.position.x, b.position.y), b.angle, (b.velocity.x, b.velocity.y), b.angular_velocity)

    def is_kinematic(self, tag: str) -> bool:
        return self._bodies[tag].body_type == pymunk.Body.KINEMATIC

    def set_kinematic(self, tag: str, pos: Vec, angle: float, vel: Vec = (0.0, 0.0), angvel: float = 0.0) -> None:
        b = self._bodies[tag]
        if b.body_type != pymunk.Body.KINEMATIC:
            b.body_type = pymunk.Body.KINEMATIC
        b.position, b.angle, b.velocity, b.angular_velocity = pos, angle, vel, angvel
        self.space.reindex_shapes_for_body(b)

    def set_dynamic(self, tag: str, vel: Vec, angvel: float, mass: float, moment: float) -> None:
        b = self._bodies[tag]
        if b.body_type != pymunk.Body.DYNAMIC:
            b.body_type = pymunk.Body.DYNAMIC
            b.mass, b.moment = mass, moment
        b.velocity, b.angular_velocity = vel, angvel

    def set_angular_velocity(self, tag: str, w: float) -> None:
        self._bodies[tag].angular_velocity = w

    # ------------------------------------------------------------ queries
    def raycast(self, a: Vec, b: Vec, radius: float = 0.0, statics_only: bool = True) -> Optional[RayHit]:
        best = None
        for info in self.space.segment_query(a, b, radius, pymunk.ShapeFilter()):
            if statics_only and info.shape.body.body_type != pymunk.Body.STATIC:
                continue
            if best is None or info.alpha < best.alpha:
                best = info
        if best is None:
            return None
        return RayHit((best.point.x, best.point.y), (best.normal.x, best.normal.y), best.alpha, self._tags.get(best.shape, "?"))

    def static_segments(self) -> List[Tuple[str, Vec, Vec, float]]:
        return list(self._static_shapes)

    # ------------------------------------------------------------ stepping
    def _on_begin(self, arb: pymunk.Arbiter, space: pymunk.Space, data) -> None:
        sa, sb = arb.shapes
        ta, tb = self._tags.get(sa, "?"), self._tags.get(sb, "?")
        # orient so that `a` is the non-static participant
        n = arb.normal  # points from shape a to shape b
        if sa.body.body_type == pymunk.Body.STATIC:
            sa, sb, ta, tb, n = sb, sa, tb, ta, -n
        pts = arb.contact_point_set.points
        p = pts[0].point_a if pts else sa.body.position
        rel = sa.body.velocity - sb.body.velocity
        normal_away = (-n.x, -n.y)  # surface normal pointing from b toward a
        approach = -(rel.x * normal_away[0] + rel.y * normal_away[1])
        self._pending.append(ContactEvent(self.t, ta, tb, (p.x, p.y), normal_away, approach))

    def step(self, dt: float) -> List[ContactEvent]:
        self._pending = []
        self.space.step(dt)
        self.t += dt
        ev = [e for e in self._pending]
        for e in ev:
            e.t = self.t
        self.events.extend(ev)
        return ev


def capsule_moment(mass: float, length: float, radius: float) -> float:
    return pymunk.moment_for_segment(mass, (0, -length / 2), (0, length / 2), radius)
