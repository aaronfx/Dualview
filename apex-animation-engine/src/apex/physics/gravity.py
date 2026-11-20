"""Configurable gravity vector with timed transitions (rotations) that never move the scene itself."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

from ..core.mathx import Vec, angle_of, ease, lerp, wrap_angle


@dataclass
class GravityTransition:
    t_start: float
    duration: float
    to: Vec  # target gravity vector (direction * magnitude)
    easing: str = "in_out"
    cause: str = ""


@dataclass
class GravityField:
    initial: Vec = (0.0, -1568.0)
    transitions: List[GravityTransition] = field(default_factory=list)

    def schedule(self, tr: GravityTransition) -> None:
        if self.transitions and tr.t_start < self.transitions[-1].t_start + self.transitions[-1].duration:
            raise ValueError("gravity transitions must not overlap")
        self.transitions.append(tr)

    def at(self, t: float) -> Vec:
        g = self.initial
        for tr in self.transitions:
            if t < tr.t_start:
                break
            if t >= tr.t_start + tr.duration:
                g = tr.to
                continue
            u = ease(tr.easing, (t - tr.t_start) / tr.duration)
            a0, a1 = angle_of(g), angle_of(tr.to)
            m0, m1 = math.hypot(*g), math.hypot(*tr.to)
            a = a0 + wrap_angle(a1 - a0) * u
            m = lerp(m0, m1, u)
            return (math.cos(a) * m, math.sin(a) * m)
        return g

    def direction(self, t: float) -> Vec:
        g = self.at(t)
        n = math.hypot(*g) or 1.0
        return (g[0] / n, g[1] / n)

    def state_label(self, t: float) -> str:
        """Discrete label G0, G1, ... = number of completed transitions (mid-transition reports the previous)."""
        k = 0
        for tr in self.transitions:
            if t >= tr.t_start + tr.duration:
                k += 1
        return f"G{k}"

    def segments(self, t_end: float) -> List[Tuple[float, float, Vec]]:
        """Intervals of constant gravity (excluding transition windows)."""
        out, g, t = [], self.initial, 0.0
        for tr in self.transitions:
            out.append((t, tr.t_start, g))
            g, t = tr.to, tr.t_start + tr.duration
        out.append((t, t_end, g))
        return [s for s in out if s[1] > s[0]]
