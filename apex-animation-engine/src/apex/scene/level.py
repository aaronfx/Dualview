"""Level builder (Milestone 4): a character grid expanded into the engine's own structures.

The grid is a convenience for authors and planners: it produces ordinary platforms (standable, climbable, solid),
orbs and portals, so everything else (physics, QA, rendering) treats a grid level exactly like hand-placed geometry.
See `LevelSpec` for the legend.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

SOLID, LEDGE = "#", "="
ORBS = {"o": "jump", "b": "boost", "^": "pad", "*": "collect"}
EMPTY = " ."
LEDGE_FRAC = 0.25  # a ledge is this fraction of a cell thick, at the top of its cell


def _runs(row: str, ch: str) -> List[Tuple[int, int]]:
    out, c0 = [], None
    for c, x in enumerate(row + " "):
        if x == ch and c0 is None:
            c0 = c
        elif x != ch and c0 is not None:
            out.append((c0, c - 1))
            c0 = None
    return out


def _rects(rows: List[str], ch: str) -> List[Tuple[int, int, int, int]]:
    """Horizontal runs of `ch`, merged downwards with identical runs in the rows below: (c0, c1, r0, r1)."""
    rects: List[List[int]] = []
    open_: Dict[Tuple[int, int], List[int]] = {}
    for r, row in enumerate(rows):
        nxt = {}
        for c0, c1 in _runs(row, ch):
            if (c0, c1) in open_ and ch == SOLID:
                rc = open_[(c0, c1)]
                rc[3] = r
            else:
                rc = [c0, c1, r, r]
                rects.append(rc)
            nxt[(c0, c1)] = rc
        open_ = nxt
    return [tuple(x) for x in rects]


def expand(env) -> None:
    """Add the grid's platforms, orbs, portals and markers to `env` (an EnvironmentSpec)."""
    from .schema import ObstacleSpec, OrbSpec, PortalSpec
    lv = env.level
    cell, (ox, oy) = lv.cell, lv.origin
    rows = list(lv.rows)
    n = len(rows)
    width = max(len(r) for r in rows)
    rows = [r.ljust(width) for r in rows]
    hw = env.room.width / 2
    if ox < -hw - 1e-6 or ox + width * cell > hw + 1e-6:
        raise ValueError(f"level: {width} columns x {cell:g} from x={ox:g} do not fit the room (x {-hw:g}..{hw:g})")
    if oy + n * cell > env.room.height:
        raise ValueError(f"level: {n} rows x {cell:g} are taller than the room ({env.room.height:g})")
    known = set(SOLID + LEDGE + EMPTY) | set(ORBS)
    x_of = lambda c: ox + (c + 0.5) * cell  # cell centre
    y_bot = lambda r: oy + (n - 1 - r) * cell  # bottom of row r
    over = lambda ch, base: {**base, **lv.legend.get(ch, {})}
    k = 0
    for c0, c1, r0, r1 in _rects(rows, SOLID):
        x0, x1 = ox + c0 * cell, ox + (c1 + 1) * cell
        y0, y1 = y_bot(r1), y_bot(r0) + cell
        env.obstacles.append(ObstacleSpec(**over(SOLID, dict(id=f"lv_block{k}", kind="platform", center=((x0 + x1) / 2, (y0 + y1) / 2),
                                                             size=(x1 - x0, y1 - y0)))))
        k += 1
    for c0, c1, r0, _ in _rects(rows, LEDGE):
        x0, x1 = ox + c0 * cell, ox + (c1 + 1) * cell
        top, th = y_bot(r0) + cell, LEDGE_FRAC * cell
        env.obstacles.append(ObstacleSpec(**over(LEDGE, dict(id=f"lv_ledge{k}", kind="platform", center=((x0 + x1) / 2, top - th / 2),
                                                             size=(x1 - x0, th)))))
        k += 1
    letters: Dict[str, Tuple[int, int]] = {}
    counts: Dict[str, int] = {}
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch in ORBS:
                kind = ORBS[ch]
                counts[ch] = counts.get(ch, 0) + 1
                cy = y_bot(r) + (0.12 * cell if kind == "pad" else 0.5 * cell)
                env.orbs.append(OrbSpec(**over(ch, dict(id=f"{kind}{counts[ch]}", kind=kind, center=(x_of(c), cy),
                                                        radius=(0.42 if kind == "pad" else 0.36) * cell))))
            elif ch.isdigit():
                lv.markers[ch] = (x_of(c), y_bot(r))
            elif ch.isalpha():
                if ch in letters:
                    raise ValueError(f"level: portal {ch!r} appears twice")
                letters[ch] = (r, c)
            elif ch not in known:
                raise ValueError(f"level: unknown symbol {ch!r} in row {r}")
    for ch, (r, c) in letters.items():
        if ch.isupper() and ch.lower() not in letters:
            raise ValueError(f"level: portal {ch!r} has no partner {ch.lower()!r}")
        if ch.islower() and ch.upper() not in letters:
            raise ValueError(f"level: portal {ch!r} has no partner {ch.upper()!r}")
        row = rows[r]
        left = row[c - 1] if c > 0 else SOLID
        right = row[c + 1] if c + 1 < width else SOLID
        # open toward the free side; free on both sides: the entrance (capital) faces back toward -x, the exit faces +x
        angle = 0.0 if left == SOLID and right != SOLID else 180.0 if right == SOLID and left != SOLID else (180.0 if ch.isupper() else 0.0)
        base = dict(id=f"portal_{ch}", link=f"portal_{ch.swapcase()}", angle=angle, height=2.4 * cell)
        base = over(ch, base)
        base.setdefault("center", (x_of(c), y_bot(r) + base["height"] / 2))
        env.portals.append(PortalSpec(**base))
    lv.expanded = True
