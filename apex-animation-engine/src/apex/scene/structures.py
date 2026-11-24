"""Fixed structures a character can stand on, bump into, vault over or climb: `platform` boxes and `glyph` symbols.

Each standable top becomes a support frame with extents, so walking past an end steps off it. Frame keys are
the obstacle id for a platform and "<id>.<k>" for the k-th standable stroke of a glyph. The physics shapes carry
the same tags, so a landing contact names its frame directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..motion.frames import GroundFrame
from . import glyphs as G
from .schema import EnvironmentSpec, ObstacleSpec

STANDABLE = ("platform", "glyph")


@dataclass
class Block:
    """A solid region (axis-aligned bounds) of a structure that a walking character may not pass through."""
    owner: str
    x0: float
    x1: float
    y0: float
    y1: float


def glyph_weight(ob) -> float:
    return ob.weight or G.default_weight(ob.size)


def top_frames(env: EnvironmentSpec) -> Dict[str, GroundFrame]:
    out: Dict[str, GroundFrame] = {}
    for ob in env.obstacles:
        cx, cy = ob.center
        if ob.kind == "platform":
            top = cy + ob.size[1] / 2
            out[ob.id] = GroundFrame(ob.id, (0.0, top), (0.0, 1.0), cx - ob.size[0] / 2, cx + ob.size[0] / 2, ob.id)
        elif ob.kind == "glyph":
            for k, (lo, hi, y) in enumerate(G.flat_tops(ob.glyph, ob.size, glyph_weight(ob))):
                key = f"{ob.id}.{k}"
                out[key] = GroundFrame(key, (0.0, cy + y), (0.0, 1.0), cx + lo, cx + hi, ob.id)
    return out


def shape_tags(ob: ObstacleSpec) -> List[Tuple[Tuple[float, float], Tuple[float, float], float, str]]:
    """Static capsule segments of a glyph structure in world space, each tagged with its frame key (or the id)."""
    cx, cy = ob.center
    w = glyph_weight(ob)
    tops = G.flat_tops(ob.glyph, ob.size, w)
    out = []
    for a, b in G.segments(ob.glyph, ob.size):
        tag = ob.id
        for k, (lo, hi, y) in enumerate(tops):
            if abs(max(a[1], b[1]) + w / 2 - y) < 1e-6 and lo - 1e-6 <= min(a[0], b[0]) + 0.4 * w / 2 and max(a[0], b[0]) - 0.4 * w / 2 <= hi + 1e-6:
                tag = f"{ob.id}.{k}"
                break
        out.append(((cx + a[0], cy + a[1]), (cx + b[0], cy + b[1]), w / 2, tag))
    return out


def blocks(env: EnvironmentSpec) -> List[Block]:
    out: List[Block] = []
    for ob in env.obstacles:
        cx, cy = ob.center
        if ob.kind in ("platform", "beam"):
            out.append(Block(ob.id, cx - ob.size[0] / 2, cx + ob.size[0] / 2, cy - ob.size[1] / 2, cy + ob.size[1] / 2))
        elif ob.kind == "glyph":
            for a, b, r, _ in shape_tags(ob):
                out.append(Block(ob.id, min(a[0], b[0]) - r, max(a[0], b[0]) + r, min(a[1], b[1]) - r, max(a[1], b[1]) + r))
    return out


def obstacle_top(env: EnvironmentSpec, frames: Dict[str, GroundFrame], ob_id: str, near_s: Optional[float] = None) -> GroundFrame:
    """The standable top of a structure (for a glyph with several, the one nearest `near_s`, else the highest)."""
    cands = [f for f in frames.values() if f.owner == ob_id]
    if not cands:
        raise ValueError(f"obstacle {ob_id} has no standable top (a platform, or a glyph with a flat stroke)")
    if near_s is None:
        return max(cands, key=lambda f: f.origin[1])
    return min(cands, key=lambda f: (0.0 if f.lo <= near_s <= f.hi else min(abs(near_s - f.lo), abs(near_s - f.hi)), -f.origin[1]))


def obstacle_bounds(env: EnvironmentSpec, ob_id: str) -> Tuple[float, float, float, float]:
    bs = [b for b in blocks(env) if b.owner == ob_id]
    if not bs:
        raise ValueError(f"unknown structure {ob_id}")
    return min(b.x0 for b in bs), max(b.x1 for b in bs), min(b.y0 for b in bs), max(b.y1 for b in bs)
