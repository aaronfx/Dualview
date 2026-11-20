"""Resolve symbolic targets ("switch:<id>", "exit:<id>", "bar:<id>", "point:x,y") and surface-mounted geometry to
world points."""
from __future__ import annotations

from typing import Optional, Tuple

from ..core.mathx import Vec
from .schema import EnvironmentSpec, SwitchSpec


def surface_point(env: EnvironmentSpec, surface: str, s: float, h: float = 0.0) -> Vec:
    """World point at position `s` along a room surface and distance `h` from it (into the room). `s` is world x
    for floor/ceiling and world y for the walls (the same convention as SwitchSpec.x and ExitSpec.s)."""
    hw, rh = env.room.width / 2, env.room.height
    return {"floor": (s, h), "ceiling": (s, rh - h), "wall_right": (hw - h, s), "wall_left": (-hw + h, s)}[surface]


def surface_normal(surface: str) -> Vec:
    return {"floor": (0.0, 1.0), "ceiling": (0.0, -1.0), "wall_right": (-1.0, 0.0), "wall_left": (1.0, 0.0)}[surface]


def switch_world(env: EnvironmentSpec, sw: SwitchSpec) -> Vec:
    """World position of the button (its top centre)."""
    return surface_point(env, sw.surface, sw.x, sw.height)


def switch_base(env: EnvironmentSpec, sw: SwitchSpec) -> Vec:
    return surface_point(env, sw.surface, sw.x, 0.0)


def exit_world(env: EnvironmentSpec, exit_id: str) -> Vec:
    ex = next(x for x in env.exits if x.id == exit_id)
    return surface_point(env, ex.surface, ex.s, 0.0)


def exit_span(env: EnvironmentSpec, exit_id: str) -> Tuple[Vec, Vec]:
    """The two world end points of the doorway along its surface."""
    ex = next(x for x in env.exits if x.id == exit_id)
    return surface_point(env, ex.surface, ex.s - ex.width / 2), surface_point(env, ex.surface, ex.s + ex.width / 2)


def bar_world(env: EnvironmentSpec, bar_id: str) -> Vec:
    ob = next(o for o in env.obstacles if o.id == bar_id and o.kind == "bar")
    return (ob.center[0], ob.center[1])


def resolve(env: EnvironmentSpec, target: Optional[str]) -> Optional[Vec]:
    if not target:
        return None
    kind, _, ref = target.partition(":")
    if kind == "switch":
        return switch_world(env, next(s for s in env.switches if s.id == ref))
    if kind == "exit":
        return exit_world(env, ref)
    if kind == "bar":
        return bar_world(env, ref)
    if kind == "obstacle":  # any fixed structure (beam or bar); used by camera include lists
        ob = next(o for o in env.obstacles if o.id == ref)
        return (float(ob.center[0]), float(ob.center[1]))
    if kind == "point":
        x, y = (float(v) for v in ref.split(","))
        return (x, y)
    raise ValueError(f"bad target {target}")


def exit_portal(env: EnvironmentSpec, exit_id: str, depth: float = 420.0) -> Tuple[float, float, float, float]:
    """Axis-aligned region beyond a doorway (the corridor a character walks into once the door is open)."""
    ex = next(x for x in env.exits if x.id == exit_id)
    hw, rh = env.room.width / 2, env.room.height
    a, b = ex.s - ex.width / 2 - 10.0, ex.s + ex.width / 2 + 10.0  # a little wider than the doorway (feet, scarf)
    return {"ceiling": (a, rh - 6, b, rh + depth), "floor": (a, -depth, b, 6), "wall_right": (hw - 6, a, hw + depth, b),
            "wall_left": (-hw - depth, a, -hw + 6, b)}[ex.surface]


def in_portal(env: EnvironmentSpec, p: Vec) -> bool:
    for ex in env.exits:
        if ex.unlock_on:
            x0, y0, x1, y1 = exit_portal(env, ex.id)
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                return True
    return False
