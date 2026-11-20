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
    shx: float = 0.0  # screen-space shake (pixels at 1080p)
    shy: float = 0.0

    def valid(self) -> bool:
        return all(math.isfinite(v) for v in (self.cx, self.cy, self.view_h, self.roll)) and self.view_h > 1


BBoxFn = Callable[[str, float], Tuple[float, float, float, float]]  # (character, t) -> xmin, ymin, xmax, ymax
VelFn = Callable[[str, float], Vec]
GravFn = Callable[[float], Vec]
FocusFn = Callable[[str, float, str], Tuple[float, float, float, float]]  # (character, t, focus) -> bbox of that region


def gravity_roll(g: Vec) -> float:
    """Camera roll (deg, wrapped to (-180, 180]) that makes the gravity vector point straight down the screen."""
    return _wrap180(90.0 + math.degrees(math.atan2(g[1], g[0])))


def _wrap180(a: float) -> float:
    a = (a + 180.0) % 360.0 - 180.0
    return 180.0 if a == -180.0 else a


def _noise(x: float, seed: float) -> float:
    i = math.floor(x)
    f = x - i
    h = lambda n: (math.sin((n + seed * 57.31) * 127.1 + 311.7) * 43758.5453) % 1.0
    u = f * f * (3 - 2 * f)
    return (h(i) * (1 - u) + h(i + 1) * u) * 2 - 1


class CameraDirector:
    def __init__(self, shots: List[ShotSpec], aspect: float, bbox: BBoxFn, velocity: VelFn, gravity: Optional[GravFn] = None,
                 focus_bbox: Optional[FocusFn] = None, shake_events: Optional[List[Tuple[float, float]]] = None,
                 gravity_angle: Optional[Callable[[float], float]] = None):
        self.shots = sorted(shots, key=lambda s: s.start)
        self.aspect = aspect
        self.bbox, self.velocity = bbox, velocity
        self.gravity = gravity or (lambda t: (0.0, -1.0))
        # unwrapped gravity angle (rad): roll follows the physical rotation direction (no shortest-way guessing)
        self.gravity_angle = gravity_angle
        self.focus_bbox = focus_bbox
        self.shake_events = shake_events or []  # (time, strength)
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
        if cam.focus != "body" and self.focus_bbox is not None:
            x0, y0, x1, y1 = self.focus_bbox(cam.target, t, cam.focus)
        else:
            x0, y0, x1, y1 = self.bbox(cam.target, t)
        vx, vy = self.velocity(cam.target, t)
        cx = (x0 + x1) / 2 + cam.offset[0] + vx * cam.lead
        cy = (y0 + y1) / 2 + cam.offset[1] + vy * cam.lead * 0.5
        if cam.mode == "track_x":
            cy = (cam.center or (0.0, 150.0))[1]
        return cx, cy, vh

    def _roll_target(self, cam: CameraSpec, sh: ShotSpec, t: float) -> float:
        if cam.roll_mode == "align_gravity":
            if self.gravity_angle is not None:
                return 90.0 + math.degrees(self.gravity_angle(t))
            return gravity_roll(self.gravity(t))
        if cam.roll_end is not None:
            u = (t - sh.start) / max(1e-6, sh.end - sh.start)
            return lerp(cam.roll, cam.roll_end, ease("in_out", u))
        return cam.roll

    def _bake(self, sh: ShotSpec) -> Tuple[np.ndarray, np.ndarray]:
        cam = sh.camera
        n = max(2, int(math.ceil((sh.end - sh.start) * INTERNAL_HZ)) + 1)
        ts = np.linspace(sh.start, sh.end, n)
        out = np.zeros((n, 4))
        # gravity-aligned shots start from the authored roll and rotate visibly (continuity: the viewer sees the turn)
        roll = cam.roll if cam.roll_mode == "align_gravity" else self._roll_target(cam, sh, sh.start)
        rv = 0.0
        rw = 3.2  # roll follows gravity with a gentle, readable lag (no snap rotations)
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
            rt = self._roll_target(cam, sh, float(t))
            if cam.roll_mode == "align_gravity":
                if self.gravity_angle is None:
                    rt = roll + _wrap180(rt - roll)  # no unwrapped angle available: shortest way round
                ra = rw * rw * (rt - roll) - 2 * rw * rv
                rv += ra * dt
                rv = clamp(rv, -cam.roll_rate, cam.roll_rate)  # large turns (180 deg reversals) stay readable
                roll += rv * dt
            else:
                roll = rt
            if cam.keep_in_frame and cam.target:
                cx, cy, vh = self._frame_guard(cam.target, float(t), cx, cy, vh, roll, cam.focus)
            out[i] = (cx, cy, vh, roll)
        return ts, out

    def _half_extents(self, vh: float, roll: float) -> Tuple[float, float]:
        """Screen-axis half extents of the safe area (independent of roll; the guard works in screen space)."""
        return vh * self.aspect / 2 * SAFE, vh / 2 * SAFE

    def _frame_guard(self, target: str, t: float, cx: float, cy: float, vh: float, roll: float = 0.0,
                     focus: str = "body") -> Tuple[float, float, float]:
        """Keep the framed region (whole body, or the focus region for close-ups) inside the safe area.

        Exact for any roll: the region's corners are projected into rolled screen space; the view is widened until
        the projected extent fits, then the camera centre is shifted (in screen space, mapped back to world) by
        the minimum amount that brings the projected region inside the safe rectangle."""
        if focus != "body" and self.focus_bbox is not None:
            x0, y0, x1, y1 = self.focus_bbox(target, t, focus)
        else:
            x0, y0, x1, y1 = self.bbox(target, t)
        r = math.radians(roll)
        c, s_ = math.cos(r), math.sin(r)
        need_w, need_h = (x1 - x0) / 2, (y1 - y0) / 2
        # projected half-extent of the region in screen axes
        pw = need_w * abs(c) + need_h * abs(s_)
        ph = need_w * abs(s_) + need_h * abs(c)
        A, B = self._half_extents(vh, roll)
        if pw > A or ph > B:
            vh *= max(pw / A, ph / B)
            A, B = self._half_extents(vh, roll)
        sxs, sys_ = [], []
        for (x, y) in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            dx, dy = x - cx, -(y - cy)
            sxs.append(dx * c - dy * s_)
            sys_.append(dx * s_ + dy * c)
        tx = clamp(0.0, max(sxs) - A, min(sxs) + A)
        ty = clamp(0.0, max(sys_) - B, min(sys_) + B)
        cx += tx * c + ty * s_
        cy += tx * s_ - ty * c
        return cx, cy, vh

    def at(self, t: float) -> CameraState:
        sh = self.shot_at(t)
        ts, arr = self._tracks[sh.id]
        cx = float(np.interp(t, ts, arr[:, 0]))
        cy = float(np.interp(t, ts, arr[:, 1]))
        vh = float(np.interp(t, ts, arr[:, 2]))
        roll = float(np.interp(t, ts, arr[:, 3]))
        shx = shy = 0.0
        if sh.camera.shake > 0:
            for te, strength in self.shake_events:
                if te <= t < te + 0.8:
                    env = sh.camera.shake * strength * math.exp(-(t - te) * 7.0)
                    shx += env * _noise((t - te) * 24, te)
                    shy += env * _noise((t - te) * 24, te + 9.1)
        return CameraState(cx, cy, vh, roll, sh.id, shx, shy)

    def subject_visible(self, target: str, t: float, region: Optional[Tuple[float, float, float, float]] = None) -> bool:
        """Whole body (or the given region) inside the frame; accounts for camera roll (screen-aligned test)."""
        c = self.at(t)
        x0, y0, x1, y1 = region if region is not None else self.bbox(target, t)
        r = math.radians(c.roll)
        hw, hh = c.view_h * self.aspect / 2, c.view_h / 2
        for (x, y) in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            dx, dy = x - c.cx, -(y - c.cy)  # screen axes (y down)
            sx = dx * math.cos(r) - dy * math.sin(r)
            sy = dx * math.sin(r) + dy * math.cos(r)
            if abs(sx) > hw or abs(sy) > hh:
                return False
        return True
