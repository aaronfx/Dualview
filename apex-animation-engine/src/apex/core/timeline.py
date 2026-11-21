"""Timeline primitives: keyframe tracks and densely sampled tracks.

Every animated quantity in the engine is a pure function of time so that any frame can be evaluated
independently (arbitrary-timestamp evaluation, scene re-rendering, QA sampling).
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import numpy as np

from .mathx import ease


@dataclass
class Key:
    t: float
    v: float
    ease: str = "in_out"  # easing of the segment that STARTS at this key


@dataclass
class Track:
    """Piecewise-eased scalar track. Values are held before the first and after the last key."""

    keys: List[Key] = field(default_factory=list)

    @classmethod
    def of(cls, *items: Sequence) -> "Track":
        return cls([Key(*it) for it in items])

    def __call__(self, t: float) -> float:
        ks = self.keys
        if not ks:
            return 0.0
        if t <= ks[0].t:
            return ks[0].v
        if t >= ks[-1].t:
            return ks[-1].v
        i = bisect.bisect_right([k.t for k in ks], t) - 1
        k0, k1 = ks[i], ks[i + 1]
        u = (t - k0.t) / (k1.t - k0.t)
        return k0.v + (k1.v - k0.v) * ease(k0.ease, u)


class SampledTrack:
    """Uniformly sampled multi-channel signal with linear interpolation (used for recorded simulation)."""

    def __init__(self, t0: float, dt: float, data: np.ndarray):
        self.t0, self.dt = t0, dt
        self.data = np.asarray(data, dtype=np.float64)
        if self.data.ndim == 1:
            self.data = self.data[:, None]

    @property
    def t1(self) -> float:
        return self.t0 + self.dt * (len(self.data) - 1)

    def __call__(self, t: float) -> np.ndarray:
        f = (t - self.t0) / self.dt
        n = len(self.data)
        if f <= 0:
            return self.data[0].copy()
        if f >= n - 1:
            return self.data[-1].copy()
        i = int(f)
        u = f - i
        return self.data[i] * (1 - u) + self.data[i + 1] * u

    def index(self, t: float) -> int:
        return int(np.clip(round((t - self.t0) / self.dt), 0, len(self.data) - 1))


def frame_times(duration: float, fps: int) -> List[float]:
    n = int(round(duration * fps))
    return [i / fps for i in range(n)]


def spans(intervals: Sequence[Tuple[float, float]], t: float) -> bool:
    return any(a <= t < b for a, b in intervals)
