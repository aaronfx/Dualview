"""Causal production plans shared by the Math, Arcade and Epic benchmark films.

A plan is *not* a movie. It records intended cause/effect, screen events and world
state. APEX must still simulate and render the actions, then obtain artistic review.
The types are strict so an AI Director cannot silently invent unsupported metadata.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Mode = Literal["math", "arcade", "epic", "hybrid"]
BeatKind = Literal["setup", "discovery", "obstacle", "response", "reversal", "payoff", "transition"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MathClaim(Strict):
    before: Dict[str, Any]
    after: Dict[str, Any]


class CausalBeat(Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z][\w-]*$")
    scene: str = Field(min_length=1, max_length=64)
    t: float = Field(ge=0)
    kind: BeatKind
    intent: str = Field(min_length=3, max_length=500)
    actor: Optional[str] = None
    causes: List[str] = Field(default_factory=list, max_length=8)
    requires: Dict[str, str] = Field(default_factory=dict)
    effects: Dict[str, str] = Field(default_factory=dict)
    proof_event: Optional[str] = None  # e.g. "break@vial", from SceneRuntime events
    tolerance: float = Field(0.75, ge=0, le=3)
    # An arcade beat uses the *film* clock, not the simulation clock. Slow motion
    # or hit-stop can make t != film_t.
    on_beat: bool = False
    film_t: Optional[float] = Field(None, ge=0)
    math: Optional[MathClaim] = None

    @field_validator("requires", "effects")
    @classmethod
    def _state_bounds(cls, data):
        if len(data) > 16 or any(not k or len(k) > 64 or len(v) > 128 for k, v in data.items()):
            raise ValueError("too many or oversized narrative state entries")
        return data

    @model_validator(mode="after")
    def _validate(self):
        if self.on_beat and self.film_t is None:
            raise ValueError("on_beat requires film_t, not simulation t")
        if self.proof_event is not None:
            from .goals import parse_goal, check_event
            etype, _, _ = parse_goal(self.proof_event)
            check_event(etype, f"beat {self.id}")
        if len(set(self.causes)) != len(self.causes) or self.id in self.causes:
            raise ValueError("duplicate or self-referential causal dependency")
        return self


class CreativePlan(Strict):
    """Optional multi-scene creative contract; no effect on legacy projects."""
    profile: Mode
    premise: str = Field(min_length=5, max_length=1000)
    initial_state: Dict[str, str] = Field(default_factory=dict)
    beats: List[CausalBeat] = Field(min_length=1, max_length=250)
    beat_tolerance_frames: int = Field(2, ge=0, le=8)

    @model_validator(mode="after")
    def _unique(self):
        ids = [b.id for b in self.beats]
        if len(set(ids)) != len(ids):
            raise ValueError("creative plan has duplicate beat ids")
        if len(self.initial_state) > 32:
            raise ValueError("creative plan has too many initial state entries")
        return self
