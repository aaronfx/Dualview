"""Symbols as geometry: each glyph is a set of strokes (polylines) in a unit box [-0.5, 0.5]^2 (y up).

One definition drives everything a symbol does in a scene:
- physics: every stroke segment is a rounded segment (a capsule) of radius weight/2;
- standing: near-horizontal strokes of a fixed glyph are support surfaces (see scene/structures.py);
- rendering: thick, round-capped, glowing strokes.

The glyph shapes are plain typographic constructions (straight strokes and arcs), drawn for this engine.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

Pt = Tuple[float, float]


def _arc(cx: float, cy: float, rx: float, ry: float, a0: float, a1: float, n: int = 10) -> List[Pt]:
    """Points on an elliptical arc from angle a0 to a1 (degrees, CCW from +x)."""
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


DOT = 0.012  # a dot is a very short stroke (it renders and collides as a round blob)

GLYPHS: Dict[str, List[List[Pt]]] = {
    "+": [[(-0.5, 0.0), (0.5, 0.0)], [(0.0, -0.5), (0.0, 0.5)]],
    "-": [[(-0.5, 0.0), (0.5, 0.0)]],
    "x": [[(-0.45, -0.5), (0.45, 0.5)], [(-0.45, 0.5), (0.45, -0.5)]],
    "÷": [[(-0.5, 0.0), (0.5, 0.0)], [(-DOT, 0.36), (DOT, 0.36)], [(-DOT, -0.36), (DOT, -0.36)]],
    "=": [[(-0.5, 0.2), (0.5, 0.2)], [(-0.5, -0.2), (0.5, -0.2)]],
    "<": [[(0.45, 0.45), (-0.45, 0.0), (0.45, -0.45)]],
    ">": [[(-0.45, 0.45), (0.45, 0.0), (-0.45, -0.45)]],
    "!": [[(0.0, 0.5), (0.0, -0.2)], [(-DOT, -0.46), (DOT, -0.46)]],
    "?": [_arc(0.0, 0.22, 0.34, 0.27, 160, -60, 10) + [(0.0, -0.1), (0.0, -0.22)], [(-DOT, -0.46), (DOT, -0.46)]],
    "π": [[(-0.5, 0.38), (0.5, 0.38)], [(-0.22, 0.38), (-0.28, -0.5)], [(0.22, 0.38), (0.24, -0.4), (0.38, -0.5)]],
    "√": [[(-0.5, -0.02), (-0.32, 0.06), (-0.1, -0.5), (0.18, 0.5), (0.5, 0.5)]],
    "0": [_arc(0.0, 0.0, 0.4, 0.5, 0, 360, 24)],
    "1": [[(-0.2, 0.32), (0.06, 0.5), (0.06, -0.5)], [(-0.26, -0.5), (0.36, -0.5)]],
    "2": [_arc(0.0, 0.2, 0.36, 0.3, 160, -35, 9) + [(-0.4, -0.5), (0.42, -0.5)]],
    "3": [_arc(0.0, 0.25, 0.32, 0.25, 150, -90, 9), _arc(0.0, -0.25, 0.36, 0.25, 90, -150, 9)],
    "4": [[(0.18, -0.5), (0.18, 0.5), (-0.42, -0.12), (0.45, -0.12)]],
    "5": [[(0.38, 0.5), (-0.3, 0.5), (-0.34, 0.06)] + _arc(0.0, -0.18, 0.38, 0.32, 125, -150, 10)],
    "6": [_arc(0.0, 0.0, 0.38, 0.5, 70, 180, 7) + _arc(0.0, -0.2, 0.38, 0.3, 180, 540, 16)[1:]],
    "7": [[(-0.42, 0.5), (0.42, 0.5), (-0.08, -0.5)]],
    "8": [_arc(0.0, 0.26, 0.3, 0.24, -90, 270, 16), _arc(0.0, -0.24, 0.36, 0.26, 90, 450, 16)],
    "9": [_arc(0.0, 0.2, 0.38, 0.3, 0, 360, 16), _arc(0.0, 0.0, 0.38, 0.5, 0, -110, 7)],
}
ALIASES = {"−": "-", "–": "-", "×": "x", "*": "x", "/": "÷"}
NAMES = {"+": "plus", "-": "minus", "x": "times", "÷": "divide", "=": "equals", "<": "less", ">": "greater", "!": "bang",
         "?": "question", "π": "pi", "√": "root"}


def canonical(g: str) -> str:
    g = ALIASES.get(g, g)
    if g not in GLYPHS:
        raise ValueError(f"unknown glyph {g!r}; available: {' '.join(sorted(GLYPHS))}")
    return g


def strokes(glyph: str, size: Sequence[float]) -> List[List[Pt]]:
    """The glyph's strokes in the body's local frame, scaled to `size` (width, height)."""
    sx, sy = size
    return [[(u * sx, v * sy) for u, v in st] for st in GLYPHS[canonical(glyph)]]


def segments(glyph: str, size: Sequence[float]) -> List[Tuple[Pt, Pt]]:
    out = []
    for st in strokes(glyph, size):
        out += list(zip(st, st[1:]))
    return out


def default_weight(size: Sequence[float]) -> float:
    return max(6.0, 0.15 * min(size[0], size[1]) if min(size) > 0 else 6.0)


def flat_tops(glyph: str, size: Sequence[float], weight: float, min_len: float = 24.0) -> List[Tuple[float, float, float]]:
    """Standable tops of a fixed glyph, in local coordinates: (x_lo, x_hi, y_top) for each near-horizontal stroke run
    that has free space above it."""
    r = weight / 2
    tops = []
    for a, b in segments(glyph, size):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) < min_len or abs(dy) > 0.12 * abs(dx):
            continue
        lo, hi = min(a[0], b[0]), max(a[0], b[0])
        tops.append((lo - 0.4 * r, hi + 0.4 * r, max(a[1], b[1]) + r))
    return tops


def mass_props(glyph: str, size: Sequence[float], weight: float, mass: float):
    """(centroid, per-segment masses) with the mass spread along the strokes by length."""
    segs = segments(glyph, size)
    lens = [max(1e-3, math.dist(a, b)) for a, b in segs]
    tot = sum(lens)
    cx = sum((a[0] + b[0]) / 2 * L for (a, b), L in zip(segs, lens)) / tot
    cy = sum((a[1] + b[1]) / 2 * L for (a, b), L in zip(segs, lens)) / tot
    return (cx, cy), [mass * L / tot for L in lens]


def extent(glyph: str, size: Sequence[float], weight: float) -> Tuple[float, float, float, float]:
    r = weight / 2
    pts = [p for st in strokes(glyph, size) for p in st]
    return (min(p[0] for p in pts) - r, min(p[1] for p in pts) - r, max(p[0] for p in pts) + r, max(p[1] for p in pts) + r)
