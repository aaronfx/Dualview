"""Hierarchical 2D skeleton with forward kinematics.

Angle conventions (character frame: facing +x, up +y):
  * a root bone's local angle is its absolute angle in the character frame;
  * a child bone's local angle is relative to its parent's absolute angle.
The character frame is mapped to the world by: mirror x by `facing`, scale (squash/stretch about a pivot),
rotate by `body_angle` (0 = upright in world), translate to `root` (pelvis position).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.mathx import Vec, clamp, v_add, v_rot

DEG = math.pi / 180


@dataclass(frozen=True)
class Bone:
    name: str
    parent: Optional[str]
    length: float
    rest: float  # rest local angle (radians)
    attach: float = 1.0  # where along the parent the bone starts (0 = parent start, 1 = parent end)
    limits: Optional[Tuple[float, float]] = None  # local-angle limits (radians)


@dataclass
class Skeleton:
    bones: List[Bone]
    _index: Dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._index = {}
        for i, b in enumerate(self.bones):
            if b.name in self._index:
                raise ValueError(f"duplicate bone {b.name}")
            if b.parent is not None and b.parent not in self._index:
                raise ValueError(f"bone {b.name} listed before its parent {b.parent}")
            if b.length <= 0:
                raise ValueError(f"bone {b.name} must have positive length")
            self._index[b.name] = i

    def __getitem__(self, name: str) -> Bone:
        return self.bones[self._index[name]]

    def names(self) -> List[str]:
        return [b.name for b in self.bones]

    def children(self, name: str) -> List[str]:
        return [b.name for b in self.bones if b.parent == name]

    def rest_angles(self) -> Dict[str, float]:
        return {b.name: b.rest for b in self.bones}

    def chain_length(self, *names: str) -> float:
        return sum(self[n].length for n in names)

    def clamp_to_limits(self, local: Dict[str, float]) -> Dict[str, float]:
        out = dict(local)
        for b in self.bones:
            if b.limits and b.name in out:
                out[b.name] = clamp(out[b.name], *b.limits)
        return out

    # ------------------------------------------------------------------ FK
    def fk_character(self, local: Dict[str, float], stretch: Optional[Dict[str, float]] = None) -> Dict[str, Tuple[Vec, Vec, float]]:
        """Forward kinematics in the character frame. Returns name -> (start, end, absolute_angle)."""
        out: Dict[str, Tuple[Vec, Vec, float]] = {}
        for b in self.bones:
            ang = local.get(b.name, b.rest)
            L = b.length * (stretch.get(b.name, 1.0) if stretch else 1.0)
            if b.parent is None:
                start: Vec = (0.0, 0.0)
                absang = ang
            else:
                ps, pe, pa = out[b.parent]
                start = (ps[0] + (pe[0] - ps[0]) * b.attach, ps[1] + (pe[1] - ps[1]) * b.attach)
                absang = pa + ang
            end = (start[0] + math.cos(absang) * L, start[1] + math.sin(absang) * L)
            out[b.name] = (start, end, absang)
        return out


def to_world(p: Vec, root: Vec, body_angle: float, facing: float, scale: Tuple[float, float] = (1.0, 1.0), pivot_y: float = 0.0) -> Vec:
    """Map a character-frame point into world space."""
    x = p[0] * facing * scale[0]
    y = pivot_y + (p[1] - pivot_y) * scale[1]
    return v_add(root, v_rot((x, y), body_angle))


def to_character(p: Vec, root: Vec, body_angle: float, facing: float) -> Vec:
    """Inverse of `to_world` (ignoring squash/stretch)."""
    q = v_rot((p[0] - root[0], p[1] - root[1]), -body_angle)
    return (q[0] * (1 if facing >= 0 else -1), q[1])
