"""Diagram layer (Milestone 5): annotations drawn from simulation data.

A diagram never carries a hand-written number. Velocities come from the simulation records, positions from the
evaluated scene, impulses from the engine events; QA re-derives each shown value independently (from the rendered
positions) and checks they agree. The layer returns plain drawing primitives in world space; the renderer draws them.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

Vec = Tuple[float, float]

COLORS = {"velocity": (120, 230, 255), "trajectory": (255, 214, 102), "label": (235, 245, 255), "measure": (180, 255, 170),
          "impulse": (255, 120, 120)}


@dataclass
class Prim:
    kind: str  # arrow | path | text | dim
    pts: List[Vec]
    rgb: Tuple[int, int, int]
    text: str = ""
    alpha: float = 1.0
    value: Optional[float] = None  # the number the primitive shows (QA re-derives it)
    vec: Optional[Vec] = None  # the vector an arrow shows (u/s), before scaling
    src: str = ""  # diagram id
    data: dict = field(default_factory=dict)


def _hex(h: Optional[str]):
    if not h:
        return None
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Diagrams:
    def __init__(self, rt):
        self.rt = rt
        self.r = rt.result
        self.specs = list(rt.scene.diagrams)
        self._tr = {}

    # ------------------------------------------------------------ data
    def point(self, ref: str, t: float) -> Vec:
        kind, _, rid = ref.partition(":")
        if kind == "point":
            x, y = (float(v) for v in rid.split(","))
            return (x, y)
        if kind == "char":  # the rendered body root: the point the physics moves (it does not swing round in a flip)
            return tuple(self.r.animators[rid].pose_at(t).root)
        fs = self.rt.evaluate(t)
        pr = next(p for p in fs.props if p.id == rid)
        return pr.pos

    def velocity(self, ref: str, t: float) -> Vec:
        """From the simulation records (characters) or the prop track (props)."""
        kind, _, rid = ref.partition(":")
        if kind == "char":  # how the body really moves: central difference of the simulated positions (240 Hz)
            an = self.r.animators[rid]
            T, X, Y = an.T, an.PX, an.PY
            i = int(np.clip(np.searchsorted(T, t), 1, len(T) - 2))
            a, b = i - 1, i + 1
            for c in an.cuts:  # never across a portal jump
                if T[a] < c <= T[b]:
                    a, b = (i, i + 1) if t >= c else (i - 1, i)
            return float((X[b] - X[a]) / (T[b] - T[a])), float((Y[b] - Y[a]) / (T[b] - T[a]))
        if kind == "prop":
            T, tr = self.r.prop_times, self.r.prop_tracks[rid]
            i = int(np.clip(np.searchsorted(T, t), 1, len(T) - 1))
            if i in self.r.prop_cuts.get(rid, ()):  # never across a jump
                i = min(i + 1, len(T) - 1)
            dt = T[i] - T[i - 1]
            return float((tr[i, 0] - tr[i - 1, 0]) / dt), float((tr[i, 1] - tr[i - 1, 1]) / dt)
        return (0.0, 0.0)

    def windows(self, d) -> List[Tuple[float, float]]:
        if d.t0 is not None:
            return [(d.t0, d.t1 if d.t1 is not None else d.t0 + d.duration)]
        from ..scene.goals import matches
        return [(e.t, e.t + d.duration) for e in self.r.events if matches(d.on, e)]

    # ------------------------------------------------------------ primitives
    def at(self, t: float) -> List[Prim]:
        out: List[Prim] = []
        for d in self.specs:
            for w0, w1 in self.windows(d):
                if not (w0 <= t <= w1):
                    continue
                fade = min(1.0, (t - w0) / 0.2, (w1 - t) / 0.25) if w1 > w0 else 1.0
                rgb = _hex(d.color) or COLORS[d.kind]
                out += self._prims(d, t, w0, max(0.0, fade), rgb)
        return out

    def _fill(self, d, t: float) -> Tuple[str, Optional[float]]:
        v = self.velocity(d.target, t)
        sp = math.hypot(*v)
        p = self.point(d.target, t)
        kind, _, rid = d.target.partition(":")
        mass = None
        if kind == "prop":
            mass = next(x.mass for x in self.rt.env.props if x.id == rid)
        name = self.rt.project.character(rid).name if kind == "char" else rid
        txt = (d.text or "{speed}").format(speed=f"{sp:.0f} {d.unit}/s", height=f"{p[1]:.0f} {d.unit}",
                                           mass=f"{mass:g} kg" if mass is not None else "", name=name)
        return txt, sp

    def _prims(self, d, t: float, w0: float, a: float, rgb) -> List[Prim]:
        if d.kind == "velocity":
            p = self.point(d.target, t)
            v = self.velocity(d.target, t)
            sp = math.hypot(*v)
            tip = (p[0] + v[0] * d.scale, p[1] + v[1] * d.scale)
            return [Prim("arrow", [p, tip], rgb, f"{sp:.0f} {d.unit}/s" if d.text is None else self._fill(d, t)[0], a, sp, v, d.id)]
        if d.kind == "trajectory":
            n = max(2, int((t - w0) * 48))
            pts = [self.point(d.target, w0 + (t - w0) * k / (n - 1)) for k in range(n)]
            return [Prim("path", pts, rgb, "", a, None, None, d.id)]
        if d.kind == "label":
            txt, sp = self._fill(d, t)
            p = self.point(d.target, t)
            return [Prim("text", [(p[0], p[1] + 120.0)], rgb, txt, a, sp, None, d.id)]
        if d.kind == "measure":
            pa, pb = self.point(d.target, t), self.point(d.to, t)
            dist = math.dist(pa, pb)
            return [Prim("dim", [pa, pb], rgb, f"{dist:.0f} {d.unit}", a, dist, None, d.id)]
        if d.kind == "impulse":
            out = []
            kind, _, rid = d.target.partition(":")
            for e in self.r.events:
                if e.character != rid or not (e.t <= t <= e.t + d.duration):
                    continue
                if e.type.startswith("orb_") and "v_after" in e.data:
                    dv = (e.data["v_after"][0] - e.data["v_before"][0], e.data["v_after"][1] - e.data["v_before"][1])
                    p = e.data["point"]
                    out.append(Prim("arrow", [p, (p[0] + dv[0] * d.scale, p[1] + dv[1] * d.scale)], rgb,
                                    f"Δv {math.hypot(*dv):.0f} {d.unit}/s", a, math.hypot(*dv), dv, d.id, {"event": e.type, "t": e.t}))
                elif e.type == "break":
                    p = e.data["point"]
                    out.append(Prim("text", [(p[0], p[1] + 70.0)], rgb, f"impulse {e.data['impulse']:.0f}", a, e.data["impulse"], None, d.id,
                                    {"event": "break"}))
            return out
        return []
