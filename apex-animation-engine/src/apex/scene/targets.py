"""Resolve symbolic targets ("switch:<id>", "exit:<id>", "point:x,y") to world points."""
from __future__ import annotations

from typing import Optional

from ..core.mathx import Vec
from .schema import EnvironmentSpec


def exit_world(env: EnvironmentSpec, exit_id: str) -> Vec:
    ex = next(x for x in env.exits if x.id == exit_id)
    hw, rh = env.room.width / 2, env.room.height
    return {"wall_right": (hw, ex.s), "wall_left": (-hw, ex.s), "floor": (ex.s, 0.0), "ceiling": (ex.s, rh)}[ex.surface]


def resolve(env: EnvironmentSpec, target: Optional[str]) -> Optional[Vec]:
    if not target:
        return None
    kind, _, ref = target.partition(":")
    if kind == "switch":
        sw = next(s for s in env.switches if s.id == ref)
        return (sw.x, sw.height)
    if kind == "exit":
        return exit_world(env, ref)
    if kind == "point":
        x, y = (float(v) for v in ref.split(","))
        return (x, y)
    raise ValueError(f"bad target {target}")
