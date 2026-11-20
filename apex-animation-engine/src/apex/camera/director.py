"""Cinematic camera director.

Per-shot camera rigs (static, follow, track_x, dolly) evaluated at a fixed internal rate with critically damped
smoothing that resets at cuts. A framing guard keeps the subject's whole body inside a safe area so fast action
stays readable (it widens / re-centres the view rather than letting limbs leave the frame).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..core.mathx import Vec, clamp, ease, lerp
from ..scene.schema import CameraSpec, ShotSpec

INTERNAL_HZ = 120
SAFE = 0.82  # fraction of the frame the subject must fit in


@dataclass
class CameraState:
    cx: float
    cy: float
    view_h: float  # world units visible vertically at the subject plane (z = 0)
    roll: float  # degrees
    shot: str

    def valid(self) -> bool:
        return all(math.isfinite(v) for v in (self.cx, self.cy, self.view_h, self.roll)) and self.view_h > 1


BBoxFn = Callable[[str, float], Tuple[float, float, float, float]]  # (character, t) -> xmin, ymin, xmax, ymax
VelFn = Callable[[str, float], Vec]


class CameraDirector:
    def __init__(self, shots: List[ShotSpec], aspect: float, bbox: BBoxFn, velocity: VelFn):
        self.shots = sorted(shots, key=lambda s: s.start)
        self.aspect = aspect
        self.bbox, self.velocity = bbox, velocity
        self._tracks: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        for sh in self.shots:
            self._tracks[sh.id] = self._bake(sh)

    def shot_at(self, t: float) -> ShotSpec:
        for sh in self.shots:
            if sh.start <= t < sh.end:
                return sh
        return self.shots[-1]

    def _target(self, cam: CameraSpec, sh: ShotSpec, t: float) -> Tuple[float, float, float]:
        u = (t - sh.start) / max(1e-6, sh.end - sh.start)
        vh = cam.view_height if cam.view_height_end is None else lerp(cam.view_height, cam.view_height_end, ease("in_out", u))
        if cam.mode == "static":
            c = cam.center or (0.0, 150.0)
            return c[0], c[1], vh
        if cam.mode == "dolly":
            a = cam.center or (0.0, 150.0)
            b = cam.center_end or a
            e = ease("in_out", u)
            return lerp(a[0], b[0], e), lerp(a[1], b[1], e), vh
        x0, y0, x1, y1 = self.bbox(cam.target, t)
        vx, vy = self.velocity(cam.target, t)
        cx = (x0 + x1) / 2 + cam.offset[0] + vx * cam.lead
        cy = (y0 + y1) / 2 + cam.offset[1] + vy * cam.lead * 0.5
        if cam.mode == "track_x":
            cy = (cam.center or (0.0, 150.0))[1]
        return cx, cy, vh

    def _bake(self, sh: ShotSpec) -> Tuple[np.ndarray, np.ndarray]:
        cam = sh.camera
        n = max(2, int(math.ceil((sh.end - sh.start) * INTERNAL_HZ)) + 1)
        ts = np.linspace(sh.start, sh.end, n)
        out = np.zeros((n, 3))
        x = np.array(self._target(cam, sh, sh.start), dtype=float)
        v = np.zeros(3)
        w = cam.stiffness
        dt = ts[1] - ts[0]
        for i, t in enumerate(ts):
            tgt = np.array(self._target(cam, sh, float(t)))
            if cam.mode in ("follow", "track_x"):
                a = w * w * (tgt - x) - 2 * w * v  # critically damped follow
                v = v + a * dt
                x = x + v * dt
            else:
                x = tgt
            cx, cy, vh = x
            if cam.keep_in_frame and cam.target:
                cx, cy, vh = self._frame_guard(cam.target, float(t), cx, cy, vh)
            out[i] = (cx, cy, vh)
        return ts, out

    def _frame_guard(self, target: str, t: float, cx: float, cy: float, vh: float) -> Tuple[float, float, float]:
        x0, y0, x1, y1 = self.bbox(target, t)
        hw = vh * self.aspect / 2 * SAFE
        hh = vh / 2 * SAFE
        need_w, need_h = (x1 - x0) / 2, (y1 - y0) / 2
        if need_h > hh or need_w > hw:
            vh *= max(need_h / hh, need_w / hw)
            hw, hh = vh * self.aspect / 2 * SAFE, vh / 2 * SAFE
        cx = clamp(cx, x1 - hw, x0 + hw)
        cy = clamp(cy, y1 - hh, y0 + hh)
        return cx, cy, vh

    def at(self, t: float) -> CameraState:
        sh = self.shot_at(t)
        ts, arr = self._tracks[sh.id]
        cx = float(np.interp(t, ts, arr[:, 0]))
        cy = float(np.interp(t, ts, arr[:, 1]))
        vh = float(np.interp(t, ts, arr[:, 2]))
        return CameraState(cx, cy, vh, sh.camera.roll, sh.id)

    def subject_visible(self, target: str, t: float) -> bool:
        c = self.at(t)
        x0, y0, x1, y1 = self.bbox(target, t)
        hw, hh = c.view_h * self.aspect / 2, c.view_h / 2
        return x0 >= c.cx - hw and x1 <= c.cx + hw and y0 >= c.cy - hh and y1 <= c.cy + hh
