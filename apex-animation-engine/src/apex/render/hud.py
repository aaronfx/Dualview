"""Game-style overlay (Milestone 6): the retry counter and on-screen messages, from the scene's HUD spec and events.

The counter shows the retries left at the start of the scene, minus each `fail` so far; the one just lost flashes red
and shrinks. Messages appear at a time or on an event (goal syntax), fade in, hold and fade out.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class HudFrame:
    retries: Optional[int]
    retries_max: int
    label: str
    flash: float  # 0..1: a retry was just lost
    messages: List[Tuple[str, str, float]] = field(default_factory=list)  # (text, style, alpha)


class Hud:
    def __init__(self, scene, events):
        self.spec = scene.hud
        self.fails = sorted(e.t for e in events if e.type == "fail")
        self.windows = []
        if self.spec is not None:
            from ..scene.goals import matches
            for m in self.spec.messages:
                if m.at is not None:
                    self.windows.append((m.at + m.delay, m))
                else:
                    hit = next((e for e in events if matches(m.on, e)), None)
                    if hit is not None:
                        self.windows.append((hit.t + m.delay, m))

    def at(self, t: float) -> Optional[HudFrame]:
        sp = self.spec
        if sp is None:
            return None
        lost = sum(1 for tf in self.fails if tf <= t)
        flash = max((max(0.0, 1.0 - (t - tf) / 0.9) for tf in self.fails if tf <= t), default=0.0)
        r = None if sp.retries is None else max(0, sp.retries - lost)
        msgs = []
        for t0, m in self.windows:
            u = t - t0
            if 0.0 <= u <= m.duration:
                a = min(1.0, u / 0.25, (m.duration - u) / 0.45)
                msgs.append((m.text, m.style, max(0.0, a)))
        return HudFrame(r, sp.retries_max, sp.label, flash, msgs)
