"""Director-side actor pacing presets.

A pace controls *presentation and action intent*, not simulation time, gravity,
contacts or body teleportation. Fast actors still need authentic anticipation
and impact. Physical event verification remains authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PaceName = Literal["measured", "active"]


@dataclass(frozen=True)
class ActorPace:
    name: PaceName
    notice_seconds: float
    decision_tempo: float
    recovery_tempo: float
    celebration_tempo: float
    travel_speed: float
    goal_speed: float
    end_hold: float
    final_tail: float

    @property
    def decision_seconds(self) -> float:
        from ..motion.library import get_clip
        return get_clip("doubt_to_dash").length() / self.decision_tempo

    @property
    def recovery_seconds(self) -> float:
        from ..motion.library import get_clip
        return get_clip("impact_to_grin").length() / self.recovery_tempo


PRESETS: dict[str, ActorPace] = {
    "measured": ActorPace("measured", 0.70, 1.0, 1.0, 1.0, 355.0, 300.0, 1.0, 2.50),
    # In active mode the entire expressive clip still plays. It is performed
    # briskly, rather than cutting off anticipation, contact or follow-through.
    "active": ActorPace("active", 0.28, 1.72, 1.60, 1.60, 485.0, 450.0, 0.22, 1.65),
}


def actor_pace(name: PaceName) -> ActorPace:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown actor pace {name!r}; expected measured or active") from exc
