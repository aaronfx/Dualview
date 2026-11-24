"""Configurable gravity vector with timed transitions (rotations) that never move the scene itself.

Angle conventions (documented in docs/SCENE_SCHEMA.md, "Gravity angles"):
- world angles are measured counter-clockwise from +x with y up; the original "down" is -90 deg;
- every transition carries a signed `sweep` (radians, + = counter-clockwise) relative to the PRECEDING gravity, so a
  180-degree reversal has an explicit, unambiguous direction;
- `angle_unwrapped(t)` accumulates the sweeps, giving each state's rotation relative to the ORIGINAL gravity
  (e.g. G1 = +90 deg, G2 = +270 deg); the camera roll follows this unwrapped angle, so it turns the same way the
  physics does.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.mathx import Vec, angle_of, ease, lerp, wrap_angle


@dataclass
class GravityTransition:
    t_start: float
    duration: float
    to: Vec  # target gravity vector (direction * magnitude)
    easing: str = "in_out"
    cause: str = ""
    sweep: Optional[float] = None  # signed rotation (rad, + = CCW) from the preceding gravity; None = shortest way


@dataclass
class GravityField:
    initial: Vec = (0.0, -1568.0)
    transitions: List[GravityTransition] = field(default_factory=list)

    def schedule(self, tr: GravityTransition) -> None:
        if self.transitions and tr.t_start < self.transitions[-1].t_start + self.transitions[-1].duration:
            raise ValueError("gravity transitions must not overlap")
        self.transitions.append(tr)

    def _sweep(self, g_from: Vec, tr: GravityTransition) -> float:
        if tr.sweep is not None:
            return tr.sweep
        return wrap_angle(angle_of(tr.to) - angle_of(g_from))

    def at(self, t: float) -> Vec:
        g = self.initial
        for tr in self.transitions:
            if t < tr.t_start:
                break
            if t >= tr.t_start + tr.duration:
                g = tr.to
                continue
            u = ease(tr.easing, (t - tr.t_start) / tr.duration)
            a0 = angle_of(g)
            m0, m1 = math.hypot(*g), math.hypot(*tr.to)
            a = a0 + self._sweep(g, tr) * u
            m = lerp(m0, m1, u)
            return (math.cos(a) * m, math.sin(a) * m)
        return g

    def angle_unwrapped(self, t: float) -> float:
        """Continuous gravity angle (rad): the initial angle plus the accumulated signed sweeps up to time t."""
        g = self.initial
        a = angle_of(g)
        for tr in self.transitions:
            if t < tr.t_start:
                break
            sw = self._sweep(g, tr)
            if t >= tr.t_start + tr.duration:
                a += sw
                g = tr.to
                continue
            return a + sw * ease(tr.easing, (t - tr.t_start) / tr.duration)
        return a

    def report(self) -> List[Dict[str, float]]:
        """Each gravity state with its angle relative to the preceding state and to the original state (degrees)."""
        out = [{"state": "G0", "t": 0.0, "world_deg": math.degrees(angle_of(self.initial)), "rel_prev_deg": 0.0, "rel_original_deg": 0.0}]
        g, acc = self.initial, 0.0
        for k, tr in enumerate(self.transitions, 1):
            sw = self._sweep(g, tr)
            acc += sw
            out.append({"state": f"G{k}", "t": tr.t_start + tr.duration, "world_deg": math.degrees(angle_of(tr.to)),
                        "rel_prev_deg": math.degrees(sw), "rel_original_deg": math.degrees(acc), "cause": tr.cause})
            g = tr.to
        return out

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
