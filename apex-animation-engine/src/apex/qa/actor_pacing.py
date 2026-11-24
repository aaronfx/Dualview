"""M4 actor pacing audit over real APEX simulation samples.

This is a *screen-time diagnostic*, not a replacement for artistic review.
It distinguishes deliberate acting/waits and necessary contact recovery from
unmotivated stationary time, and flags pauses during supposed movement.
No automatic time-warping, action deletion, or physics modification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import math


@dataclass(frozen=True)
class PauseWindow:
    character: str
    start: float
    end: float
    duration: float
    category: str  # deliberate_performance | unwarranted_idle | movement_stall
    segment: str
    reason: str
    counted: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PacingReport:
    character: str
    duration: float
    deliberate_seconds: float
    wasted_seconds: float
    longest_wasted: float
    windows: tuple[PauseWindow, ...]
    threshold: float
    allowed_waste: float

    @property
    def passed(self) -> bool:
        return self.wasted_seconds <= self.allowed_waste + 1e-6

    def to_dict(self) -> dict[str, Any]:
        return {**{k: v for k, v in asdict(self).items() if k != "windows"},
                "windows": [w.to_dict() for w in self.windows],
                "passed": self.passed,
                "method": "240Hz simulated controller records and action segments; not human artistic judgment"}


def _deliberate_reason(data: dict) -> str | None:
    # A timed acting performance, gaze, authored wait, guard, intentional
    # suspense beat, or physically imposed landing/settle can be stationary
    # without being a storytelling failure. Report it, but don't score it as
    # waste. Human review still judges if the deliberate hold is *good*.
    for name in ("act", "gaze", "gaze_ref", "gaze_mode", "look", "look_back",
                 "settle", "tense", "waiting", "fight", "pause"):
        if data.get(name):
            return f"intentional {name}"
    return None


def _moving_stalls(records: list, seg, threshold: float, minimum_speed: float):
    """Return contiguous low-displacement intervals in a moving segment."""
    samples = [r for r in records if seg.t0 - 1e-6 <= r.t <= seg.t1 + 1e-6]
    if len(samples) < 2:
        return
    start = None
    last = None
    for a, b in zip(samples, samples[1:]):
        dt = b.t - a.t
        if dt <= 0:
            continue
        dx, dy = b.pos[0] - a.pos[0], b.pos[1] - a.pos[1]
        stationary = math.hypot(dx, dy) / dt < minimum_speed
        if stationary:
            if start is None:
                start = a.t
            last = b.t
        elif start is not None:
            if last - start >= threshold - 1e-6:
                yield (start, last)
            start = None
            last = None
    if start is not None and last is not None and last - start >= threshold - 1e-6:
        yield (start, last)


def audit_character(sim, character: str, *, min_pause: float = 0.38,
                    minimum_speed: float = 14.0, max_waste: float = 0.65) -> PacingReport:
    """Inspect actual scene simulation; flag dead idle and stuck movement.

    > min_pause: an isolated short physical settling beat isn't penalized.
    > minimum_speed: root movement (not limb animation) in scene units/sec.
    Segment-level inspection avoids falsely classifying one-foot stance as
    inactivity; a running character's planted foot is *supposed* to stop.
    """
    if not 0 < min_pause <= 10 or not 0 < minimum_speed <= 100 or max_waste < 0:
        raise ValueError("invalid actor pacing audit budget")
    ctrl = sim.controllers[character]
    out: list[PauseWindow] = []
    deliberate = 0.0
    for seg in ctrl.segments:
        length = max(0.0, min(seg.t1, sim.duration) - max(seg.t0, 0.0))
        if length < min_pause:
            continue
        if seg.kind == "idle":
            purpose = _deliberate_reason(seg.data)
            intentional = purpose is not None
            if intentional:
                deliberate += length
            out.append(PauseWindow(character, round(seg.t0, 4), round(seg.t0 + length, 4),
                                   round(length, 4), "deliberate_performance" if intentional else "unwarranted_idle",
                                   seg.kind, purpose or "actor is stationary without a declared performance goal",
                                   not intentional))
        elif seg.kind in ("loco", "climb", "vault", "wall_run"):
            for start, end in _moving_stalls(ctrl.records, seg, min_pause, minimum_speed):
                dur = end - start
                out.append(PauseWindow(character, round(start, 4), round(end, 4),
                                       round(dur, 4), "movement_stall", seg.kind,
                                       "negligible physical root displacement during an intended movement",
                                       True))
    # Do not count deliberate holds against the hard budget. All windows
    # remain visible so the reviewer can spot dramatically excessive holds.
    wasted = sum(w.duration for w in out if w.counted)
    return PacingReport(character, round(sim.duration, 4), round(deliberate, 4),
                        round(wasted, 4), round(max((w.duration for w in out if w.counted), default=0.0), 4),
                        tuple(sorted(out, key=lambda w: w.start)), min_pause, max_waste)
