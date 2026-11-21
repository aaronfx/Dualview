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
CAT_CHAR = 0b10  # collision category of character bodies
CAT_PROP = 0b100  # collision category of props
ALL = pymunk.ShapeFilter.ALL_MASKS()


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
        self._pins: Dict[str, pymunk.Constraint] = {}
        self._ropes: Dict[str, tuple] = {}
        self._mass_moment: Dict[str, Tuple[float, float]] = {}
        self._shapes: Dict[str, pymunk.Shape] = {}
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
                elasticity: float = 0.15, collide_characters: bool = True, com: Vec = (0.0, 0.0), solid: bool = True) -> None:
        body = pymunk.Body(mass, pymunk.moment_for_box(mass, size) + mass * (com[0] ** 2 + com[1] ** 2),
                           body_type=pymunk.Body.DYNAMIC if solid else pymunk.Body.KINEMATIC)
        body.center_of_gravity = com
        body.position, body.angle = pos, angle
        shape = pymunk.Poly.create_box(body, size, radius=1.0)
        shape.friction, shape.elasticity, shape.collision_type = friction, elasticity, CT_PROP
        shape.filter = pymunk.ShapeFilter(categories=CAT_PROP, mask=ALL if collide_characters else ALL ^ CAT_CHAR)
        shape.sensor = not solid  # set dressing: no contact response until it becomes a real body
        self._mass_moment[tag] = (mass, body.moment if solid else pymunk.moment_for_box(mass, size))
        self._shapes[tag] = shape
        self.space.add(body, shape)
        self._tags[shape] = tag
        self._bodies[tag] = body

    def add_capsule(self, tag: str, pos: Vec, a: Vec, b: Vec, radius: float, mass: float, kinematic: bool = True) -> None:
        moment = pymunk.moment_for_segment(mass, a, b, radius)
        body = pymunk.Body(mass, moment, body_type=pymunk.Body.KINEMATIC if kinematic else pymunk.Body.DYNAMIC)
        body.position = pos
        shape = pymunk.Segment(body, a, b, radius)
        shape.friction, shape.elasticity, shape.collision_type = 0.9, 0.0, CT_CHARACTER
        # Physical props must collide with standing *and* prone characters.
        # Props explicitly marked collide_characters=False still exclude CAT_CHAR.
        shape.filter = pymunk.ShapeFilter(categories=CAT_CHAR, mask=ALL)
        self._shapes[tag] = shape
        self._mass_moment[tag] = (mass, moment)
        self.space.add(body, shape)
        self._tags[shape] = tag
        self._bodies[tag] = body

    def add_lever(self, tag: str, center: Vec, size: Vec, mass: float, pivot: Vec, angle: float = 0.0,
                  limits: Optional[Tuple[float, float]] = None, friction: float = 0.8) -> None:
        """A rigid bar pinned to a fixed fulcrum (pry bar / lever arm), optionally with angle stops (world angle, rad)."""
        self.add_box(tag, center, size, mass, angle=angle, friction=friction, elasticity=0.05)
        b = self._bodies[tag]
        j = pymunk.PivotJoint(self.space.static_body, b, pivot)
        j.collide_bodies = False
        self.space.add(j)
        if limits is not None:
            lim = pymunk.RotaryLimitJoint(self.space.static_body, b, limits[0], limits[1])
            self.space.add(lim)

    def add_static_box(self, tag: str, center: Vec, size: Vec, friction: float = 0.9) -> None:
        """Axis-aligned static box (a beam spanning the room depth), recorded as its four edge segments."""
        cx, cy = center
        hx, hy = size[0] / 2, size[1] / 2
        pts = [(cx - hx, cy - hy), (cx + hx, cy - hy), (cx + hx, cy + hy), (cx - hx, cy + hy)]
        s = pymunk.Poly(self.space.static_body, pts)
        s.friction, s.collision_type, s.elasticity = friction, CT_STATIC, 0.0
        self.space.add(s)
        self._tags[s] = tag
        for a, b in zip(pts, pts[1:] + pts[:1]):
            self._static_shapes.append((tag, a, b, 0.0))

    # ------------------------------------------------------------ constraints (grip)
    def add_pin(self, tag: str, anchor_world: Vec) -> Vec:
        """Pin the body's material point that currently lies at `anchor_world` to that fixed world point (a hand grip
        on a static bar). Returns the body-local anchor."""
        b = self._bodies[tag]
        local = b.world_to_local(anchor_world)
        j = pymunk.PivotJoint(self.space.static_body, b, anchor_world, (local.x, local.y))
        j.collide_bodies = False
        self.space.add(j)
        self._pins[tag] = j
        return (local.x, local.y)

    def add_rope(self, name: str, a: str, local_a: Vec, b: str, local_b: Vec, length: float) -> None:
        """A strap/rope between two bodies (or a body and the world, b="world"): slack below `length`, taut at it."""
        ba = self._bodies[a]
        bb = self.space.static_body if b == "world" else self._bodies[b]
        j = pymunk.SlideJoint(ba, bb, local_a, local_b, 0.0, length)
        j.collide_bodies = True
        self.space.add(j)
        self._ropes[name] = (j, a, local_a, b, local_b, length)

    def rope_tension(self, name: str, dt: float) -> float:
        return self._ropes[name][0].impulse / dt if name in self._ropes else 0.0

    def cut_rope(self, name: str) -> None:
        j = self._ropes[name][0]
        if j in self.space.constraints:
            self.space.remove(j)

    def rope_points(self, name: str) -> Tuple[Vec, Vec, float]:
        j, a, la, b, lb, length = self._ropes[name]
        pa = self.body_to_world(a, la)
        pb = lb if b == "world" else self.body_to_world(b, lb)
        return pa, pb, length

    def remove_pin(self, tag: str) -> None:
        j = self._pins.pop(tag, None)
        if j is not None:
            self.space.remove(j)

    def body_to_world(self, tag: str, local: Vec) -> Vec:
        p = self._bodies[tag].local_to_world(local)
        return (p.x, p.y)

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

    def make_dynamic(self, tag: str, vel: Vec = (0.0, 0.0), angvel: float = 0.0) -> None:
        """Return a prop that was carried kinematically to normal dynamics (its own mass and moment)."""
        m, mo = self._mass_moment[tag]
        self._shapes[tag].sensor = False
        self.set_dynamic(tag, vel, angvel, m, mo)

    def set_friction(self, tag: str, friction: float) -> None:
        """Change a body's friction, including its ongoing contacts (Chipmunk caches friction per contact)."""
        sh = self._shapes[tag]
        if sh.friction == friction:
            return
        sh.friction = friction

        def upd(arb: pymunk.Arbiter) -> None:
            a, b = arb.shapes
            arb.friction = a.friction * b.friction

        sh.body.each_arbiter(upd)

    def set_solid_to_props(self, tag: str, solid: bool) -> None:
        """Control prop collision explicitly (e.g. ghosts), independent of posture.

        Ordinary standing, falling and prone characters are solid to props.
        Individual props may opt out via collide_characters=False.
        """
        sh = self._shapes[tag]
        sh.filter = pymunk.ShapeFilter(group=sh.filter.group, categories=CAT_CHAR, mask=ALL if solid else ALL ^ CAT_PROP)

    def set_group(self, tags: List[str], group: int) -> None:
        """Shapes sharing a non-zero group never collide with each other (a lever resting in its fulcrum)."""
        for t in tags:
            sh = self._shapes[t]
            f = sh.filter
            sh.filter = pymunk.ShapeFilter(group=group, categories=f.categories, mask=f.mask)

    def apply_force(self, tag: str, force: Vec, point: Vec) -> None:
        """Force applied at a world point for the next step (character effort on a prop: push, lift, lever)."""
        self._bodies[tag].apply_force_at_world_point(force, point)

    def touching(self, a: str, b: str, vertical_only: bool = False) -> Tuple[bool, float]:
        """Whether bodies a and b are in contact, and the magnitude of the last step's contact impulse between them.
        vertical_only: count only contacts whose normal is mostly vertical (a load resting on top, not a side bump)."""
        ba, bb = self._bodies[a], self._bodies.get(b)
        found, imp = [False], [0.0]

        def visit(arb: pymunk.Arbiter) -> None:
            s1, s2 = arb.shapes
            cps = arb.contact_point_set
            if (s1.body is bb or s2.body is bb) and cps.points:
                if vertical_only and abs(cps.normal.y) < 0.6:
                    return
                found[0] = True
                imp[0] += abs(arb.total_impulse.length)

        if bb is not None:
            ba.each_arbiter(visit)
        return found[0], imp[0]

    def local_point(self, tag: str, world: Vec) -> Vec:
        p = self._bodies[tag].world_to_local(world)
        return (p.x, p.y)

    def tags(self) -> List[str]:
        return list(self._bodies)

    def apply_impulse(self, tag: str, impulse: Vec) -> None:
        """Impulse through the centre of mass (character muscular effort, e.g. a pumping kick while hanging)."""
        b = self._bodies[tag]
        b.apply_impulse_at_world_point(impulse, b.local_to_world(b.center_of_gravity))

    def set_angular_velocity(self, tag: str, w: float) -> None:
        self._bodies[tag].angular_velocity = w

    def apply_torque(self, tag: str, torque: float) -> None:
        """Apply a bounded active-muscle torque to a dynamic body for the next step."""
        body = self._bodies[tag]
        if body.body_type != pymunk.Body.DYNAMIC:
            raise ValueError(f"{tag}: torque requires a dynamic body")
        if not math.isfinite(torque):
            raise ValueError(f"{tag}: torque must be finite")
        body.torque += torque

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
