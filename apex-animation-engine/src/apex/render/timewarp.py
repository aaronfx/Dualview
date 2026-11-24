"""Film time vs story time: hit-stop and slow motion (Milestone 3).

The simulation runs in *story* time and is never changed. The film samples it through a monotonic warp:
- **hit-stop**: at a blow, story time holds for a few film frames (the impact frame lingers; the camera keeps shaking
  and the screen effects keep running in film time);
- **slow motion**: around a chosen beat (a flip, a knockdown...), story time runs at `rate` of film time, eased in
  and out over `ramp` seconds.

`sim_at(film_t)` is what the renderer samples; `film_at(story_t)` places sounds and effects on the film clock, so
audio stays in sync with the picture through every warp.
"""
from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

STEP = 1.0 / 960.0  # film-time integration step


@dataclass
class Hold:
    t: float  # story time of the blow
    film: float  # how long the frame holds (film seconds)
    power: float
    kind: str
    point: Optional[Tuple[float, float]] = None  # where the blow lands (world)
    heavy: bool = False  # a knockdown-class blow (the camera closes in on it)


@dataclass
class Slow:
    t0: float  # story time where the slow section starts (fully slowed from t0 + ramp)
    t1: float
    rate: float  # story seconds per film second while fully slowed
    ramp: float
    label: str


class TimeWarp:
    def __init__(self, duration: float, holds: Sequence[Hold] = (), slows: Sequence[Slow] = ()):
        self.duration = duration
        self.holds = sorted(holds, key=lambda h: h.t)
        self.slows = list(slows)
        film, sim = [0.0], [0.0]
        f, s = 0.0, 0.0
        hi = 0
        while s < duration - 1e-12:
            while hi < len(self.holds) and self.holds[hi].t <= s + 1e-9:
                f += self.holds[hi].film  # story time stands still while the film runs on
                film.append(f)
                sim.append(s)
                hi += 1
            r = self.rate(s)
            ds = min(r * STEP, duration - s)
            nxt = self.holds[hi].t if hi < len(self.holds) else None
            if nxt is not None and s + ds > nxt:
                ds = max(nxt - s, 0.0)
            f += ds / r
            s += ds
            film.append(f)
            sim.append(s)
        self.F, self.S = np.array(film), np.array(sim)
        self.film_duration = float(self.F[-1])

    def rate(self, s: float) -> float:
        r = 1.0
        for sl in self.slows:
            if sl.t0 <= s <= sl.t1 + sl.ramp:
                w_in = min(1.0, (s - sl.t0) / sl.ramp) if sl.ramp > 0 else 1.0
                w_out = min(1.0, max(0.0, (sl.t1 + sl.ramp - s) / sl.ramp)) if sl.ramp > 0 else 1.0
                w = min(w_in, w_out)
                w = w * w * (3 - 2 * w)
                r = min(r, 1.0 + (sl.rate - 1.0) * w)
        return max(r, 0.05)

    def sim_at(self, film_t: float) -> float:
        return float(np.interp(film_t, self.F, self.S))

    def film_at(self, story_t: float) -> float:
        """The film time a story instant first appears (the start of a hold)."""
        i = int(np.searchsorted(self.S, story_t - 1e-7, side="left"))
        if i <= 0:
            return 0.0
        if i >= len(self.S):
            return self.film_duration
        s0, s1, f0, f1 = self.S[i - 1], self.S[i], self.F[i - 1], self.F[i]
        return float(f0 + (f1 - f0) * (story_t - s0) / (s1 - s0)) if s1 > s0 else float(f1)

    def holding(self, film_t: float) -> Optional[Tuple[Hold, float]]:
        """The hold in progress at this film time, and how far into it (0..1)."""
        for h in self.holds:
            f0 = self.film_at(h.t)
            if f0 <= film_t < f0 + h.film:
                return h, (film_t - f0) / h.film
        return None

    def slow_weight(self, film_t: float) -> float:
        """0 at full speed .. 1 fully slowed (for push-ins, speed lines, sound)."""
        r = self.rate(self.sim_at(film_t))
        lo = min((sl.rate for sl in self.slows), default=1.0)
        return 0.0 if lo >= 1.0 else max(0.0, min(1.0, (1.0 - r) / (1.0 - lo)))

    def is_identity(self) -> bool:
        return not self.holds and not self.slows


def build_warp(scene, events, duration: float, fps: int) -> TimeWarp:
    """Holds and slow sections from the scene's `time_fx` and the simulated events."""
    from ..scene.goals import matches
    tf = getattr(scene, "time_fx", None)
    if tf is None:
        return TimeWarp(duration)
    holds: List[Hold] = []
    if tf.hit_stop:
        for e in events:
            if e.type not in tf.hit_stop_events:
                continue
            p = float(e.data.get("power", 1.0))
            base = tf.hit_stop_frames * (0.5 if e.type in ("block_hit", "blocked") else 1.0)
            frames = int(max(1, min(tf.hit_stop_max, round(base * (0.6 + 0.6 * p)))))
            if holds and abs(holds[-1].t - e.t) < 0.06:  # one blow can emit several events (hit, hurt, prop_hit)
                holds[-1].film = max(holds[-1].film, frames / fps)
                continue
            holds.append(Hold(e.t, frames / fps, p, e.type, tuple(e.data["point"]) if "point" in e.data else None))
    for h in holds:  # knockdown-class blows (the engine's own verdict, not a guess from the power)
        h.heavy = any(e.type == "knockdown" and abs(e.t - h.t) < 0.06 for e in events)
    slows: List[Slow] = []
    for sm in tf.slowmo:
        hit = next((e for e in events if matches(sm.at.split(":", 1)[1] if sm.at.startswith(("event:", "next:")) else sm.at, e)), None)
        if hit is None:
            continue
        slows.append(Slow(max(0.0, hit.t - sm.before - sm.ramp), hit.t + sm.after, sm.rate, sm.ramp, sm.at))
    return TimeWarp(duration, holds, slows)
