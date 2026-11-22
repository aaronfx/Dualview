"""Deterministic, event-driven world-lighting intensity for film scenes.

This is a presentation track, not a physics effect. Every cue is attached to
an observed simulation event (including a physically validated core restoration)
so frame order and partial rerenders cannot change the lighting.
"""
from __future__ import annotations

from ..scene.goals import matches


def power_level_at(spec, events, t: float) -> float:
    """Return the backdrop lighting multiplier in [0, 1] at story time t.

    Each cue eases from the intensity reached at its own event time. Later cues
    interrupt earlier transitions without creating a brightness discontinuity.
    """
    if spec is None:
        return 1.0
    changes = sorted((e.t, cue.level, cue.fade) for e in events
                     for cue in spec.cues if matches(cue.on, e))
    first, target, start, duration = spec.initial, spec.initial, 0.0, 0.0

    def sample(now: float) -> float:
        if duration <= 0:
            return target
        u = max(0.0, min(1.0, (now - start) / duration))
        u = u * u * (3.0 - 2.0 * u)
        return first + (target - first) * u

    for at, level, fade in changes:
        if at > t:
            break
        value = sample(at)
        first, target, start, duration = value, level, at, fade
    return max(0.0, min(1.0, sample(t)))
