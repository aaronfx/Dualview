"""Inverse kinematics solvers (character frame)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..core.mathx import Vec, clamp, wrap_angle


@dataclass
class TwoBoneSolution:
    a1: float  # absolute angle of the first bone (character frame)
    a2: float  # absolute angle of the second bone
    reached: bool
    distance_error: float
    stretch: float = 1.0


def solve_two_bone(start: Vec, target: Vec, l1: float, l2: float, bend: int = 1, max_stretch: float = 1.0) -> TwoBoneSolution:
    """Analytic two-bone IK (law of cosines).

    bend=+1 places the middle joint on the counter-clockwise side of the start->target line
    (knees forward for a character facing +x), bend=-1 on the clockwise side (elbows back).
    `max_stretch` > 1 allows cartoon limb stretch when the target is out of reach.
    """
    dx, dy = target[0] - start[0], target[1] - start[1]
    d = math.hypot(dx, dy)
    reach = (l1 + l2) * 0.9999
    stretch = 1.0
    if d > reach:
        stretch = min(d / reach, max_stretch)
    L1, L2 = l1 * stretch, l2 * stretch
    dd = clamp(d, abs(L1 - L2) + 1e-6, (L1 + L2) * 0.9999)
    base = math.atan2(dy, dx)
    cos_a = clamp((L1 * L1 + dd * dd - L2 * L2) / (2 * L1 * dd), -1.0, 1.0)
    a1 = base + bend * math.acos(cos_a)
    mx, my = start[0] + math.cos(a1) * L1, start[1] + math.sin(a1) * L1
    a2 = math.atan2(target[1] - my, target[0] - mx)
    ex, ey = mx + math.cos(a2) * L2, my + math.sin(a2) * L2
    err = math.hypot(ex - target[0], ey - target[1])
    return TwoBoneSolution(a1, a2, err < 0.5, err, stretch)


def to_local(abs_angle: float, parent_abs: Optional[float]) -> float:
    return abs_angle if parent_abs is None else wrap_angle(abs_angle - parent_abs)


def aim(start: Vec, target: Vec) -> float:
    return math.atan2(target[1] - start[1], target[0] - start[0])


def solve_two_bone_local(start: Vec, target: Vec, l1: float, l2: float, bend: int, parent_abs: Optional[float],
                         max_stretch: float = 1.0) -> Tuple[float, float, TwoBoneSolution]:
    sol = solve_two_bone(start, target, l1, l2, bend, max_stretch)
    return to_local(sol.a1, parent_abs), wrap_angle(sol.a2 - sol.a1), sol
