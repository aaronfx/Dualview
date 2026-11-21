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

CT_STATIC, CT_CHARACTER, CT_PROP, CT_PROXY = 1, 2, 3, 4
CAT_PROXY = 0b10000  # a standing character's bounded-force body (collides with props only)
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
        self._extra: Dict[str, List[pymunk.Shape]] = {}  # further shapes of a compound body (a glyph's strokes)
        self.events: List[ContactEvent] = []
        self._pending: List[ContactEvent] = []
        self.space.on_collision(None, None, begin=self._on_begin, post_solve=self._post_solve)
        self.step_impulse: Dict[str, Tuple[float, Vec, float]] = {}  # tag -> (contact impulse this step, main point, largest)
        self.inactive: set = set()  # bodies out of play: pieces before their prop breaks, a prop after it has broken
        self._saved_filter: Dict[str, tuple] = {}
        # bounded-force character bodies (see add_proxy): contacts with props filtered by depth and by what the
        # character is doing with that prop (carrying it, pushing it, has just thrown it)
        self._proxies: Dict[str, tuple] = {}
        self.proxy_ignore: set = set()  # (character tag, prop tag) pairs whose contact is handled elsewhere
        self.depth: Dict[str, Tuple[float, float]] = {}  # tag -> (depth lane z, half depth)
        self.proxy_grace: set = set()
        self.in_flight: set = set()  # thrown props: their hits are resolved by impulse exchange (controller), not here  # (character, prop) pairs already overlapping when the body became solid
        self.space.on_collision(CT_PROXY, CT_PROP, pre_solve=self._proxy_pre, separate=self._proxy_sep)
        # a carried prop is moved kinematically (no mass of its own in the solver): it must not shove other props with
        # unbounded force, so it passes them while carried (structures still stop it: see the controller)
        self.carried: set = set()
        self.space.on_collision(CT_PROP, CT_PROP, pre_solve=self._prop_pre)

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
        shape.filter = pymunk.ShapeFilter(categories=CAT_PROP, mask=ALL if collide_characters else ALL ^ (CAT_CHAR | CAT_PROXY))
        shape.sensor = not solid  # set dressing: no contact response until it becomes a real body
        self._mass_moment[tag] = (mass, body.moment if solid else pymunk.moment_for_box(mass, size))
        self._shapes[tag] = shape
        self.space.add(body, shape)
        self._tags[shape] = tag
        self._bodies[tag] = body

    def add_compound(self, tag: str, pos: Vec, segs: List[Tuple[Vec, Vec]], radius: float, masses: List[float], com: Vec,
                     angle: float = 0.0, friction: float = 0.6, elasticity: float = 0.2, collide_characters: bool = True,
                     solid: bool = True) -> None:
        """A dynamic body made of rounded segments (a glyph's strokes), mass spread along them."""
        mass = sum(masses)
        moment = sum(pymunk.moment_for_segment(m, (a[0] - com[0], a[1] - com[1]), (b[0] - com[0], b[1] - com[1]), radius)
                     for (a, b), m in zip(segs, masses))
        body = pymunk.Body(mass, moment, body_type=pymunk.Body.DYNAMIC if solid else pymunk.Body.KINEMATIC)
        body.center_of_gravity = com
        body.position, body.angle = pos, angle
        shapes = []
        for a, b in segs:
            sh = pymunk.Segment(body, a, b, radius)
            sh.friction, sh.elasticity, sh.collision_type = friction, elasticity, CT_PROP
            sh.filter = pymunk.ShapeFilter(categories=CAT_PROP, mask=ALL if collide_characters else ALL ^ (CAT_CHAR | CAT_PROXY))
            sh.sensor = not solid
            shapes.append(sh)
            self._tags[sh] = tag
        self._mass_moment[tag] = (mass, moment)
        self._shapes[tag] = shapes[0]
        self._extra[tag] = shapes[1:]
        self.space.add(body, *shapes)
        self._bodies[tag] = body

    def shapes_of(self, tag: str) -> List[pymunk.Shape]:
        return [self._shapes[tag]] + self._extra.get(tag, [])

    def add_proxy(self, owner: str, a: Vec, b: Vec, radius: float, mass: float, max_force: float) -> None:
        """A standing character's physical body for contact with props: a dynamic capsule (the character's mass, no
        rotation, no gravity of its own) tied to the kinematic character by a joint whose force is bounded by the
        character's strength. A prop can push it (and the character is then displaced or blocked, see the controller),
        and it pushes a prop with at most that force: no ghosting, and no infinite-mass push either."""
        ob = self._bodies[owner]
        body = pymunk.Body(mass, float("inf"))
        body.position = ob.position
        body.velocity_func = lambda bd, g, damping, dt: pymunk.Body.update_velocity(bd, (0.0, 0.0), damping, dt)
        shape = pymunk.Segment(body, a, b, radius)
        shape.friction, shape.elasticity, shape.collision_type = 0.7, 0.0, CT_PROXY
        shape.filter = pymunk.ShapeFilter(categories=CAT_PROXY, mask=0)  # enabled while the character stands
        joint = pymunk.PivotJoint(ob, body, (0.0, 0.0), (0.0, 0.0))
        joint.max_force, joint.max_bias, joint.collide_bodies = max_force, 2500.0, False
        self.space.add(body, shape, joint)
        self._tags[shape] = owner + "~body"
        self._proxies[owner] = (body, shape, joint)

    def proxy_set(self, owner: str, active: bool, max_force: float, low: Optional[float] = None) -> None:
        """`low`: the body's lower end in the character's frame (it stays at knee height above the floor when the
        character crouches, instead of sinking with the pelvis)."""
        body, shape, joint = self._proxies[owner]
        if low is not None and abs(shape.a.y - low) > 0.5:
            shape.unsafe_set_endpoints((0.0, low), shape.b)
        joint.max_force = max_force if active else 0.0  # an inactive body (airborne, lying) exerts nothing on the character
        want = CAT_PROP if active else 0
        if shape.filter.mask != want:
            if active:  # (re)activate at the character, at rest
                ob = self._bodies[owner]
                body.position, body.velocity = ob.position, ob.velocity
                self.space.reindex_shapes_for_body(body)
            shape.filter = pymunk.ShapeFilter(categories=CAT_PROXY, mask=want)
            if active:  # never resolve an interpenetration that already exists by force: that pair passes in depth
                for info in self.space.shape_query(shape):
                    if info.shape.collision_type == CT_PROP:
                        self.proxy_grace.add((owner, self._tags.get(info.shape)))

    def proxy_offset(self, owner: str) -> Tuple[Vec, Vec]:
        """(offset of the body from the character, its velocity)."""
        body = self._proxies[owner][0]
        ob = self._bodies[owner]
        return (body.position.x - ob.position.x, body.position.y - ob.position.y), (body.velocity.x, body.velocity.y)

    def proxy_contact(self, owner: str) -> Optional[str]:
        """The prop the character's body is touching (None if none)."""
        body = self._proxies[owner][0]
        hit = [None]

        def visit(arb: pymunk.Arbiter) -> None:
            for sh in arb.shapes:
                if sh.body is not body and sh.collision_type == CT_PROP:
                    hit[0] = self._tags.get(sh)
        body.each_arbiter(visit)
        return hit[0]

    def proxy_force(self, owner: str, dt: float) -> float:
        return self._proxies[owner][2].impulse / dt

    def _proxy_pre(self, arb: pymunk.Arbiter, space: pymunk.Space, data) -> None:
        sa, sb = arb.shapes
        ta, tb = self._tags.get(sa, "?"), self._tags.get(sb, "?")
        if sa.collision_type != CT_PROXY:
            ta, tb = tb, ta
        owner = ta[:-5]  # strip "~body"
        if (owner, tb) in self.proxy_ignore or (owner, tb) in self.proxy_grace or tb in self.in_flight or tb in self.carried:
            # carried (a wielded weapon) and thrown props reach bodies through the combat rules (hits, impulses)
            arb.process_collision = False
            return
        za, ha = self.depth.get(owner, (0.0, 14.0))
        zb, hb = self.depth.get(tb, (0.0, 30.0))
        if abs(za - zb) >= ha + hb:  # in different depth lanes: they pass one in front of the other
            arb.process_collision = False

    def _prop_pre(self, arb: pymunk.Arbiter, space: pymunk.Space, data) -> None:
        sa, sb = arb.shapes
        if self._tags.get(sa) in self.carried or self._tags.get(sb) in self.carried:
            arb.process_collision = False

    def _proxy_sep(self, arb: pymunk.Arbiter, space: pymunk.Space, data) -> None:
        sa, sb = arb.shapes
        ta, tb = self._tags.get(sa, "?"), self._tags.get(sb, "?")
        if sa.collision_type != CT_PROXY:
            ta, tb = tb, ta
        self.proxy_grace.discard((ta[:-5], tb))  # once apart, they collide normally

    def add_capsule(self, tag: str, pos: Vec, a: Vec, b: Vec, radius: float, mass: float, kinematic: bool = True) -> None:
        moment = pymunk.moment_for_segment(mass, a, b, radius)
        body = pymunk.Body(mass, moment, body_type=pymunk.Body.KINEMATIC if kinematic else pymunk.Body.DYNAMIC)
        body.position = pos
        shape = pymunk.Segment(body, a, b, radius)
        shape.friction, shape.elasticity, shape.collision_type = 0.9, 0.0, CT_CHARACTER
        shape.filter = pymunk.ShapeFilter(categories=CAT_CHAR, mask=ALL ^ CAT_PROP)  # standing bodies pass props by
        self._shapes[tag] = shape
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

    def add_slab(self, tag: str, pts: List[Vec], friction: float = 0.9) -> None:
        """Solid mass behind a room surface (not a surface of its own): a body pushed into a thin surface segment
        (a piece born overlapping the floor, a fast fragment) is pushed back out instead of tunnelling through."""
        s = pymunk.Poly(self.space.static_body, pts)
        s.friction, s.collision_type, s.elasticity = friction, CT_STATIC, 0.0
        self.space.add(s)
        self._tags[s] = tag

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

    def teleport(self, tag: str, pos: Vec, angle: float, vel: Vec, angvel: float) -> None:
        """Move a body (a portal): position, angle and velocity at once, keeping its type and mass."""
        b = self._bodies[tag]
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
        for sh in self.shapes_of(tag):
            sh.sensor = False
        self.set_dynamic(tag, vel, angvel, m, mo)

    def set_friction(self, tag: str, friction: float) -> None:
        """Change a body's friction, including its ongoing contacts (Chipmunk caches friction per contact)."""
        sh = self._shapes[tag]
        if sh.friction == friction:
            return
        for x in self.shapes_of(tag):
            x.friction = friction

        def upd(arb: pymunk.Arbiter) -> None:
            a, b = arb.shapes
            arb.friction = a.friction * b.friction

        sh.body.each_arbiter(upd)

    def set_solid_to_props(self, tag: str, solid: bool) -> None:
        """A standing character passes in front of props (2.5D); a lying one is solid, so props can come to rest on it."""
        sh = self._shapes[tag]
        sh.filter = pymunk.ShapeFilter(group=sh.filter.group, categories=CAT_CHAR, mask=ALL if solid else ALL ^ CAT_PROP)

    def set_group(self, tags: List[str], group: int) -> None:
        """Shapes sharing a non-zero group never collide with each other (a lever resting in its fulcrum)."""
        for t in tags:
            for sh in self.shapes_of(t):
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

    def apply_impulse_at(self, tag: str, impulse: Vec, point: Vec) -> None:
        """Impulse at a world point (changes both the velocity and the spin of a rigid body)."""
        self._bodies[tag].apply_impulse_at_world_point(impulse, point)

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
        for own, other in ((ta, tb), (tb, ta)):  # a contact the body rule ignores is not a contact (no event, no sound)
            if own.endswith("~body"):
                o = own[:-5]
                if (o, other) in self.proxy_ignore or (o, other) in self.proxy_grace or other in self.in_flight or other in self.carried:
                    return
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

    def _post_solve(self, arb: pymunk.Arbiter, space: pymunk.Space, data) -> None:
        j = arb.total_impulse.length
        if j <= 0.0:
            return
        pts = arb.contact_point_set.points
        p = (pts[0].point_a.x, pts[0].point_a.y) if pts else (0.0, 0.0)
        for sh in arb.shapes:
            tag = self._tags.get(sh)
            if tag is not None and sh.body.body_type == pymunk.Body.DYNAMIC:
                # a body made of several shapes (a glyph's strokes) takes one blow through all of them: sum them
                j0, p0, jm = self.step_impulse.get(tag, (0.0, p, 0.0))
                self.step_impulse[tag] = (j0 + j, p if j > jm else p0, max(jm, j))

    # ------------------------------------------------------------ out of play (breakables)
    def deactivate(self, tag: str) -> None:
        """Take a body out of play: it neither collides nor moves (a piece before its prop breaks; a broken prop)."""
        if tag in self.inactive:
            return
        shapes = self.shapes_of(tag)
        self._saved_filter[tag] = [(sh.filter, sh.sensor) for sh in shapes]
        for sh in shapes:
            sh.filter = pymunk.ShapeFilter(categories=0, mask=0)
            sh.sensor = True
        st = self.state(tag)
        self.set_kinematic(tag, st.pos, st.angle)
        self.inactive.add(tag)

    def activate(self, tag: str, pos: Vec, angle: float, vel: Vec, angvel: float) -> None:
        """Bring a body into play as a dynamic body with this pose and motion."""
        for sh, (flt, sen) in zip(self.shapes_of(tag), self._saved_filter.pop(tag, [])):
            sh.filter, sh.sensor = flt, sen
        self.inactive.discard(tag)
        self.set_kinematic(tag, pos, angle)
        m, mo = self._mass_moment[tag]
        self.set_dynamic(tag, vel, angvel, m, mo)

    def blockers(self, tag: str, segs: List[Tuple[Vec, Vec]], radius: float, offset: Vec = (0.0, 0.0)) -> List[str]:
        """What the body would overlap with these segments (its own frame) in place of its shapes, moved by `offset`:
        tags of characters, structures and other props (its own shapes and out-of-play bodies are ignored)."""
        body = self._bodies[tag]
        p0 = body.position
        body.position = (p0.x + offset[0], p0.y + offset[1])
        out = []
        try:
            for a, b in segs:
                probe = pymunk.Segment(body, a, b, radius)
                probe.filter = pymunk.ShapeFilter(categories=CAT_PROP, mask=ALL)
                probe.cache_bb()
                for hit in self.space.shape_query(probe):
                    other = hit.shape
                    t = self._tags.get(other, "")
                    if other is None or other.body is body or other.sensor or t in self.inactive:
                        continue
                    if t.endswith("~body"):  # a character's physical body stands for that character...
                        o = t[:-5]
                        if (o, tag) in self.proxy_ignore or tag in self.carried or tag in self.in_flight:
                            continue  # ...except for a prop it is holding or handling (the body rule ignores those)
                        t = o
                    out.append(t)
        finally:
            body.position = p0
        return out

    def free_for(self, tag: str, segs: List[Tuple[Vec, Vec]], radius: float) -> bool:
        """Would this body, with these segments (its own frame) in place of its shapes, overlap a character, a static
        structure or another prop? (Its own shapes and out-of-play bodies are ignored.)"""
        body = self._bodies[tag]
        for a, b in segs:
            probe = pymunk.Segment(body, a, b, radius)
            probe.filter = pymunk.ShapeFilter(categories=CAT_PROP, mask=ALL)
            probe.cache_bb()
            for hit in self.space.shape_query(probe):
                other = hit.shape
                if other is None or other.body is body or other.sensor or self._tags.get(other, "").endswith("~body"):
                    continue
                if self._tags.get(other) in self.inactive:
                    continue
                return False
        return True

    def reshape(self, tag: str, segs: List[Tuple[Vec, Vec]], radius: float, masses: List[float], com: Vec,
                nudge: Vec = (0.0, 0.0)) -> Tuple[float, float]:
        """Replace a compound body's segments (a morph). Mass is kept; the centre of mass stays where it is, its
        velocity is kept and the spin changes so that the angular momentum is conserved. Returns (I before, I after)."""
        body = self._bodies[tag]
        old = self.shapes_of(tag)
        tmpl = old[0]
        c_world = body.local_to_world(body.center_of_gravity)
        I0, w0 = body.moment, body.angular_velocity
        v = body.velocity
        for sh in old:
            self._tags.pop(sh, None)
        self.space.remove(*old)
        shapes = []
        for a, b in segs:
            sh = pymunk.Segment(body, a, b, radius)
            sh.friction, sh.elasticity, sh.collision_type, sh.filter = tmpl.friction, tmpl.elasticity, tmpl.collision_type, tmpl.filter
            shapes.append(sh)
            self._tags[sh] = tag
        moment = sum(pymunk.moment_for_segment(m, (a[0] - com[0], a[1] - com[1]), (b[0] - com[0], b[1] - com[1]), radius)
                     for (a, b), m in zip(segs, masses))
        self._shapes[tag], self._extra[tag] = shapes[0], shapes[1:]
        self._mass_moment[tag] = (sum(masses), moment)
        body.center_of_gravity = com
        body.moment = moment
        ca, sa = math.cos(body.angle), math.sin(body.angle)
        body.position = (c_world.x + nudge[0] - (com[0] * ca - com[1] * sa), c_world.y + nudge[1] - (com[0] * sa + com[1] * ca))
        body.velocity, body.angular_velocity = v, w0 * I0 / moment
        self.space.add(*shapes)
        self.space.reindex_shapes_for_body(body)
        return I0, moment

    def step(self, dt: float) -> List[ContactEvent]:
        self._pending = []
        self.step_impulse = {}
        self.space.step(dt)
        self.t += dt
        ev = [e for e in self._pending]
        for e in ev:
            e.t = self.t
        self.events.extend(ev)
        return ev


def capsule_moment(mass: float, length: float, radius: float) -> float:
    return pymunk.moment_for_segment(mass, (0, -length / 2), (0, length / 2), radius)
