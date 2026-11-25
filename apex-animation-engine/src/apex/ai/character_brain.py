"""Bounded, deterministic character intent selection for the APEX staging director.

This layer chooses *intent*, not coordinates or physics outcomes. APEX's action
planner and SceneRuntime remain authoritative for feasibility and collisions.
It deliberately does not use an LLM at every frame.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

import py_trees


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
    target_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("danger", "novelty"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class Decision:
    intent: Intent
    visited: tuple[Intent, ...]


@dataclass
class CharacterBrain:
    personality: Personality
    memory: dict[str, int] = field(default_factory=dict)
    failed_attempts: dict[tuple[str, Intent], int] = field(default_factory=dict)

    def record_outcome(self, target_id: str, intent: Intent, *, succeeded: bool) -> None:
        """Record only observed execution outcomes, never predicted physics."""
        key = (target_id, intent)
        if succeeded:
            self.failed_attempts.pop(key, None)
        else:
            self.failed_attempts[key] = min(3, self.failed_attempts.get(key, 0) + 1)
        # Bound memory for long films; insertion order is deterministic.
        while len(self.failed_attempts) > 128:
            del self.failed_attempts[next(iter(self.failed_attempts))]

    def _blocked(self, perception: Perception, intent: Intent) -> bool:
        return perception.target_id is not None and self.failed_attempts.get((perception.target_id, intent), 0) >= 2

    def _rules(self, p: Perception) -> tuple[tuple[Intent, bool], ...]:
        return (
            (Intent.RECOVER, p.recovering),
            (Intent.EVADE, p.danger > 0.75 or (p.danger > 0.4 and self.personality.courage < 0.35)),
            (Intent.HELP, p.ally_needs_help and self.personality.empathy >= 0.45),
            (Intent.EXPLORE, p.novelty >= 0.5 and self.personality.curiosity >= 0.6
             and not self._blocked(p, Intent.EXPLORE)),
            (Intent.APPROACH, p.goal_visible and p.danger <= self.personality.courage
             and not self._blocked(p, Intent.APPROACH)),
            (Intent.OBSERVE, True),
        )

    def decide(self, perception: Perception) -> Decision:
        """Tick a priority selector from current perception, without executing motion."""
        visited: list[Intent] = []
        selected: list[Intent] = []
        class Rule(py_trees.behaviour.Behaviour):
            def __init__(self, intent: Intent, allowed: bool):
                super().__init__(name=intent.value)
                self.intent, self.allowed = intent, allowed

            def update(self):
                visited.append(self.intent)
                if self.allowed:
                    selected.append(self.intent)
                    return py_trees.common.Status.SUCCESS
                return py_trees.common.Status.FAILURE

        root = py_trees.composites.Selector(name="character_intent", memory=False,
                                            children=[Rule(i, ok) for i, ok in self._rules(perception)])
        root.tick_once()
        if len(selected) != 1:
            raise RuntimeError("Character selector must choose exactly one intent")
        return Decision(selected[0], tuple(visited))

    def choose(self, perception: Perception) -> Intent:
        """Safety-first priorities with personality-dependent choices.

        Decisions are reproducible. State is limited to counters so there is no
        unbounded history or invented scene knowledge.
        """
        intent = self.decide(perception).intent
        self.memory[intent.value] = self.memory.get(intent.value, 0) + 1
        return intent

    def snapshot(self) -> Mapping[str, int]:
        return dict(self.memory)
