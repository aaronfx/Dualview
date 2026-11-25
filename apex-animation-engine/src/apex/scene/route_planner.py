"""Conservative ballistic route preflight for APEX's arcade and action directors.

This never dictates an animation or changes physics. It checks whether a planned
jump is remotely feasible *before* an AI Director spends tokens staging it. The
existing 240 Hz physics simulation and collision QA remain the authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Tuple

from .structures import Block, blocks

Point = Tuple[float, float]


@dataclass(frozen=True)
class JumpPlan:
    start: Point
    end: Point
    horizontal_speed: float
    vertical_speed: float
    duration: float
    apex_y: float
    samples: tuple[Point, ...]
    # Foot-space trajectory (character body extends vertically above these points).


@dataclass(frozen=True)
class RouteVerdict:
    feasible: bool
    reason: str
    plan: Optional[JumpPlan] = None


def check_jump(env, start: Point, end: Point, *, horizontal_speed: float,
               body_height: float = 165.0, body_half_width: float = 12.0,
               max_rise: float = 420.0, max_launch_speed: float = 1250.0,
               samples: int = 101, live_bounds: tuple[Block, ...] = ()) -> RouteVerdict:
    """Test a forward ballistic jump in a fixed downward-gravity environment.

    The collision check uses conservative body envelopes against existing APEX
    static structures and caller-supplied same-lane live bounds; moving obstacles
    need conservative swept bounds. Native simulation remains authoritative.
    """
    gx, gy = env.gravity
    if abs(gx) > 1e-6 or gy >= -1e-6:
        return RouteVerdict(False, "route preflight supports downward gravity only; use full physics for a gravity shift")
    if not all(math.isfinite(v) for v in (*start, *end, horizontal_speed, body_height,
                                           body_half_width, max_rise, max_launch_speed)):
        return RouteVerdict(False, "nonfinite jump parameters")
    if horizontal_speed == 0 or math.copysign(1, horizontal_speed) != math.copysign(1, end[0]-start[0]):
        return RouteVerdict(False, "horizontal travel and velocity must point in the same direction")
    if body_height <= 0 or body_half_width < 0 or max_rise <= 0 or max_launch_speed <= 0 or samples < 5:
        return RouteVerdict(False, "invalid physical budget")
    duration = (end[0] - start[0]) / horizontal_speed
    if duration < 0.06 or duration > 12.0:
        return RouteVerdict(False, "flight time is outside the 0.06–12 second planning range")
    vy = (end[1] - start[1] - 0.5 * gy * duration * duration) / duration
    if vy <= 0:
        return RouteVerdict(False, "trajectory needs upward takeoff for this jump")
    if math.hypot(horizontal_speed, vy) > max_launch_speed:
        return RouteVerdict(False, "required launch speed exceeds the allowed physical budget")
    apex_t = vy / -gy
    apex_y = start[1] + vy * apex_t + 0.5 * gy * apex_t * apex_t
    if apex_y - start[1] > max_rise:
        return RouteVerdict(False, "required apex exceeds allowed jump rise")
    height, half_width = env.room.height, env.room.width / 2
    path = []
    for b in live_bounds:
        if not all(math.isfinite(v) for v in (b.x0,b.x1,b.y0,b.y1)) or b.x0 >= b.x1 or b.y0 >= b.y1:
            return RouteVerdict(False, f"invalid live obstacle bounds: {b.owner}")
    solids = [*blocks(env), *live_bounds]
    for i in range(samples):
        t = duration * i / (samples - 1)
        x = start[0] + horizontal_speed * t
        y = start[1] + vy * t + 0.5 * gy * t * t
        path.append((x, y))
        if x - body_half_width < -half_width or x + body_half_width > half_width or y < -0.5:
            return RouteVerdict(False, "trajectory leaves the playable room")
        if y + body_height > height:
            return RouteVerdict(False, "character collides with the room ceiling")
        for solid in solids:
            if (x + body_half_width > solid.x0 + 0.01 and x - body_half_width < solid.x1 - 0.01
                    and y < solid.y1 - 0.01 and y + body_height > solid.y0 + 0.01):
                return RouteVerdict(False, f"body would cross solid obstacle {solid.owner!r}")
    return RouteVerdict(True, "conservative trajectory envelope is clear; full simulation still required",
                        JumpPlan(start, end, horizontal_speed, vy, duration, apex_y, tuple(path)))


def select_clearance_jump(env, start: Point, end: Point, *, live_bounds: tuple[Block, ...],
                          body_height: float = 165.0, body_half_width: float = 25.0,
                          max_rise: float = 260.0) -> RouteVerdict:
    """Search bounded launch speeds, preferring the lowest feasible apex.
    Start and landing must be supplied from the current support geometry.
    No unchecked jump is returned when the available arc is insufficient.
    """
    candidates = []
    for speed in (180, 220, 260, 300, 360, 420, 480, 540):
        verdict = check_jump(env, start, end,
                             horizontal_speed=math.copysign(speed, end[0] - start[0]),
                             body_height=body_height, body_half_width=body_half_width,
                             max_rise=max_rise, live_bounds=live_bounds, samples=241)
        if verdict.feasible:
            candidates.append(verdict)
    if not candidates:
        return RouteVerdict(False, "no feasible jump across current obstacle envelope")
    return min(candidates, key=lambda v: (v.plan.apex_y, v.plan.duration))
