"""Bounded, deterministic character intent selection for the APEX staging director.

This layer chooses *intent*, not coordinates or physics outcomes. APEX's action
planner and SceneRuntime remain authoritative for feasibility and collisions.
It deliberately does not use an LLM at every frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class Intent(str, Enum):
    OBSERVE = "observe"
    APPROACH = "approach"
    EVADE = "evade"
    HELP = "help"
    EXPLORE = "explore"
    RECOVER = "recover"


@dataclass(frozen=True)
class Personality:
    curiosity: float = 0.5
    courage: float = 0.5
    empathy: float = 0.5
    playfulness: float = 0.5

    def __post_init__(self) -> None:
        for name in ("curiosity", "courage", "empathy", "playfulness"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class Perception:
    danger: float = 0.0
    novelty: float = 0.0
    ally_needs_help: bool = False
    recovering: bool = False
    goal_visible: bool = False

    def __post_init__(self) -> None:
        for name in ("danger", "novelty"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass
class CharacterBrain:
    personality: Personality
    memory: dict[str, int] = field(default_factory=dict)

    def choose(self, perception: Perception) -> Intent:
        """Safety-first priorities with personality-dependent choices.

        Decisions are reproducible. State is limited to counters so there is no
        unbounded history or invented scene knowledge.
        """
        if perception.recovering:
            intent = Intent.RECOVER
        elif perception.danger > 0.75 or (
            perception.danger > 0.4 and self.personality.courage < 0.35
        ):
            intent = Intent.EVADE
        elif perception.ally_needs_help and self.personality.empathy >= 0.45:
            intent = Intent.HELP
        elif perception.novelty >= 0.5 and self.personality.curiosity >= 0.6:
            intent = Intent.EXPLORE
        elif perception.goal_visible and perception.danger <= self.personality.courage:
            intent = Intent.APPROACH
        else:
            intent = Intent.OBSERVE
        self.memory[intent.value] = self.memory.get(intent.value, 0) + 1
        return intent

    def snapshot(self) -> Mapping[str, int]:
        return dict(self.memory)
