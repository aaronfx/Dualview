"""Event-driven particles (Milestone 4).

Each burst is born from an engine event (an orb firing, a pick-up, a portal crossing, a hard landing, a blow) and its
particles are evaluated in closed form at any time: position = start + drag-damped velocity + gravity, fading over the
particle's life. Nothing is integrated frame by frame, so a frame renders the same whatever was rendered before it
(deterministic, safe under motion-blur sub-samples, hit-stops and partial re-renders). Each burst's randomness comes
from its own seed (project seed, burst index).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MAX_ALIVE = 900  # hard cap on simultaneously drawn particles (budget; QA checks it)
DRAG = 3.2  # 1/s: velocity decays as exp(-DRAG t)


@dataclass
class Burst:
    t0: float
    origin: Tuple[float, float]
    kind: str
    p0: np.ndarray  # (n, 2) start offsets
    v0: np.ndarray  # (n, 2) start velocities
    life: np.ndarray  # (n,)
    size: np.ndarray  # (n,)
    rgb: Tuple[int, int, int]
    gravity: float  # downward acceleration (u/s^2); sparks fall, glows float
    z: float = 0.0


STYLE = {  # kind -> n, speed range, life range, size range, gravity, colour
    "orb": (30, (160, 380), (0.4, 0.7), (2.2, 4.4), -200.0, (255, 226, 90)),
    "boost": (20, (220, 420), (0.25, 0.45), (1.6, 3.2), 0.0, (255, 110, 230)),
    "collect": (34, (110, 280), (0.55, 1.0), (1.8, 3.8), -120.0, (255, 246, 190)),
    "portal": (36, (80, 220), (0.45, 0.8), (2.0, 4.0), 0.0, (120, 210, 255)),
    "dust": (12, (60, 180), (0.35, 0.6), (2.5, 5.0), 260.0, (170, 180, 190)),
    "spark": (14, (300, 640), (0.15, 0.32), (1.2, 2.4), 900.0, (255, 190, 90)),
    "debris": (30, (120, 420), (0.35, 0.75), (1.4, 3.2), 1100.0, (255, 235, 200)),
}


def _color(env, e) -> Optional[Tuple[int, int, int]]:
    from .skia_renderer import hex_rgb
    if e.type.startswith("orb_") or e.type == "collect":
        o = next((o for o in env.orbs if o.id == e.data.get("orb")), None)
        return hex_rgb(o.color) if o is not None and o.color else None
    if e.type.startswith("portal_"):
        pid = e.data.get("portal")
        p = next((p for p in env.portals if p.id == pid), None)
        return hex_rgb(p.color) if p is not None and p.color else portal_rgb(env, pid)
    return None


PORTAL_PAIRS = ((255, 150, 60), (70, 190, 255), (150, 255, 120), (255, 90, 160), (190, 140, 255))


def portal_rgb(env, pid: str) -> Tuple[int, int, int]:
    """Default portal colours: both ends of a pair share a hue family; the entrance is warmer, the exit cooler."""
    from .skia_renderer import hex_rgb
    p = next((p for p in env.portals if p.id == pid), None)
    if p is not None and p.color:
        return hex_rgb(p.color)
    pairs = sorted({tuple(sorted((q.id, q.link))) for q in env.portals})
    for i, (a, b) in enumerate(pairs):
        if pid in (a, b):
            base = PORTAL_PAIRS[i % len(PORTAL_PAIRS)]
            return base if pid == a else tuple(int(0.55 * c + 0.45 * 255) for c in base)
    return PORTAL_PAIRS[0]


class Particles:
    def __init__(self, events: Sequence, env, seed: int = 7):
        self.bursts: List[Burst] = []
        idx = 0
        for e in sorted(events, key=lambda e: (e.t, e.type, e.character)):
            kind = None
            pt = e.data.get("point")
            if e.type in ("orb_jump", "orb_pad"):
                kind = "orb"
            elif e.type == "orb_boost":
                kind = "boost"
            elif e.type == "collect":
                kind = "collect"
            elif e.type in ("portal_enter", "portal_exit"):
                kind = "portal"
            elif e.type == "impact" and e.data.get("normal_speed", 0) > 650:
                kind = "dust"
            elif e.type == "hit":
                kind = "spark"
            elif e.type in ("break", "creature_break", "collapse"):
                kind = "debris"
            elif e.type == "morph":
                kind = "collect"  # a shimmer where the new shape appears
            if kind is None or not isinstance(pt, (tuple, list)):
                continue
            idx += 1
            n, (v_lo, v_hi), (l_lo, l_hi), (s_lo, s_hi), grav, rgb = STYLE[kind]
            rgb = _color(env, e) or rgb
            rng = np.random.default_rng([seed, idx])  # its own stream: adding a burst never changes another one
            ang = rng.uniform(0, 2 * math.pi, n)
            sp = rng.uniform(v_lo, v_hi, n)
            p0 = np.zeros((n, 2))
            if kind == "dust":  # kicked up along the floor
                ang = np.where(rng.random(n) < 0.5, rng.uniform(0.05, 0.6, n), rng.uniform(math.pi - 0.6, math.pi - 0.05, n))
            if kind == "portal":  # a swirl on the portal's ring
                p = next((p for p in env.portals if p.id == e.data.get("portal")), None)
                h = (p.height if p else 140.0) / 2
                u = rng.uniform(-1, 1, n)
                ra = math.radians(p.angle if p else 0.0)
                tx, ty = -math.sin(ra), math.cos(ra)
                p0 = np.stack([u * h * tx, u * h * ty], 1)
                ang = np.full(n, ra) + rng.normal(0, 0.5, n)
            v0 = np.stack([np.cos(ang) * sp, np.sin(ang) * sp], 1)
            self.bursts.append(Burst(e.t, (float(pt[0]), float(pt[1])), kind, p0, v0, rng.uniform(l_lo, l_hi, n),
                                     rng.uniform(s_lo, s_hi, n), tuple(int(c) for c in rgb), grav))

    def at(self, t: float) -> List[Tuple[float, float, float, float, Tuple[int, int, int]]]:
        """The particles alive at story time t: (x, y, radius, alpha, rgb), oldest bursts first, at most MAX_ALIVE."""
        out = []
        for b in self.bursts:
            a = t - b.t0
            if a < 0 or a > float(b.life.max()):
                continue
            k = (1.0 - math.exp(-DRAG * a)) / DRAG
            x = b.origin[0] + b.p0[:, 0] + b.v0[:, 0] * k
            y = b.origin[1] + b.p0[:, 1] + b.v0[:, 1] * k - 0.5 * b.gravity * a * a
            u = np.clip(a / b.life, 0.0, 1.0)
            alive = u < 1.0
            alpha = (1.0 - u) ** 1.6
            r = b.size * (1.0 + 0.4 * u)
            for i in np.nonzero(alive)[0]:
                out.append((float(x[i]), float(y[i]), float(r[i]), float(alpha[i]), b.rgb))
        return out[-MAX_ALIVE:]

    def count_at(self, t: float) -> int:
        return len(self.at(t))
