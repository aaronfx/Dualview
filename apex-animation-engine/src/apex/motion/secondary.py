"""Secondary motion: physically simulated details that react to the character and to gravity.

Both systems are simulated once, deterministically, after the main simulation, and then sampled by time, so
`evaluate(t)` stays a pure function.
  * ScarfSim   - two-tail verlet rope pinned to the rig's neck; driven by the gravity field and by the character's
                 own motion (drag against still air gives streaming when running/falling, overshoot when stopping).
  * DustField  - ambient particles that drift with the gravity field and react to impacts; they make the gravity
                 direction visible without rotating the scene.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..core.mathx import Vec, v_rot
from ..physics.gravity import GravityField

SC_HZ = 240


class ScarfSim:
    TAILS = ((10, 6.6, 0.0), (7, 6.0, -3.5))  # (nodes, segment length, anchor drop along the neck)

    def __init__(self, pose_at, rig, gravity: GravityField, bounds: Tuple[float, float, float, float], t0: float, t1: float,
                 seed: int = 3, gravity_scale: float = 0.55, damping: float = 3.4):
        self.t0, self.dt = t0, 1.0 / SC_HZ
        n = int(math.ceil((t1 - t0) * SC_HZ)) + 2
        self.n = n
        self.data = [np.zeros((n, k, 2), dtype=np.float64) for (k, _, _) in self.TAILS]
        self.anchor_err = 0.0
        xmin, ymin, xmax, ymax = bounds
        rng = np.random.default_rng(seed)
        phase = rng.uniform(0, 100, size=8)
        state = []
        for (k, seg, drop) in self.TAILS:
            a = self._anchor(pose_at(t0), rig, drop)
            P = np.array([[a[0] - i * seg * 0.7, a[1] - i * seg * 0.7] for i in range(k)])
            state.append((P, P.copy()))
        for step in range(n):
            t = t0 + step * self.dt
            pose = pose_at(t)
            g = gravity.at(t)
            gx, gy = g[0] * gravity_scale, g[1] * gravity_scale
            damp = math.exp(-damping * self.dt)
            for ti, ((k, seg, drop), (P, Q)) in enumerate(zip(self.TAILS, state)):
                a = self._anchor(pose, rig, drop)
                V = (P - Q) * damp
                Q[:] = P
                flutter = 60.0 * np.sin(t * 8.0 + np.arange(k) * 0.7 + phase[ti])
                gn = math.hypot(gx, gy) or 1.0
                P[:, 0] += V[:, 0] + (gx + flutter * (gy / gn)) * self.dt ** 2
                P[:, 1] += V[:, 1] + (gy - flutter * (gx / gn)) * self.dt ** 2
                P[0] = a
                for _ in range(8):
                    for i in range(1, k):  # rope: resist stretch strongly, compression weakly (cloth buckles)
                        d = P[i] - P[i - 1]
                        L = math.hypot(d[0], d[1]) or 1e-9
                        df = max(L - seg, (L - seg) * 0.15) / L
                        if i == 1:
                            P[i] -= d * df
                        else:
                            P[i - 1] += d * df * 0.5
                            P[i] -= d * df * 0.5
                    for i in range(2, k):  # weak bending stiffness
                        d = P[i] - P[i - 2]
                        L = math.hypot(d[0], d[1]) or 1e-9
                        mn = seg * 1.35
                        if L < mn:
                            df = (L - mn) / L * 0.3
                            if i - 2 > 0:
                                P[i - 2] += d * df
                            P[i] -= d * df
                    P[0] = a
                    np.clip(P[:, 0], xmin + 1, xmax - 1, out=P[:, 0])  # cloth never passes through the room
                    np.clip(P[:, 1], ymin + 1, ymax - 1, out=P[:, 1])
                self.data[ti][step] = P
                self.anchor_err = max(self.anchor_err, float(np.hypot(*(P[0] - a))))

    @staticmethod
    def _anchor(pose, rig, drop: float) -> Vec:
        j = rig.world_joints(pose)
        nb, nt = j["neck_base"], j["neck_top"]
        back = v_rot((-pose.facing, 0.0), pose.body_angle)
        up = (nt[0] - nb[0], nt[1] - nb[1])
        L = math.hypot(*up) or 1.0
        return (nb[0] + up[0] * 0.3 + back[0] * 3.5 + up[0] / L * drop, nb[1] + up[1] * 0.3 + back[1] * 3.5 + up[1] / L * drop)

    def at(self, t: float) -> List[np.ndarray]:
        f = min(max((t - self.t0) / self.dt, 0.0), self.n - 1.001)
        i = int(f)
        u = f - i
        return [d[i] * (1 - u) + d[i + 1] * u for d in self.data]

    def max_stretch(self) -> float:
        worst = 0.0
        for (k, seg, _), d in zip(self.TAILS, self.data):
            L = np.hypot(*(np.diff(d, axis=1).transpose(2, 0, 1)))
            worst = max(worst, float(L.max() / seg))
        return worst


class DustField:
    HZ = 60

    def __init__(self, n: int, room, gravity: GravityField, impulses: Sequence[Tuple[float, Vec, float]], t1: float, seed: int = 11):
        self.dt = 1.0 / self.HZ
        steps = int(math.ceil(t1 * self.HZ)) + 2
        self.steps = steps
        rng = np.random.default_rng(seed)
        hw, rh = room.width / 2, room.height
        z0, z1 = room.depth_front + 20, room.depth_back - 20
        P = np.stack([rng.uniform(-hw + 5, hw - 5, n), rng.uniform(5, rh - 5, n) ** 1.0, rng.uniform(z0, z1, n)], 1)
        V = np.zeros_like(P)
        self.size = rng.uniform(0.6, 1.0, n)
        self.data = np.zeros((steps, n, 3), dtype=np.float32)
        lo = np.array([-hw + 2, 2, z0])
        hi = np.array([hw - 2, rh - 2, z1])
        ph = rng.uniform(0, 100, (n, 3))
        for k in range(steps):
            t = k * self.dt
            g = gravity.at(t)
            gm = math.hypot(*g) or 1.0
            acc = np.array([g[0] / gm, g[1] / gm, 0.0]) * 120.0
            wander = 18.0 * np.sin(t * np.array([0.7, 0.9, 0.5]) + ph)
            V += (acc + wander - V * 2.0) * self.dt
            for (te, c, mag) in impulses:
                if te <= t < te + self.dt:
                    d = P[:, :2] - np.array(c)
                    r = np.hypot(d[:, 0], d[:, 1]) + 1
                    s = mag * np.exp(-r / 300.0) / r
                    V[:, 0] += d[:, 0] * s
                    V[:, 1] += d[:, 1] * s
            P += V * self.dt
            under, over = P < lo, P > hi
            P = np.clip(P, lo, hi)
            V[under | over] = 0.0
            self.data[k] = P

    def at(self, t: float) -> np.ndarray:
        f = min(max(t / self.dt, 0.0), self.steps - 1.001)
        i = int(f)
        u = f - i
        return self.data[i] * (1 - u) + self.data[i + 1] * u
