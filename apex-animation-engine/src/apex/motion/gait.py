"""Procedural gait with planted feet.

Given the pelvis' path along a surface s(t) (from the simulation), the generator derives step phase from
speed, places every footfall at a fixed surface position (so stance feet never slide), and swings the free
foot along an arc to its next plant. Walk and run blend continuously with speed (double support -> flight).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.mathx import clamp, lerp, smoothstep


@dataclass
class GaitParams:
    walk_speed: float = 140.0
    run_speed: float = 420.0
    cadence_scale: float = 1.0
    stride_scale: float = 1.0
    leg_length: float = 86.0

    def step_length(self, v: float) -> float:
        return (30.0 + 0.24 * abs(v)) * self.stride_scale

    def cadence(self, v: float) -> float:
        """Steps per second (minimum keeps a slow shuffle alive while accelerating)."""
        return max(1.4, abs(v) / self.step_length(v)) * self.cadence_scale

    def run_blend(self, v: float) -> float:
        return smoothstep(self.walk_speed + 60, self.run_speed - 40, abs(v))

    def stance_fraction(self, v: float) -> float:
        """Fraction of a full (two-step) cycle a foot spends on the ground: walk > 0.5 (double support), run < 0.5 (flight)."""
        return lerp(0.62, 0.34, self.run_blend(v))


@dataclass
class FootSample:
    s: float
    h: float
    angle: float  # foot pitch relative to the surface (0 = flat, + = toes up)
    stance: bool


@dataclass
class Footfall:
    t: float
    leg: int
    s: float


class Gait:
    """Gait for one locomotion segment [t0, t1] on one surface."""

    def __init__(self, times: np.ndarray, s: np.ndarray, v: np.ndarray, params: GaitParams, direction: float,
                 start_plants: Tuple[float, float], lead_leg: int = 0):
        self.times, self.s, self.v = times, s, v
        self.p = params
        self.dir = 1.0 if direction >= 0 else -1.0
        self.t0, self.t1 = float(times[0]), float(times[-1])
        dt = np.diff(times, prepend=times[0])
        cad = np.array([params.cadence(x) for x in v])
        self.phase = np.cumsum(cad * dt)  # in steps; 0 at t0
        # The lead leg is exactly at the end of its stance at t0 (about to lift); the other leg is mid-stance.
        # Footfalls with index < lead_leg are the feet's starting positions; later ones are planned from s(t).
        self.offset = lead_leg - 2 + 2 * params.stance_fraction(float(v[0]))
        # footfalls that happened at or before t0 are the given start plants; later ones are planned from s(t)
        self.first_k = int(math.floor(self.offset)) + 1
        self.start_plants = start_plants
        self._plant_cache: Dict[int, float] = {}
        self.footfalls: List[Footfall] = []
        kmax = int(math.floor(self.phase[-1] + self.offset)) + 1
        for k in range(self.first_k, kmax + 1):
            tk = self.time_of(k)
            if tk is not None and tk <= self.t1 + 1e-9:
                self.footfalls.append(Footfall(tk, k % 2, self.plant(k)))

    # -- helpers
    def _interp(self, arr: np.ndarray, t: float) -> float:
        return float(np.interp(t, self.times, arr))

    def phase_at(self, t: float) -> float:
        return self._interp(self.phase, t) + self.offset

    def time_of(self, k: float) -> Optional[float]:
        ph = self.phase + self.offset
        if k < ph[0] or k > ph[-1]:
            return None
        return float(np.interp(k, ph, self.times))

    def lead(self, v: float) -> float:
        """Footfall lands ahead of the pelvis by ~half the distance the pelvis travels during stance,
        so each stance phase is centred under the body (keeps the planted leg within reach)."""
        return self.p.stance_fraction(v) * self.p.step_length(v) * 0.95 * self.dir

    def plant(self, k: int) -> float:
        """Surface position of footfall k (leg = k % 2)."""
        if k in self._plant_cache:
            return self._plant_cache[k]
        if k < self.first_k:
            val = self.start_plants[k % 2]
        else:
            tk = self.time_of(k)
            if tk is None:  # beyond the segment: extrapolate from the end state
                tk = self.t1
            val = self._interp(self.s, tk) + self.lead(self._interp(self.v, tk))
        self._plant_cache[k] = val
        return val

    # -- evaluation
    def foot(self, t: float, leg: int) -> FootSample:
        p = self.phase_at(t)
        k_last = math.floor((p - leg) / 2) * 2 + leg  # last footfall index for this leg
        q = (p - k_last) / 2.0  # 0..1 over the leg's full cycle
        v = self._interp(self.v, clamp(t, self.t0, self.t1))
        sf = self.p.stance_fraction(v)
        s0 = self.plant(int(k_last))
        if q < sf:
            u = q / sf
            heel_lift = smoothstep(0.65, 1.0, u)
            return FootSample(s0, 0.0, -0.55 * heel_lift, True)
        s2 = self.plant(int(k_last) + 2)
        u = (q - sf) / (1 - sf)
        e = u * u * (3 - 2 * u)
        lift = lerp(0.16, 0.42, self.p.run_blend(v)) * self.p.leg_length * self.p.stride_scale
        h = lift * math.sin(math.pi * u ** 0.8) ** 1.2
        ang = lerp(-0.9, 0.25, smoothstep(0.0, 0.9, u))
        return FootSample(lerp(s0, s2, e), h, ang, False)

    def pelvis_bob(self, t: float, leg_stance_h: float) -> float:
        p = self.phase_at(t)
        v = self._interp(self.v, clamp(t, self.t0, self.t1))
        sf = self.p.stance_fraction(v)
        frac = p - math.floor(p)
        amp = lerp(2.2, 5.5, self.p.run_blend(v))
        # lowest at mid-stance of each step (walk), highest in flight (run)
        return -amp * math.cos(2 * math.pi * (frac - sf))

    def arm_phase(self, t: float) -> float:
        return math.cos(math.pi * (self.phase_at(t) - 0.2))

    def speed(self, t: float) -> float:
        return self._interp(self.v, clamp(t, self.t0, self.t1))

    def accel(self, t: float) -> float:
        h = 0.05
        return (self.speed(t + h) - self.speed(t - h)) / (2 * h)

    def final_plants(self) -> Tuple[float, float]:
        """Where each foot rests when the segment ends (the swing foot completes its step)."""
        p_end = self.phase_at(self.t1)
        out = []
        for leg in (0, 1):
            k_last = math.floor((p_end - leg) / 2) * 2 + leg
            q = (p_end - k_last) / 2.0
            sf = self.p.stance_fraction(self.speed(self.t1))
            out.append(self.plant(int(k_last)) if q < sf else self.plant(int(k_last) + 2))
        return out[0], out[1]

    def stance_intervals(self, leg: int) -> List[Tuple[float, float, float]]:
        """(t_start, t_end, s) for every stance phase of `leg` inside the segment."""
        res = []
        ts = np.linspace(self.t0, self.t1, max(2, int((self.t1 - self.t0) * 480)))
        cur = None
        for t in ts:
            f = self.foot(float(t), leg)
            if f.stance:
                if cur is None or abs(cur[2] - f.s) > 1e-6:
                    if cur is not None:
                        res.append(cur)
                    cur = [float(t), float(t), f.s]
                else:
                    cur[1] = float(t)
            elif cur is not None:
                res.append(cur)
                cur = None
        if cur is not None:
            res.append(cur)
        return [tuple(r) for r in res]
