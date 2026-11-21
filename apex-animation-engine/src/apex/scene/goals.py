"""Story goals: the beats a scene must produce in simulation, e.g. "pinned@milo[by=post]".

Syntax: `[event:]<type>[@<who>][[key=value,...]]`, where `who` is a character, prop or rope id and the bracketed
filters match the event's data (e.g. `by=post`). Explicit goals are ordered: each must happen after the previous.
When a scene has none, `derive_goals` infers the events the action list depends on (unordered).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

_GOAL = re.compile(r"^(?:event:)?([a-z_]+)(?:@([A-Za-z0-9_\-]+))?(?:\[([^\]]*)\])?$")
PRONE_ACTIONS = ("struggle", "crawl_out", "get_up")


def parse_goal(g: str) -> Tuple[str, Optional[str], Dict[str, str]]:
    m = _GOAL.match(g.strip())
    if not m:
        raise ValueError(f"goal {g!r} must look like 'type', 'type@who' or 'type@who[key=value]'")
    etype, who, filt = m.group(1), m.group(2), {}
    if m.group(3):
        for part in m.group(3).split(","):
            k, _, v = part.partition("=")
            if not k.strip() or not v.strip():
                raise ValueError(f"goal {g!r}: filter {part!r} must be key=value")
            filt[k.strip()] = v.strip()
    return etype, who, filt


def matches(goal: str, e) -> bool:
    etype, who, filt = parse_goal(goal)
    return (e.type == etype and (who is None or e.character == who)
            and all(str(e.data.get(k)) == v for k, v in filt.items()))


def derive_goals(scene) -> List[str]:
    """Events the action list cannot do without: every `until` event, and a fall before any lying-down action."""
    out: List[str] = []
    for a in scene.actions:
        if a.type in PRONE_ACTIONS:
            g = f"body_fall@{a.character}"
            if g not in out:
                out.append(g)
        if a.until:
            g = a.until.split(":", 1)[1]
            if g not in out:
                out.append(g)
    return out


def progress(goals: Sequence[str], events, ordered: bool = True, before: Optional[float] = None):
    """How many goals happened (in order, if `ordered`), their times, and the first goal still missing."""
    t_prev = -1.0
    times: List[Optional[float]] = []
    met = 0
    for g in goals:
        hit = next((e for e in events if matches(g, e) and (not ordered or e.t >= t_prev)
                    and (before is None or e.t <= before)), None)
        times.append(hit.t if hit else None)
        if hit is None:
            if ordered:
                times += [None] * (len(goals) - len(times))
                break
            continue
        met += 1
        if ordered:
            t_prev = hit.t
    missing = next((g for g, t in zip(goals, times) if t is None), None)
    return met, times, missing
