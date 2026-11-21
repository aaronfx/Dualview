"""Small, dependency-light 2D math helpers used across the engine.

World convention: x to the right, y up, units ~ centimetres. Angles in radians, counter-clockwise.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, Sequence, Tuple

Vec = Tuple[float, float]
TAU = math.tau


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, u: float) -> float:
    return a + (b - a) * u


def inv_lerp(a: float, b: float, v: float) -> float:
    if b == a:
        return 0.0
    return clamp((v - a) / (b - a), 0.0, 1.0)


def smoothstep(a: float, b: float, v: float) -> float:
    u = inv_lerp(a, b, v)
    return u * u * (3 - 2 * u)


def wrap_angle(a: float) -> float:
    """Wrap to (-pi, pi]."""
    a = math.fmod(a + math.pi, TAU)
    if a <= 0:
        a += TAU
    return a - math.pi


def lerp_angle(a: float, b: float, u: float) -> float:
    """Interpolate along the shortest arc."""
    return a + wrap_angle(b - a) * u


def v_add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def v_sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def v_scale(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s)


def v_len(a: Vec) -> float:
    return math.hypot(a[0], a[1])


def v_dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def v_cross(a: Vec, b: Vec) -> float:
    return a[0] * b[1] - a[1] * b[0]


def v_norm(a: Vec) -> Vec:
    n = v_len(a)
    return (0.0, 0.0) if n == 0 else (a[0] / n, a[1] / n)


def v_rot(a: Vec, ang: float) -> Vec:
    c, s = math.cos(ang), math.sin(ang)
    return (a[0] * c - a[1] * s, a[0] * s + a[1] * c)


def v_lerp(a: Vec, b: Vec, u: float) -> Vec:
    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u))


def angle_of(a: Vec) -> float:
    return math.atan2(a[1], a[0])


def from_angle(ang: float, length: float = 1.0) -> Vec:
    return (math.cos(ang) * length, math.sin(ang) * length)


# ---------------------------------------------------------------- easing
def _ease_in_out_cubic(u: float) -> float:
    return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


EASES: dict[str, Callable[[float], float]] = {
    "linear": lambda u: u,
    "in": lambda u: u ** 3,
    "out": lambda u: 1 - (1 - u) ** 3,
    "in_out": _ease_in_out_cubic,
    "in2": lambda u: u * u,
    "out2": lambda u: 1 - (1 - u) ** 2,
    "in_out2": lambda u: 2 * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 2 / 2,
    "back_out": lambda u: 1 + 2.70158 * (u - 1) ** 3 + 1.70158 * (u - 1) ** 2,
    "hold": lambda u: 0.0,
    "sine": lambda u: 0.5 - 0.5 * math.cos(math.pi * u),  # gentlest in-out (peak rate pi/2 x average)
}


def ease(name: str, u: float) -> float:
    return EASES[name](clamp(u, 0.0, 1.0))


def damped_spring(x0: float, v0: float, target: float, omega: float, zeta: float, t: float) -> Tuple[float, float]:
    """Closed-form damped harmonic oscillator; returns (x, v) after time t.

    Used for physically motivated secondary motion (landing compression, balance wobble).
    """
    x = x0 - target
    if t <= 0:
        return x0, v0
    if zeta < 1.0:
        wd = omega * math.sqrt(1 - zeta * zeta)
        e = math.exp(-zeta * omega * t)
        a = x
        b = (v0 + zeta * omega * x) / wd
        xt = e * (a * math.cos(wd * t) + b * math.sin(wd * t))
        vt = e * ((-zeta * omega) * (a * math.cos(wd * t) + b * math.sin(wd * t)) + (-a * wd * math.sin(wd * t) + b * wd * math.cos(wd * t)))
    elif zeta == 1.0:
        e = math.exp(-omega * t)
        b = v0 + omega * x
        xt = e * (x + b * t)
        vt = e * (b - omega * (x + b * t))
    else:
        r = omega * math.sqrt(zeta * zeta - 1)
        r1, r2 = -zeta * omega + r, -zeta * omega - r
        c2 = (v0 - r1 * x) / (r2 - r1)
        c1 = x - c2
        xt = c1 * math.exp(r1 * t) + c2 * math.exp(r2 * t)
        vt = c1 * r1 * math.exp(r1 * t) + c2 * r2 * math.exp(r2 * t)
    return xt + target, vt


def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def poly_bounds(pts: Sequence[Vec]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)
