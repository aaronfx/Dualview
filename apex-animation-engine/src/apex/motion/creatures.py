"""Composite creatures (Milestone 5): glyph limbs on a glyph body, held together by joints, moved by bounded forces.

Every part is an ordinary glyph prop in the physics world, so a creature collides with structures, props and the
characters' bounded-force bodies like anything else. The creature itself only adds:
- pivot joints (body to each part) and rotary springs that a gait drives (legs and arms swing in turn, paced by the
  distance the body has travelled; tails and heads are held loosely);
- a drive: a bounded horizontal force that follows the creature's path, a bounded lift that holds its centre at its
  standing height, and a bounded torque that keeps it upright (a strong enough blow still knocks it about);
- tearing: a contact impulse on any part at or above `breaks` removes every joint and the drive; the parts fall as
  free props.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pymunk

from ..core.mathx import clamp

GROUP_BASE = 7000  # shape groups for creatures (parts of one creature never collide with each other)


class CreatureDriver:
    def __init__(self, spec, world, idx: int):
        self.spec, self.world = spec, world
        self.cid = spec.id
        self.body_tag = f"{spec.id}.body"
        self.part_tags = [f"{spec.id}.{k}" for k in range(len(spec.parts))]
        world.set_group([self.body_tag] + self.part_tags, GROUP_BASE + idx)
        B = world._bodies[self.body_tag]
        self.constraints: List[pymunk.Constraint] = []
        self.springs: List[Tuple[pymunk.DampedRotarySpring, object]] = []
        self.anchors: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []  # (on the body, on the part), local frames
        for tag, pt in zip(self.part_tags, spec.parts):
            P = world._bodies[tag]
            anchor = (spec.position[0] + pt.at[0], spec.position[1] + pt.at[1])
            j = pymunk.PivotJoint(B, P, anchor)
            j.collide_bodies = False
            stiff = {"leg": 2.2e5, "arm": 1.2e5, "tail": 3e4, "head": 1.5e5, "eye": 2e5}[pt.role] * pt.mass
            sp = pymunk.DampedRotarySpring(B, P, 0.0, stiff, 0.18 * math.sqrt(stiff * pt.mass * 400.0))
            world.space.add(j, sp)
            self.constraints += [j, sp]
            self.springs.append((sp, pt))
            self.anchors.append((tuple(B.world_to_local(anchor)), tuple(P.world_to_local(anchor))))
        self.mass = B.mass + sum(world._bodies[t].mass for t in self.part_tags)
        self.phase = 0.0
        self.x_prev: Optional[float] = None
        self.broken_t: Optional[float] = None
        path = sorted(spec.path) or [(0.0, spec.position[0])]
        self.pt, self.px = np.array([p[0] for p in path]), np.array([p[1] for p in path])
        self.drive_log: List[Tuple[float, float, float, float]] = []  # (t, Fx, Fy, torque) actually applied

    def target(self, t: float) -> Tuple[float, float]:
        x = float(np.interp(t, self.pt, self.px))
        if len(self.pt) > 1:
            i = int(np.clip(np.searchsorted(self.pt, t), 1, len(self.pt) - 1))
            v = (self.px[i] - self.px[i - 1]) / max(1e-6, self.pt[i] - self.pt[i - 1]) if self.pt[0] <= t <= self.pt[-1] else 0.0
        else:
            v = 0.0
        return x, v

    def tick(self, t: float, g: Tuple[float, float]) -> None:
        """Before the physics step: the drive forces and the gait."""
        if self.broken_t is not None:
            return
        sp = self.spec
        B = self.world._bodies[self.body_tag]
        c = B.local_to_world(B.center_of_gravity)
        xt, vt = self.target(t)
        # horizontal: follow the path (a critically damped pull, bounded by the creature's strength)
        fx = clamp(self.mass * (36.0 * (xt - c.x) + 12.0 * (vt - B.velocity.x)), -sp.max_force, sp.max_force)
        # vertical: hold the centre at standing height, carrying the whole creature's weight (bounded)
        gm = math.hypot(*g)
        fy = clamp(self.mass * (gm + 60.0 * (sp.height - c.y) - 14.0 * B.velocity.y), 0.0, sp.max_lift)
        B.apply_force_at_world_point((fx, fy), c)
        tq = clamp(-B.moment * (80.0 * math.remainder(B.angle, 2 * math.pi) + 16.0 * B.angular_velocity), -0.6 * sp.max_force * sp.size[0],
                   0.6 * sp.max_force * sp.size[0])
        B.torque += tq
        self.drive_log.append((t, fx, fy, tq))
        # gait: the swing phase advances with the distance travelled
        if self.x_prev is not None:
            self.phase += abs(c.x - self.x_prev) / sp.stride * math.pi
        self.x_prev = c.x
        amp = clamp(abs(B.velocity.x) / 60.0, 0.0, 1.0)  # standing still, the legs come to rest
        for spring, pt in self.springs:
            if pt.role in ("leg", "arm"):
                spring.rest_angle = amp * pt.swing * math.sin(self.phase + pt.phase)
            elif pt.role == "tail":
                spring.rest_angle = 0.25 * math.sin(0.6 * self.phase + pt.phase)

    def after_step(self, t: float, events: list, Event) -> None:
        """After the physics step: a hard enough blow on any part tears the creature apart."""
        if self.broken_t is not None or self.spec.breaks is None:
            return
        hits = [(self.world.step_impulse.get(tag, (0.0, None, 0.0)), tag) for tag in [self.body_tag] + self.part_tags]
        (j, pt, _), tag = max(hits, key=lambda h: h[0][0])
        if j < self.spec.breaks:
            return
        self.world.space.remove(*self.constraints)
        self.constraints = []
        self.broken_t = t
        events.append(Event(t, "creature_break", self.cid, {"creature": self.cid, "impulse": j, "threshold": self.spec.breaks,
                                                            "part": tag, "point": tuple(pt) if pt else None}))

    def joint_error(self, tracks: Dict[str, np.ndarray], i: int) -> float:
        """How far apart the two ends of the worst joint are in track sample i (0 for a creature that holds together)."""
        b = tracks[self.body_tag][i]
        worst = 0.0
        for tag, (la, lp) in zip(self.part_tags, self.anchors):
            p = tracks[tag][i]
            wa = (b[0] + la[0] * math.cos(b[2]) - la[1] * math.sin(b[2]), b[1] + la[0] * math.sin(b[2]) + la[1] * math.cos(b[2]))
            wp = (p[0] + lp[0] * math.cos(p[2]) - lp[1] * math.sin(p[2]), p[1] + lp[0] * math.sin(p[2]) + lp[1] * math.cos(p[2]))
            worst = max(worst, math.dist(wa, wp))
        return worst
