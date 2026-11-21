"""Beat sync (Milestone 4): a beat grid in film time (what the audience hears) and its use in the story clock.

Beat k is at `offset + k * 60 / bpm` s of film time. When the scene has hit-stops or slow motion, film time and story
time differ; a `BeatClock` maps through the time warp, so a `wait_beat` that ends on a beat in the film ends at the
right story instant. Cut snapping moves each shot boundary that is close to a beat onto it.
"""
from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple


def period(music) -> float:
    return 60.0 / music.bpm


def beat_times(music, film_end: float) -> List[float]:
    P = period(music)
    k_max = int(math.floor((film_end - music.offset) / P + 1e-9))
    return [music.offset + k * P for k in range(0, k_max + 1)]


def nearest_beat(music, f: float) -> Tuple[int, float]:
    P = period(music)
    k = max(0, int(round((f - music.offset) / P)))
    return k, music.offset + k * P


class BeatClock:
    """Story-time targets of beats. `film_of` / `story_of` map between the clocks (identity without a time warp)."""

    def __init__(self, music, film_of: Optional[Callable[[float], float]] = None, story_of: Optional[Callable[[float], float]] = None):
        self.music = music
        self.film_of = film_of or (lambda t: t)
        self.story_of = story_of or (lambda f: f)

    def next(self, t: float, n: int = 1) -> Tuple[int, float]:
        """The n-th beat after story time t: (beat index, its story time)."""
        P = period(self.music)
        f = self.film_of(t)
        k = int(math.floor((f - self.music.offset) / P + 1e-9)) + n
        k = max(k, n - 1)
        return k, self.story_of(self.music.offset + k * P)


def snap_shots(scene, warp, fps: int, locks=()) -> Tuple[list, List[dict]]:
    """Shot boundaries within `snap_window` beats of a beat move onto it (in film time). Returns the new shots and a
    log of each boundary (before, after, beat index, film time). A boundary on a `lock` (a portal crossing: the picture
    already cuts there) stays put: moving it would put two cuts a few frames apart."""
    music = scene.music
    P = period(music)
    shots = sorted(scene.shots, key=lambda s: s.start)
    bounds = [s.end for s in shots[:-1]]
    log, new = [], []
    lo = 0.0
    for i, b in enumerate(bounds):
        f = warp.film_at(b)
        k, fb = nearest_beat(music, f)
        nb = b
        locked = any(abs(b - lk) < 2.0 / fps for lk in locks)
        if not locked and abs(f - fb) <= music.snap_window * P + 1e-9:
            cand = warp.sim_at(fb)
            hi = bounds[i + 1] if i + 1 < len(bounds) else scene.duration
            if lo + 0.4 < cand < hi - 0.4:  # never squeeze a shot below 0.4 s
                nb = cand
        log.append({"shot": shots[i].id, "before": round(b, 4), "after": round(nb, 4), "beat": k,
                    "film": round(warp.film_at(nb), 4), "snapped": nb != b, "locked": locked})
        new.append(nb)
        lo = nb
    edges = [0.0] + new + [scene.duration]
    out = [s.model_copy(update={"start": edges[i], "end": edges[i + 1]}) for i, s in enumerate(shots)]
    return out, log
