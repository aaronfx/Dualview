"""Ground (support-surface) frames: every grounded motion is authored in (s, h) = (along surface, height above it)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..core.mathx import Vec, v_dot


@dataclass(frozen=True)
class GroundFrame:
    tag: str
    origin: Vec  # a point on the surface
    normal: Vec  # unit normal pointing into free space
    lo: float = -math.inf  # extent along the tangent (s): room surfaces are unbounded; a platform top ends
    hi: float = math.inf
    owner: Optional[str] = None  # the structure this top belongs to (None: a room surface)

    @property
    def bounded(self) -> bool:
        return math.isfinite(self.lo) or math.isfinite(self.hi)

    @property
    def tangent(self) -> Vec:
        # tangent = normal rotated -90deg, so a floor (normal +y) has tangent +x
        return (self.normal[1], -self.normal[0])

    @property
    def body_angle(self) -> float:
        """World rotation of a character standing upright on this surface."""
        return math.atan2(self.normal[1], self.normal[0]) - math.pi / 2

    def to_world(self, s: float, h: float) -> Vec:
        t, n = self.tangent, self.normal
        return (self.origin[0] + t[0] * s + n[0] * h, self.origin[1] + t[1] * s + n[1] * h)

    def to_frame(self, p: Vec) -> Tuple[float, float]:
        d = (p[0] - self.origin[0], p[1] - self.origin[1])
        return v_dot(d, self.tangent), v_dot(d, self.normal)

    def vec_to_frame(self, v: Vec) -> Tuple[float, float]:
        return v_dot(v, self.tangent), v_dot(v, self.normal)

    def foot_angle_world(self) -> float:
        """Foot direction (relative to the character frame) for a flat foot: 0 when the body is upright on this frame."""
        return 0.0


def room_frames(width: float, height: float) -> dict:
    """Frames for the four inner surfaces of a room spanning x in [-w/2, w/2], y in [0, height]."""
    hw = width / 2
    return {
        "floor": GroundFrame("floor", (0.0, 0.0), (0.0, 1.0)),
        "wall_right": GroundFrame("wall_right", (hw, 0.0), (-1.0, 0.0)),
        "wall_left": GroundFrame("wall_left", (-hw, 0.0), (1.0, 0.0)),
        "ceiling": GroundFrame("ceiling", (0.0, height), (0.0, -1.0)),
    }
