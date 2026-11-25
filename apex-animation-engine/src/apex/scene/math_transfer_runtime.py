"""Authenticate mathematical transitions against native simulation events.

No scheduled time or authored final answer can independently authorize a
rewrite. This runtime is opt-in and leaves ordinary scenes untouched.
"""
from __future__ import annotations
import math
from .transposition_stage import compile_native_transfer


class MathTransferRuntime:
    def __init__(self, spec, props, world):
        self.spec, self.world = spec, world
        self.stage, expected = compile_native_transfer(spec)
        actual = {p.id: p for p in props}
        if any(actual.get(p.id) != p for p in expected):
            raise ValueError("math transfer props do not match the proven native compiler")
        self.term, self.eq, self.rhs, self.combined = (expected[i].id for i in (1, 2, 3, 4))
        self.term_width, self.eq_width = expected[1].size[0], expected[2].size[0]
        self.combined_pos = expected[4].position
        self.rhs_pos = expected[3].position
        self.world.deactivate(self.combined)
        self.visibility = {self.combined: (math.inf, math.inf)}
        self.crossed = False
        self.transferred_at = None
        self.evaluated = False
        self.cursor = 0
        self.pick = self.placed = False
        self.requested_at = None

    def tick(self, t, controllers, events, Event):
        actor = controllers.get(self.spec.actor)
        if actor is None:
            raise ValueError("math transfer actor is not placed")
        w = self.world
        # Only actual native pickup, placement and pointing events count.
        for e in events[self.cursor:]:
            if e.character != self.spec.actor:
                continue
            if e.type == "pick_up" and e.data.get("prop") == self.term:
                self.pick = True
            elif e.type == "place" and e.data.get("prop") == self.term:
                self.placed = True
            elif e.type == "point" and e.data.get("target") == "prop:" + self.term:
                self.requested_at = e.t
        self.cursor = len(events)
        if self.evaluated:
            return
        st = w.state(self.term)
        if (not self.crossed and self.pick and actor.carrying == self.term
                and st.pos[0] - self.term_width / 2 > w.state(self.eq).pos[0] + self.eq_width / 2 - 1):
            self.crossed = True
            events.append(Event(t, "math_crossed", self.spec.actor, {"prop": self.term, "point": st.pos}))
        if (self.crossed and self.placed and self.transferred_at is None
                and actor.carrying is None and w.is_kinematic(self.term)
                and w.glyph_now[self.term] == self.stage.plan.destination.text
                and math.dist(st.pos, self.stage.destination) < 2
                and abs(st.angle) < 0.04
                and math.dist(w.state(self.rhs).pos, self.rhs_pos) < 2):
            self.transferred_at = t
            events.append(Event(t, "math_transferred", self.spec.actor,
                                {"prop": self.term, "point": st.pos,
                                 "expression": self.stage.plan.expression_text}))
        if (self.transferred_at is not None and self.requested_at is not None
                and self.requested_at >= self.transferred_at + self.spec.min_hold
                and t >= self.requested_at and actor.carrying is None
                and math.dist(st.pos, self.stage.destination) < 2
                and math.dist(w.state(self.rhs).pos, self.rhs_pos) < 2
                and w.glyph_now[self.term] == self.stage.plan.destination.text):
            # Both operands merge into the identical numeric expression
            # geometry. Neither has been thrown away. Native morph then
            # visibly evaluates that complete expression into the result.
            for pid in (self.term, self.rhs):
                w.deactivate(pid)
                self.visibility[pid] = (-math.inf, t)
            w.activate(self.combined, self.combined_pos, 0.0, (0.0, 0.0), 0.0)
            w.set_kinematic(self.combined, self.combined_pos, 0.0)
            self.visibility[self.combined] = (t, math.inf)
            self.evaluated = True
            events.append(Event(t, "math_evaluate", self.spec.actor,
                                {"prop": self.combined, "point": self.combined_pos,
                                 "expression": self.stage.plan.expression_text,
                                 "result": self.stage.plan.result}))
