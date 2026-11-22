"""Skia (CPU raster) renderer for the 2.5D cutaway room + stick characters.

The renderer only consumes `FrameState`, `CameraState`, specs and rigs; it owns no animation logic, so it can be
replaced (e.g. by a 3D/OpenGL backend) behind the `Renderer` protocol in `render/base.py`.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import skia

from ..camera.director import CameraState
from ..core.mathx import Vec, clamp, lerp, smoothstep
from ..rig.stickman import Pose, StickmanRig
from ..scene.runtime import FrameState
from ..scene.schema import CharacterStyle, EnvironmentSpec
from ..scene.targets import exit_portal, surface_normal, surface_point

FOV_K = 1.1  # camera distance = view_h * FOV_K  (vertical FOV ~ 49deg)
CYAN = (70, 236, 255)
RED = (255, 50, 62)
WHITE = (235, 252, 255)
GREEN = (90, 255, 160)
TANGENT = {"floor": (1.0, 0.0), "ceiling": (1.0, 0.0), "wall_right": (0.0, 1.0), "wall_left": (0.0, 1.0)}


def hex_rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def col(rgb: Sequence[float], a: float = 1.0) -> int:
    return skia.ColorSetARGB(int(clamp(a, 0, 1) * 255), int(rgb[0]), int(rgb[1]), int(rgb[2]))


def mix(a: Sequence[float], b: Sequence[float], u: float) -> Tuple[float, float, float]:
    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u))


class SkiaRenderer:
    def __init__(self, width: int, height: int, env: EnvironmentSpec, styles: Dict[str, CharacterStyle], rigs: Dict[str, StickmanRig],
                 bloom: bool = True):
        self.W, self.H = width, height
        self.env, self.styles, self.rigs = env, styles, rigs
        self.bloom = bloom
        self.depth: Dict[str, float] = {}  # character id -> drawing depth lane (CharacterPlacement.z)
        self.focal = height * FOV_K
        info = skia.ImageInfo.Make(width, height, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
        self.surface = skia.Surface.MakeRaster(info)
        sinfo = skia.ImageInfo.Make(width // 4, height // 4, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
        self.small = skia.Surface.MakeRaster(sinfo)
        r = env.room
        self.hw, self.rh, self.back, self.near = r.width / 2, r.height, r.depth_back, r.depth_front
        self.GLYPH_DEPTH = 90.0
        self.grid = r.grid_spacing
        self.theme = env.theme  # per-environment art direction
        self.accent, self.alert = hex_rgb(self.theme.accent), hex_rgb(self.theme.alert)
        self.bg, self.dust_rgb = hex_rgb(self.theme.background), hex_rgb(self.theme.dust)

    @staticmethod
    def indicator_rotation(g) -> float:
        """Canvas rotation (deg) of the console's gravity arrow (drawn pointing down at 0) for gravity g (world, y-up)."""
        return -math.degrees(math.atan2(g[1], g[0])) - 90.0

    # ------------------------------------------------------------ projection
    def _setup(self, cam: CameraState) -> None:
        self.cam = cam
        self.Fd = cam.view_h * FOV_K

    def P(self, x: float, y: float, z: float = 0.0) -> Tuple[float, float, float]:
        d = max(z + self.Fd, 20.0)
        k = self.focal / d
        return ((x - self.cam.cx) * k, -(y - self.cam.cy) * k, k)

    def poly(self, pts3: Sequence[Tuple[float, float, float]]) -> skia.Path:
        path = skia.Path()
        for i, p in enumerate(pts3):
            sx, sy, _ = self.P(*p)
            (path.lineTo if i else path.moveTo)(sx, sy)
        path.close()
        return path

    def line3(self, c: skia.Canvas, a, b, rgb, alpha: float, width: float, glow: bool = True) -> None:
        pa, pb = self.P(*a), self.P(*b)
        k = (pa[2] + pb[2]) / 2
        if glow:
            c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, Color=col(rgb, 0.08 * alpha), StrokeWidth=max(1.0, width * 4 * k), Style=skia.Paint.kStroke_Style))
        c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.25), 0.85 * alpha), StrokeWidth=max(0.8, width * k), Style=skia.Paint.kStroke_Style))

    # ------------------------------------------------------------ main
    def render(self, fs: FrameState, cam: CameraState, red_flash: float = 0.0, fx: Optional[List[dict]] = None, fade: float = 0.0,
               trails: Optional[Dict[str, List[Tuple[Pose, float]]]] = None, fx_t: Optional[float] = None,
               smears: Optional[Dict[str, Pose]] = None, prop_ghosts: Optional[Dict[str, List[Tuple[float, float, float, float]]]] = None,
               screen: Optional[Dict[str, float]] = None, particles=None, diagrams=None) -> np.ndarray:
        """`fx_t`: the clock effects run on (film time: they keep animating through a hit-stop). `smears`: each character's
        pose a moment earlier (fast limbs leave a smear). `prop_ghosts`: earlier poses of fast props. `screen`: full-screen
        effects (flash, speed lines, vignette pulse)."""
        self._setup(cam)
        self._collapsed = getattr(fs, "collapsed", set()) or set()
        if getattr(fs, "depth", None):
            self.depth = dict(fs.depth)  # depth lanes can change over time (e.g. rolling past in front of someone)
        c = self.surface.getCanvas()
        c.clear(col(self.bg))
        c.save()
        sc = self.H / 1080.0
        c.translate(self.W / 2 + cam.shx * sc, self.H / 2 + cam.shy * sc)
        c.rotate(cam.roll)
        self._room(c, fs, red_flash)
        if self.env.decor:
            self._decor(c, fs, front=False)
        self._exits(c, fs)
        self._shafts(c, fs)
        self._switches(c, fs)
        self._obstacles(c, back=True)
        if self.env.decor:
            self._decor(c, fs, front=True)
        if self.env.portals:
            self._portals(c, fs)
        if self.env.orbs:
            self._orbs(c, fs)
        self._dust(c, fs, front=False)
        vis = {cid: self._exit_fade(pose, fs) for cid, pose in fs.poses.items()}
        for cid, pose in fs.poses.items():
            if vis[cid] > 0.99:
                self._back_shadow(c, cid, pose, fs)
        lying = [self.rigs[cid].world_joints(pose) for cid, pose in fs.poses.items() if pose.state in ("fall", "prone", "crawl", "getup")]
        front = []
        for pr in sorted(fs.props, key=lambda p: -p.z):  # far props first (painter's order)
            if pr.front or self._on_lying(pr, lying):  # a load resting on a lying character is drawn over the body
                front.append(pr)
            else:
                self._prop(c, pr)
        for rp in fs.ropes:
            self._rope(c, rp)
        for cid, pose in fs.poses.items():
            if vis[cid] > 0.99:
                self._reflection(c, cid, pose)
                self._contact_shadow(c, cid, pose)
        for e in fx or []:
            self._effect(c, e, fs.t if fx_t is None else fx_t)
        for pid, ghosts in (prop_ghosts or {}).items():
            pr = next((p for p in fs.props if p.id == pid), None)
            if pr is not None:
                for (gx, gy, ga, alpha) in ghosts:
                    self._prop_ghost(c, pr, gx, gy, ga, alpha)
        # lying bodies in front; otherwise far depth lanes first (painter's order)
        order = sorted(fs.poses.items(), key=lambda kv: (kv[1].state in ("fall", "prone", "crawl", "getup"), -self.depth.get(kv[0], 0.0)))
        for cid, pose in order:
            if vis[cid] <= 0.0:
                continue
            c.save()
            clip = self._interior_clip(fs)
            if clip is not None:
                c.clipPath(clip, doAntiAlias=True)
            if trails and cid in trails and vis[cid] > 0.99:
                self._trail(c, cid, pose, trails[cid])
            if smears and cid in smears and vis[cid] > 0.99:
                self._smear(c, cid, pose, smears[cid])
            self._character(c, cid, pose, alpha=vis[cid], scarf=fs.scarves.get(cid))
            c.restore()
        for pr in sorted(front, key=lambda p: -p.z):
            self._prop(c, pr)
        if particles:
            self._particles(c, particles)
        self._obstacles(c, back=False)
        if diagrams:
            self._diagrams(c, diagrams)
        self._dust(c, fs, front=True)
        self._cutaway(c, red_flash, fs)
        c.restore()
        self._post(c, red_flash)
        if screen:
            self._screen_fx(c, screen)
        if fade > 0.0:  # shot fade to black (end of film)
            c.drawRect(skia.Rect(0, 0, self.W, self.H), skia.Paint(Color=col((0, 0, 0), clamp(fade, 0.0, 1.0))))
        img = self.surface.makeImageSnapshot()
        return img.toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)

    # ------------------------------------------------------------ orbs, portals, particles (Milestone 4)
    ORB_RGB = {"jump": (255, 222, 70), "boost": (255, 100, 225), "pad": (255, 200, 60), "collect": (255, 245, 200)}

    def _orbs(self, c: skia.Canvas, fs: FrameState) -> None:
        taken = getattr(fs, "orbs_taken", {}) or {}
        fired = getattr(fs, "orb_fired", {}) or {}
        t = fs.t
        for o in self.env.orbs:
            rgb = hex_rgb(o.color) if o.color else self.ORB_RGB[o.kind]
            x, y = o.center
            if o.id in taken:
                continue
            pulse = 1.0 + 0.08 * math.sin(t * 6.0 + x * 0.01)
            sx, sy, k = self.P(x, y, 0.0)
            r = o.radius * k * pulse
            if o.kind == "pad":
                pts = [self.P(x + o.radius * math.cos(a), y, 30.0 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 28)]
                path = skia.Path()
                for i, p in enumerate(pts):
                    (path.lineTo if i else path.moveTo)(p[0], p[1])
                path.close()
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, 0.35)))
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.4), 0.9), Style=skia.Paint.kStroke_Style,
                                            StrokeWidth=max(1.0, 2.2 * k)))
                self._glow(c, (sx, sy), r * 1.8, rgb, 0.35)
            elif o.kind == "collect":
                a = t * 2.2 + x * 0.003
                d = [(0.0, -r), (r * 0.62 * abs(math.cos(a)) + 1.0, 0.0), (0.0, r), (-r * 0.62 * abs(math.cos(a)) - 1.0, 0.0)]
                path = skia.Path()
                for i, (px, py) in enumerate(d):
                    (path.lineTo if i else path.moveTo)(sx + px, sy + py)
                path.close()
                self._glow(c, (sx, sy), r * 2.2, rgb, 0.45)
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, 0.95)))
            else:
                self._glow(c, (sx, sy), r * 2.4, rgb, 0.4)
                c.drawCircle(sx, sy, r, skia.Paint(AntiAlias=True, Color=col(rgb, 0.18)))
                c.drawCircle(sx, sy, r, skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.3), 0.95), Style=skia.Paint.kStroke_Style,
                                                   StrokeWidth=max(1.2, 3.0 * k)))
                c.drawCircle(sx, sy, r * 0.42, skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.6), 0.95)))
                if o.kind == "boost":  # chevrons point the way it pushes
                    for dx in (-0.25, 0.2):
                        p = skia.Path()
                        p.moveTo(sx + (dx - 0.15) * r, sy - 0.35 * r)
                        p.lineTo(sx + (dx + 0.1) * r, sy)
                        p.lineTo(sx + (dx - 0.15) * r, sy + 0.35 * r)
                        c.drawPath(p, skia.Paint(AntiAlias=True, Color=col(WHITE, 0.9), Style=skia.Paint.kStroke_Style,
                                                 StrokeWidth=max(1.0, 2.0 * k)))
            if o.id in fired and fired[o.id] < 0.35:  # it just fired: a ring expands from it
                u = fired[o.id] / 0.35
                c.drawCircle(sx, sy, r * (1.0 + 2.2 * u), skia.Paint(AntiAlias=True, Color=col(WHITE, 0.7 * (1 - u)),
                                                                     Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.0, 3.0 * k * (1 - u))))

    def _portals(self, c: skia.Canvas, fs: FrameState) -> None:
        from .particles import portal_rgb
        t = fs.t
        for p in self.env.portals:
            rgb = portal_rgb(self.env, p.id)
            ra = math.radians(p.angle)
            nx, ny = math.cos(ra), math.sin(ra)
            tx, ty = -ny, nx
            h = p.height / 2
            pts = []
            for a in np.linspace(0, 2 * math.pi, 40):
                u, w = math.sin(a), math.cos(a)
                pts.append(self.P(p.center[0] + tx * h * u + nx * 9.0 * w, p.center[1] + ty * h * u + ny * 9.0 * w, 26.0 * w))
            path = skia.Path()
            for i, q in enumerate(pts):
                (path.lineTo if i else path.moveTo)(q[0], q[1])
            path.close()
            sx, sy, k = self.P(p.center[0], p.center[1], 0.0)
            self._glow(c, (sx, sy), h * k * 1.25, rgb, 0.28, squash=1.0)
            c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(mix(rgb, (0, 0, 0), 0.55), 0.85)))
            for j in range(3):  # a slow inner swirl
                f = 0.35 + 0.2 * j
                ph = t * (1.6 + 0.5 * j) + j
                q0 = self.P(p.center[0] + tx * h * f * math.sin(ph), p.center[1] + ty * h * f * math.sin(ph), 0.0)
                self._glow(c, (q0[0], q0[1]), 10.0 * k, mix(rgb, WHITE, 0.4), 0.5)
            c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.25), 0.95), Style=skia.Paint.kStroke_Style,
                                        StrokeWidth=max(1.5, 4.0 * k)))
            # the open side: a short tick along the facing direction
            a0 = self.P(p.center[0] + nx * 10.0, p.center[1] + ny * 10.0)
            a1 = self.P(p.center[0] + nx * 26.0, p.center[1] + ny * 26.0)
            c.drawLine(a0[0], a0[1], a1[0], a1[1], skia.Paint(AntiAlias=True, Color=col(rgb, 0.6), StrokeWidth=max(1.0, 2.0 * k)))

    def _diagrams(self, c: skia.Canvas, prims) -> None:
        """The diagram layer: arrows, paths, labels and dimension lines in world space (crisp, on top of the action)."""
        sc = self.H / 720.0
        font = getattr(self, "_dfont", None)
        if font is None:
            font = self._dfont = skia.Font(skia.Typeface("DejaVu Sans"), 21 * sc)

        def label(x, y, txt, rgb, a):
            w = font.measureText(txt)
            pad = 4 * sc
            c.drawRoundRect(skia.Rect(x - w / 2 - pad, y - 18 * sc, x + w / 2 + pad, y + 6 * sc), 4 * sc, 4 * sc,
                            skia.Paint(AntiAlias=True, Color=col((8, 10, 16), 0.72 * a)))
            c.drawString(txt, x - w / 2, y, font, skia.Paint(AntiAlias=True, Color=col(rgb, a)))

        for p in prims:
            a, rgb = p.alpha, p.rgb
            if a <= 0.01:
                continue
            stroke = skia.Paint(AntiAlias=True, Color=col(rgb, 0.95 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=2.6 * sc,
                                StrokeCap=skia.Paint.kRound_Cap)
            if p.kind == "arrow":
                (x0, y0, _), (x1, y1, _) = self.P(*p.pts[0]), self.P(*p.pts[1])
                L = math.hypot(x1 - x0, y1 - y0)
                c.drawLine(x0, y0, x1, y1, stroke)
                if L > 4:
                    ux, uy = (x1 - x0) / L, (y1 - y0) / L
                    h = min(14 * sc, 0.4 * L)
                    path = skia.Path()
                    path.moveTo(x1, y1)
                    path.lineTo(x1 - ux * h - uy * h * 0.5, y1 - uy * h + ux * h * 0.5)
                    path.lineTo(x1 - ux * h + uy * h * 0.5, y1 - uy * h - ux * h * 0.5)
                    path.close()
                    c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, 0.95 * a)))
                if p.text:
                    label(x1 + (x1 - x0) / max(L, 1) * 18 * sc, y1 + (y1 - y0) / max(L, 1) * 18 * sc - 4 * sc, p.text, rgb, a)
            elif p.kind == "path":
                if len(p.pts) > 1:
                    path = skia.Path()
                    for i, q in enumerate(p.pts):
                        x, y, _ = self.P(*q)
                        (path.lineTo if i else path.moveTo)(x, y)
                    dash = skia.Paint(AntiAlias=True, Color=col(rgb, 0.8 * a), Style=skia.Paint.kStroke_Style, StrokeWidth=2.2 * sc,
                                      PathEffect=skia.DashPathEffect.Make([7 * sc, 6 * sc], 0))
                    c.drawPath(path, dash)
            elif p.kind == "text":
                x, y, _ = self.P(*p.pts[0])
                label(x, y, p.text, rgb, a)
            elif p.kind == "dim":
                (x0, y0, _), (x1, y1, _) = self.P(*p.pts[0]), self.P(*p.pts[1])
                L = math.hypot(x1 - x0, y1 - y0) or 1.0
                nx, ny = -(y1 - y0) / L * 7 * sc, (x1 - x0) / L * 7 * sc
                c.drawLine(x0, y0, x1, y1, stroke)
                for (x, y) in ((x0, y0), (x1, y1)):
                    c.drawLine(x - nx, y - ny, x + nx, y + ny, stroke)
                label((x0 + x1) / 2 + nx * 2.2, (y0 + y1) / 2 + ny * 2.2, p.text, rgb, a)

    def _particles(self, c: skia.Canvas, parts) -> None:
        for (x, y, r, a, rgb) in parts:
            sx, sy, k = self.P(x, y, 0.0)
            rr = max(1.0, 1.25 * r * k)
            self._glow(c, (sx, sy), rr * 4.0, rgb, 0.5 * a)
            c.drawCircle(sx, sy, rr, skia.Paint(AntiAlias=True, Color=col(mix(rgb, WHITE, 0.5), a)))

    # ------------------------------------------------------------ set dressing (Milestone 5)
    def _quad(self, x0, y0, x1, y1, z):
        return self.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)])

    def _decor(self, c: skia.Canvas, fs: FrameState, front: bool) -> None:
        bk = self.back - 2.0
        t = fs.t
        for d in self.env.decor:
            rgb = hex_rgb(d.color) if d.color else self.accent
            z = d.z if d.z is not None else bk
            if (d.kind == "bench") != front:
                continue
            rng = np.random.default_rng([d.seed, int(d.x * 10) & 0xffff])
            x0, y0, x1, y1 = d.x - d.w / 2, d.y, d.x + d.w / 2, d.y + d.h
            if d.kind == "window":
                sky = self._quad(x0, y0, x1, y1, z)
                a, b = self.P(d.x, y1, z), self.P(d.x, y0, z)
                c.drawPath(sky, skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                    [skia.Point(0, a[1]), skia.Point(0, b[1])], [col((10, 12, 40)), col((48, 30, 86))])))
                c.save()
                c.clipPath(sky, doAntiAlias=True)
                bx = x0
                while bx < x1:  # a skyline: buildings with lit windows, deterministic per window
                    bw = float(rng.uniform(0.07, 0.16) * d.w)
                    bh = float(rng.uniform(0.25, 0.8) * d.h)
                    shade = (16, 18, 34) if rng.random() < 0.5 else (22, 20, 44)
                    c.drawPath(self._quad(bx, y0, bx + bw, y0 + bh, z), skia.Paint(AntiAlias=True, Color=col(shade)))
                    for wy in np.arange(y0 + 8, y0 + bh - 6, 9.0):
                        for wx in np.arange(bx + 4, bx + bw - 4, 7.0):
                            if rng.random() < 0.32:
                                p = self.P(wx, wy, z)
                                c.drawRect(skia.Rect(p[0], p[1], p[0] + 2.2 * p[2], p[1] + 2.8 * p[2]),
                                           skia.Paint(Color=col((255, 214, 140), 0.55 + 0.35 * rng.random())))
                    bx += bw + float(rng.uniform(0.0, 0.03) * d.w)
                c.restore()
                for (xa, ya, xb, yb) in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1), (d.x, y0, d.x, y1)):
                    self.line3(c, (xa, ya, z), (xb, yb, z), (90, 100, 130), 0.9, 5.0, glow=False)
            elif d.kind == "panel":
                c.drawPath(self._quad(x0, y0, x1, y1, z), skia.Paint(AntiAlias=True, Color=col(mix(hex_rgb(self.theme.back), WHITE, 0.07))))
                c.drawPath(self._quad(x0, y0, x1, y1, z), skia.Paint(AntiAlias=True, Color=col(mix(rgb, (0, 0, 0), 0.4), 0.8),
                                                                       Style=skia.Paint.kStroke_Style, StrokeWidth=2.0))
                for k in range(max(1, int(d.w // 22))):
                    on = (math.sin(t * (1.3 + 0.37 * k) + k * 2.1 + d.seed) > -0.2)
                    p = self.P(x0 + 12 + k * 22, y1 - 12, z)
                    self._glow(c, (p[0], p[1]), 6 * p[2], (120, 255, 160) if on else (255, 90, 90), 0.6)
            elif d.kind == "screen":
                c.drawPath(self._quad(x0 - 5, y0 - 5, x1 + 5, y1 + 5, z), skia.Paint(AntiAlias=True, Color=col((30, 32, 40))))
                c.drawPath(self._quad(x0, y0, x1, y1, z), skia.Paint(AntiAlias=True, Color=col(mix(rgb, (0, 0, 0), 0.82))))
                pts = [(x0 + 6 + (d.w - 12) * i / 40, y0 + d.h * (0.42 + 0.28 * math.sin(i * 0.45 + t * 2.0 + d.seed)
                                                                    * math.exp(-((i - 20) / 14) ** 2))) for i in range(41)]
                path = skia.Path()
                for i, q in enumerate(pts):
                    s3 = self.P(q[0], q[1], z)
                    (path.lineTo if i else path.moveTo)(s3[0], s3[1])
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=1.8))
                if d.text:
                    p = self.P(x0 + 6, y1 - 6, z)
                    f = skia.Font(skia.Typeface("DejaVu Sans Mono"), max(6.0, 9.0 * p[2]))
                    c.drawString(d.text, p[0], p[1] + 9 * p[2], f, skia.Paint(AntiAlias=True, Color=col(rgb, 0.9)))
                ctr = self.P(d.x, d.y + d.h / 2, z)
                self._glow(c, (ctr[0], ctr[1]), 0.7 * d.w * ctr[2], rgb, 0.12)
            elif d.kind == "pipe":
                xb, yb = (d.x2 if d.x2 is not None else d.x + d.w), (d.y2 if d.y2 is not None else d.y)
                self.line3(c, (d.x, d.y, z), (xb, yb, z), (70, 76, 92), 1.0, 12.0, glow=False)
                self.line3(c, (d.x, d.y + 3, z), (xb, yb + 3, z), (120, 128, 150), 0.6, 3.0, glow=False)
                L = math.hypot(xb - d.x, yb - d.y)
                for k in range(1, int(L // 140) + 1):
                    u = k * 140 / L
                    p = self.P(d.x + (xb - d.x) * u, d.y + (yb - d.y) * u, z)
                    c.drawCircle(p[0], p[1], 9 * p[2], skia.Paint(AntiAlias=True, Color=col((95, 100, 120))))
            elif d.kind == "lamp":
                top = self.rh
                p0, p1 = self.P(d.x, top - 6, 0.0), self.P(d.x, top - 40, 0.0)
                c.drawLine(p0[0], p0[1], p1[0], p1[1], skia.Paint(AntiAlias=True, Color=col((80, 84, 96)), StrokeWidth=3 * p1[2]))
                cone = skia.Path()
                a = self.P(d.x - 22, top - 44, 0.0)
                b = self.P(d.x + 22, top - 44, 0.0)
                fl, fr = self.P(d.x - d.w, 0.0, 0.0), self.P(d.x + d.w, 0.0, 0.0)
                cone.moveTo(a[0], a[1]); cone.lineTo(b[0], b[1]); cone.lineTo(fr[0], fr[1]); cone.lineTo(fl[0], fl[1]); cone.close()
                warm = hex_rgb(d.color) if d.color else (255, 226, 170)
                c.drawPath(cone, skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus, Shader=skia.GradientShader.MakeLinear(
                    [skia.Point(0, a[1]), skia.Point(0, fl[1])], [col(warm, 0.22), col(warm, 0.02)])))
                c.drawPath(self._quad(d.x - 24, top - 46, d.x + 24, top - 38, 0.0), skia.Paint(AntiAlias=True, Color=col((200, 205, 215))))
                fp = self.P(d.x, 0.0, 0.0)
                self._glow(c, (fp[0], fp[1]), d.w * fp[2], warm, 0.18, squash=0.25)
            elif d.kind == "shelf":
                c.drawPath(self._quad(x0, y0, x1, y0 + 6, z), skia.Paint(AntiAlias=True, Color=col((80, 70, 60))))
                n = max(1, int(d.w // 26))
                for k in range(n):
                    jx = x0 + 13 + k * (d.w - 26) / max(1, n - 1) if n > 1 else d.x
                    jh = float(rng.uniform(18, 34))
                    jc = [(120, 255, 200), (255, 150, 220), (140, 200, 255), (255, 220, 120)][int(rng.integers(0, 4))]
                    c.drawPath(self._quad(jx - 7, y0 + 6, jx + 7, y0 + 6 + jh, z), skia.Paint(AntiAlias=True, Color=col(jc, 0.35)))
                    c.drawPath(self._quad(jx - 7, y0 + 6, jx + 7, y0 + 6 + jh * 0.55, z), skia.Paint(AntiAlias=True, Color=col(jc, 0.55)))
            elif d.kind == "bench":
                zf, zb = z - 40, z + 40
                top = self.poly([(x0, y1, zf), (x1, y1, zf), (x1, y1, zb), (x0, y1, zb)])
                c.drawPath(top, skia.Paint(AntiAlias=True, Color=col((70, 74, 86))))
                c.drawPath(self._quad(x0, y1 - 8, x1, y1, zf), skia.Paint(AntiAlias=True, Color=col((46, 48, 58))))
                for lx in (x0 + 10, x1 - 10):
                    c.drawPath(self._quad(lx - 4, y0, lx + 4, y1 - 8, zf), skia.Paint(AntiAlias=True, Color=col((40, 42, 50))))

    # ------------------------------------------------------------ environment
    def _room(self, c: skia.Canvas, fs: FrameState, red: float) -> None:
        hw, rh, bk, nr = self.hw, self.rh, self.back, self.near
        planes = {
            "back": ([(-hw, 0, bk), (hw, 0, bk), (hw, rh, bk), (-hw, rh, bk)], hex_rgb(self.theme.back)),
            "floor": ([(-hw, 0, nr), (hw, 0, nr), (hw, 0, bk), (-hw, 0, bk)], hex_rgb(self.theme.floor)),
            "left": ([(-hw, 0, nr), (-hw, 0, bk), (-hw, rh, bk), (-hw, rh, nr)], hex_rgb(self.theme.side)),
            "right": ([(hw, 0, nr), (hw, 0, bk), (hw, rh, bk), (hw, rh, nr)], hex_rgb(self.theme.side)),
            "ceil": ([(-hw, rh, nr), (hw, rh, nr), (hw, rh, bk), (-hw, rh, bk)], hex_rgb(self.theme.ceiling)),
        }
        for name, (pts, rgb) in planes.items():
            c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(mix(rgb, (60, 10, 14), red * 0.5))))
        gcol = mix(self.accent, self.alert, clamp(red * 1.3, 0, 1))
        ga = self.env.room.grid_alpha
        if ga < 1.0:  # a quieter grid under set dressing
            gcol = mix(hex_rgb(self.theme.back), gcol, ga)
        g = self.grid
        xs = np.arange(-hw, hw + 1, g)
        ys = np.arange(0, rh + 1, g)
        zs = np.arange(bk, nr, -g)
        for x in xs:
            maj = abs(x) % (4 * g) < 1
            self.line3(c, (x, 0, bk), (x, rh, bk), gcol, 1.0 if maj else 0.6, 1.6)
            self.line3(c, (x, 0, nr), (x, 0, bk), gcol, 1.0 if maj else 0.6, 1.6)
        for y in ys:
            self.line3(c, (-hw, y, bk), (hw, y, bk), gcol, 0.7, 1.6)
            self.line3(c, (-hw, y, nr), (-hw, y, bk), gcol, 0.6, 1.6)
            self.line3(c, (hw, y, nr), (hw, y, bk), gcol, 0.6, 1.6)
        for z in zs:
            self.line3(c, (-hw, 0, z), (hw, 0, z), gcol, 0.6, 1.6)
            self.line3(c, (-hw, 0, z), (-hw, rh, z), gcol, 0.5, 1.6)
            self.line3(c, (hw, 0, z), (hw, rh, z), gcol, 0.5, 1.6)
        # haze toward the ceiling
        top = self.P(0, rh, 300)[1]
        mid = self.P(0, rh - 500, 300)[1]
        shader = skia.GradientShader.MakeLinear([skia.Point(0, top), skia.Point(0, mid)], [col(self.bg, 0.85), col(self.bg, 0.0)])
        c.drawRect(skia.Rect(-4000, -4000, 4000, 4000), skia.Paint(Shader=shader))
        if self.env.room.entry_door:
            door = self.poly([(-hw, 0, -75), (-hw, 0, 75), (-hw, 230, 75), (-hw, 230, -75)])
            a, b = self.P(-hw, 230, 0), self.P(-hw, 0, 0)
            sh = skia.GradientShader.MakeLinear([skia.Point(0, a[1]), skia.Point(0, b[1])], [col((40, 120, 140), 0.9), col((210, 250, 255), 1.0)])
            c.drawPath(door, skia.Paint(AntiAlias=True, Shader=sh))
            c.drawPath(door, skia.Paint(AntiAlias=True, Color=col((160, 250, 255), 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=2.5))

    def _glow(self, c: skia.Canvas, center: Tuple[float, float], radius: float, rgb, alpha: float, squash: float = 1.0) -> None:
        if radius <= 1:
            return
        c.save()
        c.translate(center[0], center[1])
        c.scale(1.0, squash)
        sh = skia.GradientShader.MakeRadial(skia.Point(0, 0), radius, [col(rgb, alpha), col(rgb, 0.0)])
        c.drawCircle(0, 0, radius, skia.Paint(AntiAlias=True, Shader=sh, BlendMode=skia.BlendMode.kPlus))
        c.restore()

    def _SP(self, surface: str, s_: float, h: float, z: float) -> Tuple[float, float, float]:
        x, y = surface_point(self.env, surface, s_, h)
        return (x, y, z)

    def _switches(self, c: skia.Canvas, fs: FrameState) -> None:
        cam = (self.cam.cx, self.cam.cy)
        for sw in self.env.switches:
            surf = sw.surface
            SP = lambda s_, h, z: self._SP(surf, s_, h, z)
            tv, nv = TANGENT[surf], surface_normal(surf)
            glow = fs.switch_glow.get(sw.id, 0.6)
            x, z0, z1, top = sw.x, 20.0, 76.0, sw.height - 6
            fl = self.P(*SP(x, 0, 48))
            if surf in ("floor", "ceiling"):
                self._glow(c, (fl[0], fl[1]), (220 + 120 * min(glow, 2.5)) * fl[2], self.alert, 0.16 * min(glow, 2.5), squash=0.25)
            else:
                c.save()
                c.translate(fl[0], fl[1])
                c.scale(0.25, 1.0)
                self._glow(c, (0, 0), (220 + 120 * min(glow, 2.5)) * fl[2], self.alert, 0.16 * min(glow, 2.5))
                c.restore()
            body = (34, 38, 46)
            faces = []
            for sgn in (1, -1):  # side faces, visible when the camera is on their side
                cx_, cy_, _ = SP(x + 30 * sgn, top / 2, z0)
                if (cam[0] - cx_) * tv[0] * sgn + (cam[1] - cy_) * tv[1] * sgn > 0:
                    faces.append([SP(x + 30 * sgn, 0, z0), SP(x + 30 * sgn, 0, z1), SP(x + 30 * sgn, top, z1), SP(x + 30 * sgn, top, z0)])
            tx_, ty_, _ = SP(x, top, z0)
            if (cam[0] - tx_) * nv[0] + (cam[1] - ty_) * nv[1] > 0:
                faces.append([SP(x - 30, top, z0), SP(x + 30, top, z0), SP(x + 30, top, z1), SP(x - 30, top, z1)])
            for f in faces:
                c.drawPath(self.poly(f), skia.Paint(AntiAlias=True, Color=col(mix(body, (0, 0, 0), 0.3))))
            front = self.poly([SP(x - 30, 0, z0), SP(x + 30, 0, z0), SP(x + 30, top, z0), SP(x - 30, top, z0)])
            c.drawPath(front, skia.Paint(AntiAlias=True, Color=col(body)))
            c.drawPath(front, skia.Paint(AntiAlias=True, Color=col((255, 80, 90), 0.5 * min(1, glow)), Style=skia.Paint.kStroke_Style, StrokeWidth=1.5))
            strip = self.poly([SP(x - 30, 2, z0 - 0.5), SP(x + 30, 2, z0 - 0.5), SP(x + 30, 6, z0 - 0.5), SP(x - 30, 6, z0 - 0.5)])
            c.drawPath(strip, skia.Paint(AntiAlias=True, Color=col(self.alert, 0.9 * min(1.2, glow))))
            # display: arrow showing the current gravity direction (absolute, world frame)
            sc = self.P(*SP(x, top * 0.55, z0 - 0.5))
            k = sc[2]
            c.save()
            c.translate(sc[0], sc[1])
            c.scale(k, k)
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(Color=col((8, 14, 18))))
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(AntiAlias=True, Color=col(self.accent, 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
            c.rotate(self.indicator_rotation(fs.gravity))
            p = skia.Paint(AntiAlias=True, Color=col(self.accent), Style=skia.Paint.kStroke_Style, StrokeWidth=2.6, StrokeCap=skia.Paint.kRound_Cap)
            path = skia.Path()
            path.moveTo(0, -9); path.lineTo(0, 9); path.moveTo(-6, 3); path.lineTo(0, 9); path.lineTo(6, 3)
            c.drawPath(path, p)
            c.restore()
            # button dome, oriented along the console's surface normal
            pressed = clamp((glow - 0.7) / 2.0, 0, 1) * 4.0
            b = self.P(*SP(x, sw.height - 6 - pressed * 0.6, 34))
            b2 = self.P(*SP(x, sw.height + 4, 34))
            kb = b[2]
            ang = math.degrees(math.atan2(b2[1] - b[1], b2[0] - b[0])) + 90.0  # dome drawn pointing to -y (up) at 0
            c.save()
            c.translate(b[0], b[1])
            c.rotate(ang)
            c.drawOval(skia.Rect(-14 * kb, -5.5 * kb, 14 * kb, 3.5 * kb), skia.Paint(AntiAlias=True, Color=col((40, 10, 12))))
            dome = skia.Path()
            dome.addArc(skia.Rect(-11 * kb, -10 * kb, 11 * kb, 6 * kb), 180, 180)
            dome.close()
            sh = skia.GradientShader.MakeRadial(skia.Point(0, -5 * kb), 14 * kb, [col((255, 220, 220), min(1, 0.6 + glow * 0.4)), col(self.alert), col((140, 10, 20))], [0.0, 0.45, 1.0])
            c.drawPath(dome, skia.Paint(AntiAlias=True, Shader=sh))
            c.restore()
            h = self.P(*SP(x, sw.height, 34))
            self._glow(c, (h[0], h[1]), (40 + 45 * min(glow, 2.5)) * h[2], (255, 70, 80), 0.42 * min(1.0, glow))

    def _obstacles(self, c: skia.Canvas, back: bool) -> None:
        """Beams / rails spanning the room depth. Long faces are drawn behind the characters (back=True); the front
        cap and near edge are drawn in front (back=False) only for the part nearer than the character plane."""
        nr, bk = self.near + 2, self.back
        cam = (self.cam.cx, self.cam.cy)
        for ob in self.env.obstacles:
            if ob.id in getattr(self, "_collapsed", ()):
                continue  # it gave way: its falling planks are drawn as props
            cx_, cy_ = ob.center
            if ob.kind == "bar":
                self._rail(c, ob, back)
                continue
            if ob.kind == "glyph":
                self._glyph_structure(c, ob, back)
                continue
            hx, hy = ob.size[0] / 2, ob.size[1] / 2
            x0, x1, y0, y1 = cx_ - hx, cx_ + hx, cy_ - hy, cy_ + hy
            za, zb = (0.0, bk) if back else (nr, 0.0)
            faces = []
            if cam[0] > x1:
                faces.append(([(x1, y0, za), (x1, y1, za), (x1, y1, zb), (x1, y0, zb)], 0.75))
            if cam[0] < x0:
                faces.append(([(x0, y0, za), (x0, y1, za), (x0, y1, zb), (x0, y0, zb)], 0.75))
            if cam[1] > y1:
                faces.append(([(x0, y1, za), (x1, y1, za), (x1, y1, zb), (x0, y1, zb)], 0.95))
            if cam[1] < y0:
                faces.append(([(x0, y0, za), (x1, y0, za), (x1, y0, zb), (x0, y0, zb)], 0.55))
            base = (44, 50, 58) if ob.kind == "beam" else mix((30, 34, 42), self.accent, 0.12)
            for pts, shade in faces:
                c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(mix((0, 0, 0), base, shade))))
                c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(self.accent, 0.35), Style=skia.Paint.kStroke_Style, StrokeWidth=1.0))
            if not back and ob.kind == "platform":  # front face of a slab: dark, with a glowing top edge
                cap = self.poly([(x0, y0, nr), (x1, y0, nr), (x1, y1, nr), (x0, y1, nr)])
                c.drawPath(cap, skia.Paint(AntiAlias=True, Color=col(mix((22, 25, 32), self.accent, 0.1))))
                a3, b3 = self.P(x0, y1, nr), self.P(x1, y1, nr)
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col(self.accent, 0.9), StrokeWidth=max(1.5, 3.0 * a3[2]),
                                                                  MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 2.0)))
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col((255, 255, 255), 0.7), StrokeWidth=max(1.0, 1.2 * a3[2])))
                c.drawPath(cap, skia.Paint(AntiAlias=True, Color=col(self.accent, 0.35), Style=skia.Paint.kStroke_Style, StrokeWidth=1.0))
            elif not back:  # front cap with hazard stripes
                cap = self.poly([(x0, y0, nr), (x1, y0, nr), (x1, y1, nr), (x0, y1, nr)])
                c.drawPath(cap, skia.Paint(AntiAlias=True, Color=col((52, 58, 66))))
                c.save()
                c.clipPath(cap, doAntiAlias=True)
                n = 7
                for i in range(-n, n):
                    yy = y0 + (i + 0.5) * (y1 - y0) / n * 1.0
                    stripe = self.poly([(x0, yy, nr - 0.3), (x1, yy + 18, nr - 0.3), (x1, yy + 30, nr - 0.3), (x0, yy + 12, nr - 0.3)])
                    if i % 2 == 0:
                        c.drawPath(stripe, skia.Paint(AntiAlias=True, Color=col((255, 196, 40), 0.85)))
                c.restore()
                c.drawPath(cap, skia.Paint(AntiAlias=True, Color=col(self.accent, 0.6), Style=skia.Paint.kStroke_Style, StrokeWidth=1.4))

    # ------------------------------------------------------------ symbols (glyph structures and props)
    GLYPH_DEPTH = 90.0

    def _glyph_strokes_path(self, strokes, z: float) -> Tuple[skia.Path, float]:
        path = skia.Path()
        k = 1.0
        for st in strokes:
            for i, (x, y) in enumerate(st):
                px, py, k = self.P(x, y, z)
                if i == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            if len(st) == 2 and math.dist(st[0], st[1]) < 1.0:  # a dot
                px, py, k = self.P(st[0][0], st[0][1], z)
                path.lineTo(px + 0.01, py)
        return path, k

    def _draw_glyph(self, c: skia.Canvas, strokes, weight: float, rgb, z_front: float, z_back: float, layers: int = 6,
                    part: str = "all", alpha: float = 1.0) -> None:
        """An extruded glyph: dark layers from the back plane to the front, then a glowing front face."""
        dark = mix((8, 9, 12), rgb, 0.22)
        side = mix((12, 14, 18), rgb, 0.45)
        rng = range(layers + 1)
        for i in rng:
            u = i / layers
            z = z_back + (z_front - z_back) * u
            front = i == layers
            if (part == "back" and z < 0.0) or (part == "front" and z >= 0.0):
                continue  # behind the character plane in the back pass, nearer than it in the front pass
            path, k = self._glyph_strokes_path(strokes, z)
            w = max(1.5, weight * k)
            if front:
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, 0.55 * alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=w * 1.25,
                                            StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join,
                                            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(2.0, 0.35 * w))))
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(mix(rgb, (255, 255, 255), 0.15), alpha), Style=skia.Paint.kStroke_Style,
                                            StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col((255, 255, 255), 0.55 * alpha), Style=skia.Paint.kStroke_Style,
                                            StrokeWidth=max(1.0, w * 0.22), StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))
            else:
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(mix(dark, side, u), alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                                            StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))

    def _glyph_structure(self, c: skia.Canvas, ob, back: bool) -> None:
        from ..scene import glyphs
        from ..scene.structures import glyph_weight
        cx, cy = ob.center
        strokes = [[(cx + x, cy + y) for x, y in st] for st in glyphs.strokes(ob.glyph, ob.size)]
        rgb = hex_rgb(ob.color) if ob.color else self.accent
        D = self.GLYPH_DEPTH
        self._draw_glyph(c, strokes, glyph_weight(ob), rgb, -D / 2, D / 2, layers=8, part="back" if back else "front")

    def _glyph_prop(self, c: skia.Canvas, pr) -> None:
        from ..scene import glyphs
        sp = next(p for p in self.env.props if p.id == pr.id)
        ca, sa = math.cos(pr.angle), math.sin(pr.angle)
        if getattr(pr, "morph", None):  # changing shape: a blend of the two glyphs
            local = glyphs.blend(pr.morph[0], pr.morph[1], pr.morph[2], sp.size, shift=pr.morph[3] if len(pr.morph) > 3 else (0.0, 0.0))
        else:
            local = glyphs.strokes(getattr(pr, "glyph", None) or sp.glyph, sp.size)
        strokes = [[(pr.pos[0] + x * ca - y * sa, pr.pos[1] + x * sa + y * ca) for x, y in st] for st in local]
        rgb = hex_rgb(sp.color) if sp.color else self.accent
        self._draw_glyph(c, strokes, sp.weight or glyphs.default_weight(sp.size), rgb, pr.z - pr.depth / 2, pr.z + pr.depth / 2, layers=4)

    def _rail(self, c: skia.Canvas, ob, back: bool) -> None:
        """Grab rail spanning the room depth: a steel tube with yellow grip bands, bolted to the back wall by a
        bracket, with an end cap at the front. Drawn behind the character for z >= 0 and in front for z < 0."""
        nr, bk = self.near + 2, self.back
        x, y = ob.center
        r = max(ob.size[0] / 2, 6.0) * 1.15
        z0, z1 = (0.0, bk) if back else (nr, 0.0)
        a, b = self.P(x, y, z0), self.P(x, y, z1)
        k = (a[2] + b[2]) / 2
        c.drawLine(a[0], a[1], b[0], b[1], skia.Paint(AntiAlias=True, Color=col((255, 214, 90), 0.18), StrokeWidth=max(3.0, 7 * r * k),
                                                     StrokeCap=skia.Paint.kRound_Cap, MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 4 * k)))
        c.drawLine(a[0], a[1], b[0], b[1], skia.Paint(AntiAlias=True, Color=col((120, 132, 142)), StrokeWidth=max(2.0, 2 * r * k),
                                                     StrokeCap=skia.Paint.kRound_Cap))
        n = 12  # grip bands along the tube
        zs = np.linspace(z0, z1, n + 1)
        for i in range(n):
            if i % 2 == 0:
                p0, p1 = self.P(x, y, zs[i]), self.P(x, y, zs[i + 1])
                c.drawLine(p0[0], p0[1], p1[0], p1[1], skia.Paint(AntiAlias=True, Color=col((255, 196, 40)), StrokeWidth=max(1.6, 1.7 * r * (p0[2] + p1[2]) / 2)))
        c.drawLine(a[0], a[1], b[0], b[1], skia.Paint(AntiAlias=True, Color=col((235, 245, 255), 0.7), StrokeWidth=max(0.6, 0.35 * r * k)))
        if back:  # bracket on the back wall
            q = self.P(x, y, bk - 0.5)
            s_ = 26 * q[2]
            c.drawRect(skia.Rect(q[0] - s_, q[1] - s_, q[0] + s_, q[1] + s_), skia.Paint(AntiAlias=True, Color=col((70, 80, 92))))
            c.drawRect(skia.Rect(q[0] - s_, q[1] - s_, q[0] + s_, q[1] + s_), skia.Paint(AntiAlias=True, Color=col(self.accent, 0.6), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
            for dx, dy in ((-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6), (0.6, 0.6)):
                c.drawCircle(q[0] + dx * s_, q[1] + dy * s_, max(1.0, 2.5 * q[2]), skia.Paint(AntiAlias=True, Color=col((200, 210, 220))))
        else:  # end cap at the front
            q = self.P(x, y, nr)
            c.drawCircle(q[0], q[1], max(2.0, 1.6 * r * q[2]), skia.Paint(AntiAlias=True, Color=col((255, 196, 40))))
            c.drawCircle(q[0], q[1], max(2.0, 1.6 * r * q[2]), skia.Paint(AntiAlias=True, Color=col((40, 30, 10)), Style=skia.Paint.kStroke_Style, StrokeWidth=1.5))

    @staticmethod
    def _on_lying(pr, lying) -> bool:
        if not lying or pr.kind not in ("post", "container", "crate"):
            return False
        ca, sa = math.cos(pr.angle), math.sin(pr.angle)
        hx, hy = pr.size[0] / 2, pr.size[1] / 2
        xs = [pr.pos[0] + x * ca - y * sa for x in (-hx, hx) for y in (-hy, hy)]
        ys = [pr.pos[1] + x * sa + y * ca for x in (-hx, hx) for y in (-hy, hy)]
        for j in lying:
            jx = [p[0] for p in j.values()]
            jy = [p[1] for p in j.values()]
            if min(xs) < max(jx) and max(xs) > min(jx) and min(ys) < max(jy) + 6 and max(ys) > min(jy):
                return True
        return False

    def _box3d(self, c: skia.Canvas, pr, face: Tuple[int, int, int], side: Tuple[int, int, int], edge, alpha: float = 1.0) -> List[Tuple[float, float]]:
        """An extruded, rotated box: back face, side faces, front face. Returns the front face's screen corners."""
        ca, sa = math.cos(pr.angle), math.sin(pr.angle)
        hx, hy = pr.size[0] / 2, pr.size[1] / 2
        corners = [(pr.pos[0] + x * ca - y * sa, pr.pos[1] + x * sa + y * ca) for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
        zf, zb = pr.z - pr.depth / 2, pr.z + pr.depth / 2
        back = [(x, y, zb) for x, y in corners]
        fr = [(x, y, zf) for x, y in corners]
        c.drawPath(self.poly(back), skia.Paint(AntiAlias=True, Color=col(mix(side, (0, 0, 0), 0.45), alpha)))
        for i in range(4):
            j = (i + 1) % 4
            c.drawPath(self.poly([fr[i], fr[j], back[j], back[i]]), skia.Paint(AntiAlias=True, Color=col(mix(side, face, 0.15 * (i % 2)), alpha)))
        c.drawPath(self.poly(fr), skia.Paint(AntiAlias=True, Color=col(face, alpha)))
        c.drawPath(self.poly(fr), skia.Paint(AntiAlias=True, Color=col(edge, 0.7 * alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=1.3))
        return [self.P(*p)[:2] for p in fr]

    def _local3(self, pr, lx: float, ly: float, z: Optional[float] = None) -> Tuple[float, float]:
        ca, sa = math.cos(pr.angle), math.sin(pr.angle)
        x, y = pr.pos[0] + lx * ca - ly * sa, pr.pos[1] + lx * sa + ly * ca
        return self.P(x, y, pr.z - pr.depth / 2 if z is None else z)[:2]

    def _prop_line(self, c: skia.Canvas, pr, a: Vec, b: Vec, rgb, w: float, alpha: float = 1.0) -> None:
        p0, p1 = self._local3(pr, *a), self._local3(pr, *b)
        k = self.P(pr.pos[0], pr.pos[1], pr.z - pr.depth / 2)[2]
        c.drawLine(p0[0], p0[1], p1[0], p1[1], skia.Paint(AntiAlias=True, Color=col(rgb, alpha), StrokeWidth=max(1.0, w * k),
                                                         StrokeCap=skia.Paint.kRound_Cap))

    def _prop(self, c: skia.Canvas, pr) -> None:
        kind = pr.kind
        if kind == "glyph":
            self._glyph_prop(c, pr)
            return
        hx, hy = pr.size[0] / 2, pr.size[1] / 2
        if kind == "container":  # ribbed steel container with corner posts and a pull handle
            self._box3d(c, pr, (78, 92, 104), (52, 60, 70), self.accent)
            for i in range(1, 6):
                x = -hx + i * pr.size[0] / 6
                self._prop_line(c, pr, (x, -hy + 6), (x, hy - 6), (110, 126, 138), 2.2)
            for sx in (-1, 1):
                self._prop_line(c, pr, (sx * (hx - 4), -hy), (sx * (hx - 4), hy), (40, 46, 52), 5.0)
            self._prop_line(c, pr, (-hx + 8, hy - 6), (hx - 8, hy - 6), (40, 46, 52), 4.0)
            self._prop_line(c, pr, (-hx - 3, 4), (-hx - 3, 26), (255, 196, 40), 3.0)
            return
        if kind == "post":  # steel support column (I-beam), heavy cap plate at the top, hazard bands at the base
            self._box3d(c, pr, (96, 104, 112), (58, 64, 70), self.accent)
            self._prop_line(c, pr, (0, -hy + 4), (0, hy - 4), (60, 66, 72), 3.0)
            self._prop_line(c, pr, (-hx - 4, hy - 4), (hx + 4, hy - 4), (150, 160, 168), 7.0)  # cap plate
            for i in range(4):
                y0 = -hy + 6 + i * 14
                self._prop_line(c, pr, (-hx + 1, y0), (hx - 1, y0 + 7), (255, 190, 30) if i % 2 == 0 else (25, 25, 25), 5.0)
            return
        if kind == "bar":  # pry bar: dark steel, chisel tip (-x end), yellow grip (+x end)
            self._prop_line(c, pr, (-hx, 0), (hx, 0), (70, 76, 84), max(5.0, pr.size[1] * 1.1))
            self._prop_line(c, pr, (-hx, 0), (hx, 0), (150, 158, 166), max(1.5, pr.size[1] * 0.3))
            self._prop_line(c, pr, (hx - 34, 0), (hx, 0), (255, 196, 40), max(6.0, pr.size[1] * 1.3))
            self._prop_line(c, pr, (-hx, -2), (-hx + 10, 2), (190, 200, 210), 3.0)
            return
        if kind == "toolbox":  # red steel toolbox with a lid seam and a handle
            self._box3d(c, pr, (176, 44, 40), (112, 28, 26), (255, 150, 120))
            self._prop_line(c, pr, (-hx + 2, hy * 0.35), (hx - 2, hy * 0.35), (90, 20, 18), 2.0)
            self._prop_line(c, pr, (-hx * 0.4, hy + 5), (hx * 0.4, hy + 5), (60, 62, 66), 3.0)
            self._prop_line(c, pr, (-hx * 0.4, hy), (-hx * 0.4, hy + 5), (60, 62, 66), 2.5)
            self._prop_line(c, pr, (hx * 0.4, hy), (hx * 0.4, hy + 5), (60, 62, 66), 2.5)
            return
        self._prop_flat(c, pr)

    def _rope(self, c: skia.Canvas, rp) -> None:
        """Ratchet strap: sags when slack, straight when taut; after it snaps, two ends hang down."""
        rgb = hex_rgb(rp.color)
        k = self.P(rp.a[0], rp.a[1], 0)[2]
        paint = skia.Paint(AntiAlias=True, Color=col(rgb, 0.95), StrokeWidth=max(1.5, 3.2 * k), Style=skia.Paint.kStroke_Style,
                           StrokeCap=skia.Paint.kRound_Cap)
        if rp.snapped:
            for end, other in ((rp.a, rp.b), (rp.b, rp.a)):
                L = 0.32 * rp.length
                dx = other[0] - end[0]
                tip = (end[0] + math.copysign(0.25 * L, dx), max(2.0, end[1] - 0.9 * L))
                ctrl = (end[0] + math.copysign(0.3 * L, dx), end[1] - 0.2 * L)
                path = skia.Path()
                p0, p1, p2 = self.P(*end, 0), self.P(*ctrl, 0), self.P(*tip, 0)
                path.moveTo(p0[0], p0[1])
                path.quadTo(p1[0], p1[1], p2[0], p2[1])
                c.drawPath(path, paint)
            return
        d = math.dist(rp.a, rp.b)
        sag = 0.5 * math.sqrt(max(0.0, rp.length ** 2 - d ** 2))
        mid = ((rp.a[0] + rp.b[0]) / 2, (rp.a[1] + rp.b[1]) / 2 - sag)
        mid = (mid[0], max(1.0, mid[1]))
        path = skia.Path()
        p0, p1, p2 = self.P(*rp.a, 0), self.P(*mid, 0), self.P(*rp.b, 0)
        path.moveTo(p0[0], p0[1])
        path.quadTo(2 * p1[0] - (p0[0] + p2[0]) / 2, 2 * p1[1] - (p0[1] + p2[1]) / 2, p2[0], p2[1])
        c.drawPath(path, paint)

    def _prop_flat(self, c: skia.Canvas, pr) -> None:
        sx, sy, k = self.P(pr.pos[0], pr.pos[1], 0)
        w, h = pr.size[0] * k, pr.size[1] * k
        c.save()
        c.translate(sx, sy)
        c.rotate(-math.degrees(pr.angle))
        sh = skia.GradientShader.MakeLinear([skia.Point(-w / 2, 0), skia.Point(w / 2, 0)], [col((60, 70, 78)), col((140, 155, 165)), col((50, 58, 66))], [0, 0.45, 1])
        r = skia.Rect(-w / 2, -h / 2, w / 2, h / 2)
        c.drawRect(r, skia.Paint(AntiAlias=True, Shader=sh))
        c.drawRect(r, skia.Paint(AntiAlias=True, Color=col(self.accent, 0.55), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
        c.drawRect(skia.Rect(-w / 2, -2 * k, w / 2, 2 * k), skia.Paint(Color=col((255, 205, 60), 0.85)))
        c.restore()

    def _cutaway(self, c: skia.Canvas, red: float, fs: Optional[FrameState] = None) -> None:
        hw, rh, z = self.hw, self.rh, self.near - 0.5
        th, M = 46.0, 1600.0
        oc = mix((13, 15, 19), (40, 8, 11), red * 0.5)
        holes = []
        if fs is not None:
            for ex in self._open_exits(fs):
                x0, y0, x1, y1 = exit_portal(self.env, ex.id)
                holes.append(self.poly([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]))
        for f in ([(-hw - M, 0, z), (hw + M, 0, z), (hw + M, -M, z), (-hw - M, -M, z)],
                  [(hw, -M, z), (hw + M, -M, z), (hw + M, rh + M, z), (hw, rh + M, z)],
                  [(-hw - M, -M, z), (-hw, -M, z), (-hw, rh + M, z), (-hw - M, rh + M, z)],
                  [(-hw - M, rh, z), (hw + M, rh, z), (hw + M, rh + M, z), (-hw - M, rh + M, z)]):
            path = self.poly(f)
            for hole in holes:  # an open doorway shows the lit corridor beyond the room
                path = skia.Op(path, hole, skia.PathOp.kDifference_PathOp) or path
            c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(oc)))
        slab = mix((30, 35, 42), (70, 14, 18), red * 0.5)
        for f in ([(-hw - th, 0, z), (hw + th, 0, z), (hw + th, -th, z), (-hw - th, -th, z)],
                  [(hw, 0, z), (hw + th, 0, z), (hw + th, rh, z), (hw, rh, z)],
                  [(-hw - th, 0, z), (-hw, 0, z), (-hw, rh, z), (-hw - th, rh, z)]):
            c.drawPath(self.poly(f), skia.Paint(AntiAlias=True, Color=col(slab)))
        e = mix(self.accent, self.alert, clamp(red * 1.3, 0, 1))
        for a, b in (((-hw, 0, z), (hw, 0, z)), ((hw, 0, z), (hw, rh, z)), ((-hw, 0, z), (-hw, rh, z))):
            self.line3(c, a, b, e, 1.0, 3.0)

    # ------------------------------------------------------------ characters
    def _zfn(self) -> float:
        return self.focal / self.Fd

    def _char_paths(self, cid: str, pose: Pose):
        rig, st = self.rigs[cid], self.styles[cid]
        j = rig.world_joints(pose)
        dz = self.depth.get(cid, 0.0)  # depth lane: nearer characters draw slightly larger
        k = self.focal / max(self.Fd + dz, 20.0) if dz else self._zfn()
        S = lambda p: ((p[0] - self.cam.cx) * k, -(p[1] - self.cam.cy) * k)
        return rig, st, j, k, S

    def _character(self, c: skia.Canvas, cid: str, pose: Pose, alpha: float = 1.0, mirror_y: Optional[float] = None, scarf=None,
                   tint: Optional[Tuple[int, int, int]] = None) -> None:
        rig, st, j, k, S0 = self._char_paths(cid, pose)
        if mirror_y is not None:
            S = lambda p: S0((p[0], 2 * mirror_y - p[1]))
        else:
            S = S0
        near, far, vis = hex_rgb(st.body_color), hex_rgb(st.far_color), hex_rgb(st.visor_color)
        if tint is not None:
            near = far = vis = tint
        else:  # aerial perspective: a farther lane is a little darker, a nearer one a little brighter (depth reads at a glance)
            dzc = clamp(self.depth.get(cid, 0.0) / 60.0, -1.0, 1.0)
            if dzc > 0:
                near, far = mix(near, self.bg, 0.28 * dzc), mix(far, self.bg, 0.28 * dzc)
            elif dzc < 0:
                near, far = mix(near, (255, 255, 255), 0.14 * -dzc), mix(far, (255, 255, 255), 0.1 * -dzc)
        lw = st.limb_width * k

        def stroke(pts, rgb, w):
            path = skia.Path()
            for i, p in enumerate(pts):
                q = S(p)
                (path.lineTo if i else path.moveTo)(q[0], q[1])
            paint = skia.Paint(AntiAlias=True, Color=col(rgb, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                               StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
            c.drawPath(path, paint)

        def dot(p, r, rgb):
            q = S(p)
            c.drawCircle(q[0], q[1], r, skia.Paint(AntiAlias=True, Color=col(rgb, alpha)))

        if mirror_y is None:
            glow = skia.Paint(AntiAlias=True, Color=col(hex_rgb(st.glow_color), 0.35), Style=skia.Paint.kStroke_Style, StrokeWidth=lw * 3.2,
                              StrokeCap=skia.Paint.kRound_Cap, MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(1.0, 4 * k)))
            path = skia.Path()
            for chain in (["pelvis", "neck_base", "head_center"], ["pelvis", "knee_n", "ankle_n"], ["pelvis", "knee_f", "ankle_f"],
                          ["shoulder_n", "elbow_n", "wrist_n"], ["shoulder_f", "elbow_f", "wrist_f"]):
                for i, n in enumerate(chain):
                    q = S(j[n])
                    (path.lineTo if i else path.moveTo)(q[0], q[1])
            c.drawPath(path, glow)
            # dark under-stroke: invisible against the dark rooms, it keeps the silhouette readable against bright
            # light (an open doorway, a flash) where a light character would otherwise dissolve
            ol = skia.Path()
            for chain in (["pelvis", "spine_mid", "neck_base", "neck_top"], ["hip_n", "knee_n", "ankle_n", "toe_n"],
                          ["hip_f", "knee_f", "ankle_f", "toe_f"], ["shoulder_n", "elbow_n", "wrist_n"], ["shoulder_f", "elbow_f", "wrist_f"]):
                for i, n in enumerate(chain):
                    q = S(j[n])
                    (ol.lineTo if i else ol.moveTo)(q[0], q[1])
            c.drawPath(ol, skia.Paint(AntiAlias=True, Color=col((12, 12, 16), 0.6 * alpha), Style=skia.Paint.kStroke_Style,
                                      StrokeWidth=lw * 1.4 + 3.2 * k, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join))
            hc0, up0, fwd0 = rig.head_frame(pose)
            c.drawCircle(*S(hc0), rig.p.head * 0.55 * k * 1.12 + 1.6 * k,
                         skia.Paint(AntiAlias=True, Color=col((12, 12, 16), 0.6 * alpha)))
        # far limbs
        if scarf is not None and mirror_y is None:
            self._scarf(c, scarf, S, hex_rgb(st.scarf_color), lw, alpha)
        stroke([j["shoulder_f"], j["elbow_f"], j["wrist_f"]], far, lw * 0.92)
        self._hand(c, pose, "f", j, S, far, lw, alpha)
        stroke([j["hip_f"], j["knee_f"], j["ankle_f"]], far, lw)
        stroke([j["ankle_f"], j["toe_f"]], far, lw * 1.35)
        # torso (tapered)
        stroke([j["pelvis"], j["spine_mid"], j["neck_base"]], near, lw * 1.12)
        stroke([j["neck_base"], j["neck_top"]], near, lw * 0.85)
        dot(j["pelvis"], lw * 0.75, near)
        # head with visor
        hc, up, fwd = rig.head_frame(pose)
        r = rig.p.head * 0.55
        head_pts = [(-10, 9), (-2, 13), (8, 11.5), (13, 3), (11, -6), (4, -12), (-6, -11), (-12, -2)]
        hf = 1.0 if abs(pose.head_facing) > 0 else 1.0
        H = lambda x, y: (hc[0] + fwd[0] * x * r / 12 + up[0] * y * r / 12, hc[1] + fwd[1] * x * r / 12 + up[1] * y * r / 12)
        path = skia.Path()
        for i, (x, y) in enumerate(head_pts):
            q = S(H(x, y))
            (path.lineTo if i else path.moveTo)(q[0], q[1])
        path.close()
        c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(near, alpha)))
        e = pose.eye
        vh = 2.6 * e
        vpath = skia.Path()
        for i, (x, y) in enumerate([(3, 4.5 + vh * 0.6), (13.4, 4.2 + vh * 0.5), (14.4, 4.2 - vh), (3.5, 4.5 - vh * 0.9)]):
            q = S(H(x, y))
            (vpath.lineTo if i else vpath.moveTo)(q[0], q[1])
        vpath.close()
        if mirror_y is None:
            c.drawPath(vpath, skia.Paint(AntiAlias=True, Color=col(vis, 0.8), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(1.0, 3 * k * e))))
        c.drawPath(vpath, skia.Paint(AntiAlias=True, Color=col(vis, alpha)))
        # near limbs
        stroke([j["hip_n"], j["knee_n"], j["ankle_n"]], near, lw * 1.05)
        stroke([j["ankle_n"], j["toe_n"]], near, lw * 1.4)
        stroke([j["shoulder_n"], j["elbow_n"], j["wrist_n"]], near, lw * 0.98)
        self._hand(c, pose, "n", j, S, near, lw, alpha)

    LIMBS = (("shoulder_n", "elbow_n", "wrist_n", "hand_n"), ("shoulder_f", "elbow_f", "wrist_f", "hand_f"),
             ("hip_n", "knee_n", "ankle_n", "toe_n"), ("hip_f", "knee_f", "ankle_f", "toe_f"))

    def _trail(self, c: skia.Canvas, cid: str, pose: Pose, ghosts: List[Tuple[Pose, float]]) -> None:
        """Motion trails: fading ghost limbs from slightly earlier poses, drawn only for limbs moving fast on screen
        (reads the arc of a fast move, in the spirit of hand-drawn smears)."""
        rig, st, j, k, S = self._char_paths(cid, pose)
        rgb = hex_rgb(st.glow_color)
        lw = st.limb_width * k
        for gpose, alpha in ghosts:
            jg = rig.world_joints(gpose)
            for chain in self.LIMBS:
                a, b = S(j[chain[-1]]), S(jg[chain[-1]])
                if math.hypot(a[0] - b[0], a[1] - b[1]) < 14.0:
                    continue
                path = skia.Path()
                for i, n in enumerate(chain[:-1] if "hand" in chain[-1] else chain[:-1]):
                    q = S(jg[n])
                    (path.lineTo if i else path.moveTo)(q[0], q[1])
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=lw * 0.9,
                                            StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join,
                                            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(1.0, 1.5 * k))))

    def _scarf(self, c, tails, S, rgb, lw, alpha) -> None:
        for ti, P in enumerate(tails):
            pts = [tuple(p) for p in P]
            for _ in range(2):  # Chaikin smoothing for a cloth-like curve
                q = [pts[0]]
                for a, b in zip(pts, pts[1:]):
                    q += [(a[0] * 0.75 + b[0] * 0.25, a[1] * 0.75 + b[1] * 0.25), (a[0] * 0.25 + b[0] * 0.75, a[1] * 0.25 + b[1] * 0.75)]
                q.append(pts[-1])
                pts = q
            scr = [S(p) for p in pts]
            w0, w1 = (1.45, 0.65) if ti == 0 else (1.15, 0.55)
            left, right = [], []
            for i, p in enumerate(scr):
                a, b = scr[max(0, i - 1)], scr[min(len(scr) - 1, i + 1)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                n = math.hypot(dx, dy) or 1.0
                w = lw * lerp(w0, w1, i / (len(scr) - 1)) / 2
                left.append((p[0] - dy / n * w, p[1] + dx / n * w))
                right.append((p[0] + dy / n * w, p[1] - dx / n * w))
            path = skia.Path()
            path.moveTo(*left[0])
            for p in left[1:]:
                path.lineTo(*p)
            for p in reversed(right):
                path.lineTo(*p)
            path.close()
            shade = rgb if ti == 0 else tuple(int(v * 0.8) for v in rgb)
            c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(shade, alpha)))

    def _hand(self, c, pose: Pose, side: str, j, S, rgb, lw, alpha) -> None:
        shape = pose.hands.get(side, "fist")
        w, h = S(j[f"wrist_{side}"]), S(j[f"hand_{side}"])
        if shape == "point":
            c.drawLine(w[0], w[1], h[0], h[1], skia.Paint(AntiAlias=True, Color=col(rgb, alpha), StrokeWidth=lw * 0.55, StrokeCap=skia.Paint.kRound_Cap))
            c.drawCircle(w[0], w[1], lw * 0.75, skia.Paint(AntiAlias=True, Color=col(rgb, alpha)))
        elif shape == "open":
            m = ((w[0] + h[0]) / 2, (w[1] + h[1]) / 2)
            c.drawLine(w[0], w[1], m[0], m[1], skia.Paint(AntiAlias=True, Color=col(rgb, alpha), StrokeWidth=lw * 1.25, StrokeCap=skia.Paint.kRound_Cap))
        else:
            c.drawCircle(w[0], w[1], lw * 0.85, skia.Paint(AntiAlias=True, Color=col(rgb, alpha)))

    def _door_geom(self, ex):
        """Doorway quad on its surface: `width` along the surface, and a depth span that includes the character plane
        (z = 0) and reaches well back so the door reads as a panel even though side surfaces are seen edge-on."""
        a, b = ex.s - ex.width / 2, ex.s + ex.width / 2
        return a, b, -100.0, 320.0

    def _exits(self, c: skia.Canvas, fs: FrameState) -> None:
        """Exit doors with their state machine: sealed (red bars) -> unlocking (bars retract, turn green) -> unlocked ->
        opening (the leaf slides back into the wall, white light behind) -> open."""
        for ex in self.env.exits:
            state, u = fs.doors.get(ex.id, ("sealed", 0.0))
            surf = ex.surface
            SP = lambda s_, h, z: self._SP(surf, s_, h, z)
            a, b, z0, z1 = self._door_geom(ex)
            pulse = 0.85 + 0.15 * math.sin(fs.t * 4.2)
            openness = {"opening": u, "open": 1.0, "exited": 1.0, "closing": 1.0 - u}.get(state, 0.0)
            mid = self.P(*SP(ex.s, 0.5, 0))
            self._glow(c, (mid[0], mid[1]), max((260 + 120 * openness) * mid[2], 40), (150, 245, 255), (0.25 + 0.12 * openness) * pulse)
            c.drawPath(self.poly([SP(a - 16, 0.6, z0 - 16), SP(a - 16, 0.6, z1 + 16), SP(b + 16, 0.6, z1 + 16), SP(b + 16, 0.6, z0 - 16)]),
                       skia.Paint(AntiAlias=True, Color=col((32, 42, 50))))
            door = self.poly([SP(a, 0.8, z0), SP(a, 0.8, z1), SP(b, 0.8, z1), SP(b, 0.8, z0)])
            pa, pb = self.P(*SP(b, 0.8, 0)), self.P(*SP(a, 0.8, 0))
            # the doorway: bright outside light (visible as the leaf slides away)
            sh_out = skia.GradientShader.MakeLinear([skia.Point(pa[0], pa[1]), skia.Point(pb[0], pb[1])],
                                                    [col((255, 255, 255)), col((205, 250, 255)), col((255, 255, 255))], [0, 0.5, 1])
            c.drawPath(door, skia.Paint(AntiAlias=True, Shader=sh_out))
            # door leaf (glowing panel) slides back along the depth axis while opening
            if openness < 1.0:
                zl = z0 + (z1 - z0) * openness
                leaf = self.poly([SP(a, 1.0, zl), SP(a, 1.0, z1), SP(b, 1.0, z1), SP(b, 1.0, zl)])
                sh = skia.GradientShader.MakeLinear([skia.Point(pa[0], pa[1]), skia.Point(pb[0], pb[1])],
                                                    [col((150, 230, 245), 0.95 * pulse), col((70, 190, 215), 0.85 * pulse),
                                                     col((150, 230, 245), 0.95 * pulse)], [0, 0.5, 1])
                c.drawPath(leaf, skia.Paint(AntiAlias=True, Shader=sh))
            c.drawPath(door, skia.Paint(AntiAlias=True, Color=col(WHITE, 0.95), Style=skia.Paint.kStroke_Style, StrokeWidth=3.0))
            if state in ("sealed", "unlocking") and ex.sealed:
                k = 1.0 - (u if state == "unlocking" else 0.0)  # bars retract into the frame
                rgb = mix(self.alert, GREEN, smoothstep(0.0, 0.5, u) if state == "unlocking" else 0.0)
                for i in range(1, 5):
                    ss = lerp(a, b, i / 5)
                    zc, zh = (z0 + z1) / 2, (z1 - z0 - 16) / 2 * k
                    c.drawPath(self.poly([SP(ss - 5, 1.2, zc - zh), SP(ss - 5, 1.2, zc + zh), SP(ss + 5, 1.2, zc + zh), SP(ss + 5, 1.2, zc - zh)]),
                               skia.Paint(AntiAlias=True, Color=col(rgb, 0.9)))
            # status lights at the frame ends
            lamp = self.alert if state == "sealed" else GREEN
            for ss in (a - 9, b + 9):
                q = self.P(*SP(ss, 1.0, z0 - 8))
                c.drawCircle(q[0], q[1], max(1.5, 5 * q[2]), skia.Paint(AntiAlias=True, Color=col(lamp)))
                self._glow(c, (q[0], q[1]), 22 * q[2], lamp, 0.5)
            if openness > 0:  # light beyond the doorway (character plane): bright at the threshold, falling off outward
                x0, y0, x1, y1 = exit_portal(self.env, ex.id)
                corr = self.poly([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)])
                n = surface_normal(surf)
                p_in = surface_point(self.env, surf, ex.s, 0.0)
                p_out = (p_in[0] - n[0] * 300, p_in[1] - n[1] * 300)
                qa, qb = self.P(p_in[0], p_in[1], 0), self.P(p_out[0], p_out[1], 0)
                sh = skia.GradientShader.MakeLinear([skia.Point(qa[0], qa[1]), skia.Point(qb[0], qb[1])],
                                                    [col((250, 255, 255), 0.97 * openness), col((190, 242, 252), 0.75 * openness),
                                                     col((120, 200, 220), 0.3 * openness)], [0.0, 0.55, 1.0])
                c.drawPath(corr, skia.Paint(AntiAlias=True, Shader=sh))
                for side in (a, b):  # door jambs
                    j0 = surface_point(self.env, surf, side, 0.0)
                    j1 = (j0[0] - n[0] * 90, j0[1] - n[1] * 90)
                    self.line3(c, (j0[0], j0[1], 0), (j1[0], j1[1], 0), WHITE, 0.8 * openness, 2.5)

    def _open_exits(self, fs: FrameState):
        return [ex for ex in self.env.exits if fs.doors.get(ex.id, ("sealed", 0))[0] in ("opening", "open", "exited", "closing")]

    def _passed_exits(self, fs: FrameState):
        """Exits a character may be beyond (open, or closed behind someone who walked out)."""
        return [ex for ex in self.env.exits if fs.doors.get(ex.id, ("sealed", 0))[0] in ("opening", "open", "exited", "closing", "closed")]

    def _exit_fade(self, pose: Pose, fs: FrameState) -> float:
        """Characters walking out through an open doorway fade into the light beyond it."""
        alpha = 1.0
        for ex in self._passed_exits(fs):
            n = surface_normal(ex.surface)
            o = surface_point(self.env, ex.surface, ex.s, 0.0)
            d = -((pose.root[0] - o[0]) * n[0] + (pose.root[1] - o[1]) * n[1])  # >0 beyond the plane
            alpha = min(alpha, 1.0 - smoothstep(20.0, 115.0, d))
        return alpha

    def _interior_clip(self, fs: FrameState) -> Optional[skia.Path]:
        exits = self._open_exits(fs)
        if not exits:
            return None
        path = self.poly([(-self.hw, 0, 0), (self.hw, 0, 0), (self.hw, self.rh, 0), (-self.hw, self.rh, 0)])
        for ex in exits:
            x0, y0, x1, y1 = exit_portal(self.env, ex.id)
            path = skia.Op(path, self.poly([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]), skia.PathOp.kUnion_PathOp) or path
        return path

    def _shafts(self, c: skia.Canvas, fs: Optional[FrameState] = None) -> None:
        """Soft volumetric light shafts from the doorway and the exits (additive, low alpha); an open exit pours light."""
        hw = self.hw
        beams = []
        if self.env.room.entry_door:
            beams.append(((-hw, 0.0), (-hw, 230.0), (-hw + 520, 0.0), (-hw + 380, 0.0), (190, 240, 255), 1.0))
        for ex in self.env.exits:
            state, u = fs.doors.get(ex.id, ("sealed", 0.0)) if fs else ("sealed", 0.0)
            gain = 1.0 + 1.1 * ({"opening": u, "open": 1.0, "exited": 1.0, "closing": 1.0 - u}.get(state, 0.0))
            a, b = ex.s - ex.width / 2, ex.s + ex.width / 2
            pa, pb = surface_point(self.env, ex.surface, a, 0), surface_point(self.env, ex.surface, b, 0)
            pc, pd = surface_point(self.env, ex.surface, a - 200, 620), surface_point(self.env, ex.surface, b + 160, 620)
            beams.append((pa, pb, pc, pd, (120, 240, 255), gain))
        for a, b, cpt, d, rgb, gain in beams:
            pa, pb, pc, pd = self.P(a[0], a[1], 0), self.P(b[0], b[1], 0), self.P(cpt[0], cpt[1], 0), self.P(d[0], d[1], 0)
            path = skia.Path()
            path.moveTo(pa[0], pa[1]); path.lineTo(pb[0], pb[1]); path.lineTo(pd[0], pd[1]); path.lineTo(pc[0], pc[1]); path.close()
            mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
            ex_, ey_ = (pc[0] + pd[0]) / 2, (pc[1] + pd[1]) / 2
            sh = skia.GradientShader.MakeLinear([skia.Point(mx, my), skia.Point(ex_, ey_)], [col(rgb, min(0.4, 0.16 * gain)), col(rgb, 0.0)])
            c.drawPath(path, skia.Paint(AntiAlias=True, Shader=sh, BlendMode=skia.BlendMode.kPlus))

    def _back_shadow(self, c: skia.Canvas, cid: str, pose: Pose, fs: FrameState) -> None:
        """Soft silhouette shadow on the back wall (key light near the camera, slightly above-left).

        A light near the lens throws a shadow roughly the character's own on-screen size, offset a little: it is
        drawn at the character's screen scale (not shrunk to back-wall depth, which read as a second, distant
        figure in 1C review) and heavily blurred so it reads as light, not as a body."""
        k0 = self._zfn()
        c.save()
        c.translate(9.0 * k0, 7.0 * k0)  # screen offset: down-right of the character
        blur = 7.0 * k0 + 4
        layer = skia.Paint(ImageFilter=skia.ImageFilters.Blur(blur, blur), Color=col((0, 0, 0), 0.26))
        c.saveLayer(None, layer)
        self._character(c, cid, pose, alpha=1.0, mirror_y=None, scarf=fs.scarves.get(cid), tint=(0, 0, 0))
        c.restore()
        c.restore()

    def _dust(self, c: skia.Canvas, fs: FrameState, front: bool) -> None:
        if fs.dust is None:
            return
        P, Q = fs.dust, fs.dust_prev
        sel = (P[:, 2] < 0) if front else (P[:, 2] >= 0)
        for p, q in zip(P[sel], Q[sel]):
            a = self.P(float(p[0]), float(p[1]), float(p[2]))
            b = self.P(float(q[0]), float(q[1]), float(q[2]))
            sz = clamp(1.6 * a[2], 0.8, 6.0)
            alpha = clamp(0.55 - (float(p[2]) + self.Fd) / 6000.0, 0.12, 0.5)
            paint = skia.Paint(AntiAlias=True, Color=col(self.dust_rgb, alpha), StrokeWidth=sz, StrokeCap=skia.Paint.kRound_Cap, Style=skia.Paint.kStroke_Style)
            if math.hypot(a[0] - b[0], a[1] - b[1]) > 2.5:
                c.drawLine(b[0], b[1], a[0], a[1], paint)
            else:
                c.drawPoint(a[0], a[1], paint)

    def _reflection(self, c: skia.Canvas, cid: str, pose: Pose) -> None:
        hw = self.hw
        floor = self.poly([(-hw, 0, self.near), (hw, 0, self.near), (hw, 0, self.back), (-hw, 0, self.back)])
        c.save()
        c.clipPath(floor, doAntiAlias=True)
        self._character(c, cid, pose, alpha=0.16, mirror_y=0.0)
        c.restore()

    def _contact_shadow(self, c: skia.Canvas, cid: str, pose: Pose) -> None:
        px, py = pose.root
        dz = self.depth.get(cid, 0.0)  # the shadow lies at the character's own depth lane (a depth cue)
        for d, at, horiz in ((py, (px, 0.0), True), (self.rh - py, (px, self.rh), True), (self.hw - px, (self.hw - 0.5, py), False),
                             (px + self.hw, (-self.hw + 0.5, py), False)):
            if 0 <= d < 260:
                p = self.P(at[0], at[1], 4 + dz)
                if horiz:
                    self._shadow(c, p, 70 * p[2], 0.55 * (1 - d / 260), squash=0.22)
                else:
                    self._shadow(c, p, 70 * p[2], 0.55 * (1 - d / 260), squash=1.0, sx=0.25)

    def _shadow(self, c, p, radius, alpha, squash=1.0, sx=1.0) -> None:
        c.save()
        c.translate(p[0], p[1])
        c.scale(sx, squash)
        sh = skia.GradientShader.MakeRadial(skia.Point(0, 0), max(1.0, radius), [col((0, 0, 0), alpha), col((0, 0, 0), 0.0)])
        c.drawCircle(0, 0, radius, skia.Paint(AntiAlias=True, Shader=sh))
        c.restore()

    # ------------------------------------------------------------ effects
    def _effect(self, c: skia.Canvas, e: dict, t: float) -> None:
        age = t - e["t"]
        kind = e["kind"]
        if kind == "ring_floor":
            u = age / e.get("life", 0.8)
            if not 0 <= u <= 1:
                return
            R = e["r0"] + e["speed"] * age
            p = self.P(e["x"], e.get("y", 0.0), e.get("z", 48))
            c.save()
            c.translate(p[0], p[1])
            c.scale(1, 0.22)
            c.drawCircle(0, 0, R * p[2], skia.Paint(AntiAlias=True, Color=col(e.get("rgb", self.alert), 0.8 * (1 - u)), Style=skia.Paint.kStroke_Style, StrokeWidth=(6 * (1 - u) + 1) * 4))
            c.restore()
        elif kind == "ring_wall":
            u = age / e.get("life", 0.7)
            if not 0 <= u <= 1:
                return
            R = e["r0"] + e["speed"] * (1 - (1 - u) ** 3) * e.get("life", 0.7)
            p = self.P(e.get("x", self.hw - 0.5), e["y"], 0)
            c.save()
            c.translate(p[0], p[1])
            c.scale(0.28, 1)
            c.drawCircle(0, 0, R * p[2], skia.Paint(AntiAlias=True, Color=col((180, 250, 255), 0.9 * (1 - u)), Style=skia.Paint.kStroke_Style, StrokeWidth=(4 * (1 - u) + 1) * 3))
            c.restore()
            self._glow(c, (p[0], p[1]), 150 * p[2], (160, 250, 255), 0.45 * (1 - u))
        elif kind == "sweep":
            u = age / e.get("life", 0.45)
            if not 0 <= u <= 1:
                return
            x = lerp(-self.hw, self.hw, u)
            a = math.sin(math.pi * u)
            c.drawPath(self.poly([(x - 10, 0, 690), (x + 10, 0, 690), (x + 10, self.rh, 690), (x - 10, self.rh, 690)]),
                       skia.Paint(AntiAlias=True, Color=col((150, 250, 255), 0.5 * a), BlendMode=skia.BlendMode.kPlus))
        elif kind == "burst":  # hard impact: radial speed streaks hugging the surface + debris flicks
            u = age / e.get("life", 0.32)
            if not 0 <= u <= 1:
                return
            nx, ny = e["n"]
            tx_, ty_ = ny, -nx
            rng = np.random.default_rng(e.get("seed", 1))
            st = e.get("strength", 1.0)
            grow = 1 - (1 - u) ** 3
            for i in range(14):
                ang = rng.uniform(-1.25, 1.25)  # mostly along the surface, some lifting off it
                side = 1 if i % 2 else -1
                dx = tx_ * side * math.cos(ang) + nx * abs(math.sin(ang))
                dy = ty_ * side * math.cos(ang) + ny * abs(math.sin(ang))
                L = rng.uniform(60, 150) * st
                r0, r1 = 14 + L * 0.35 * grow, 14 + L * grow
                a3 = self.P(e["x"] + dx * r0, e["y"] + dy * r0, 0)
                b3 = self.P(e["x"] + dx * r1, e["y"] + dy * r1, 0)
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col((235, 250, 255), 0.85 * (1 - u)),
                                                                 StrokeWidth=max(1.0, 2.6 * a3[2] * (1 - u)), StrokeCap=skia.Paint.kRound_Cap))
            for i in range(10):  # debris specks thrown off the surface
                ang = rng.uniform(-1.4, 1.4)
                v = rng.uniform(140, 320) * st
                dx = tx_ * math.sin(ang) + nx * math.cos(ang)
                dy = ty_ * math.sin(ang) + ny * math.cos(ang)
                d = v * age
                p3 = self.P(e["x"] + dx * d, e["y"] + dy * d, rng.uniform(-30, 30))
                c.drawCircle(p3[0], p3[1], max(1.0, 2.2 * p3[2]), skia.Paint(AntiAlias=True, Color=col((200, 225, 235), 0.9 * (1 - u))))
            p0 = self.P(e["x"], e["y"], 0)
            self._glow(c, (p0[0], p0[1]), (40 + 160 * grow) * p0[2], (230, 250, 255), 0.55 * (1 - u))
        elif kind == "flash":  # short light burst (grab spark, door unlock, door open)
            u = age / e.get("life", 0.5)
            if not 0 <= u <= 1:
                return
            p = self.P(e["x"], e["y"], 0)
            self._glow(c, (p[0], p[1]), (e.get("r", 60) + e.get("grow", 120) * u) * p[2], e.get("rgb", (255, 230, 150)), e.get("a", 0.7) * (1 - u))
        elif kind == "impact":  # a blow lands: spikes radiating from the contact, a hot core and a ring
            u = age / e.get("life", 0.24)
            if not 0 <= u <= 1:
                return
            p = self.P(e["x"], e["y"], 0)
            st = e.get("strength", 1.0)
            rng = np.random.default_rng(e.get("seed", 3))
            grow = 1 - (1 - u) ** 3
            fade = (1 - u) ** 1.5
            n = 11
            for i in range(n):
                ang = 2 * math.pi * i / n + rng.uniform(-0.18, 0.18)
                L = (rng.uniform(26, 54) if i % 2 else rng.uniform(52, 92)) * st
                r0, r1 = 6 + 0.3 * L * grow, 8 + L * (0.35 + 0.65 * grow)
                a3 = (p[0] + math.cos(ang) * r0 * p[2], p[1] - math.sin(ang) * r0 * p[2])
                b3 = (p[0] + math.cos(ang) * r1 * p[2], p[1] - math.sin(ang) * r1 * p[2])
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col((255, 250, 235), 0.95 * fade),
                                                                 StrokeWidth=max(1.2, (4.5 if i % 2 == 0 else 2.6) * st * p[2] * (1 - u)),
                                                                 StrokeCap=skia.Paint.kRound_Cap))
            c.drawCircle(p[0], p[1], (10 + 34 * grow) * st * p[2], skia.Paint(AntiAlias=True, Color=col((255, 255, 255), 0.7 * fade),
                                                                                Style=skia.Paint.kStroke_Style, StrokeWidth=max(1.0, 3.5 * st * (1 - u) * p[2])))
            c.drawCircle(p[0], p[1], max(1.0, 9 * st * (1 - u) * p[2]), skia.Paint(AntiAlias=True, Color=col((255, 255, 255), fade)))
        elif kind == "spark":  # blocked: bright sparks thrown off the guard
            u = age / e.get("life", 0.3)
            if not 0 <= u <= 1:
                return
            rng = np.random.default_rng(e.get("seed", 5))
            st = e.get("strength", 1.0)
            for i in range(12):
                ang = rng.uniform(0.2, math.pi - 0.2) * (1 if i % 3 else -0.4)
                v = rng.uniform(160, 380) * st
                x = e["x"] + math.cos(ang) * v * age
                y = e["y"] + math.sin(ang) * v * age - 700 * age * age
                tail = 0.035
                xa = e["x"] + math.cos(ang) * v * max(0.0, age - tail)
                ya = e["y"] + math.sin(ang) * v * max(0.0, age - tail) - 700 * max(0.0, age - tail) ** 2
                a3, b3 = self.P(xa, ya, 0), self.P(x, y, 0)
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col((255, 215, 120), 1 - u),
                                                                 StrokeWidth=max(1.0, 2.4 * b3[2]), StrokeCap=skia.Paint.kRound_Cap))
        elif kind == "swoosh":  # the arc a fast fist / foot cuts through the air
            t_end = e["t_end"]
            if t < e["t"] or t > t_end + 0.16:
                return
            pts = [pp for (tp, pp) in e["pts"] if tp <= t]
            if len(pts) < 2:
                return
            fade = 1.0 if t <= t_end else 1.0 - (t - t_end) / 0.16
            P2 = [self.P(x, y, 0) for (x, y) in pts]
            for i in range(1, len(P2)):
                w = i / (len(P2) - 1)
                a3, b3 = P2[i - 1], P2[i]
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=col(e.get("rgb", (255, 255, 255)), 0.55 * w * fade),
                                                                 StrokeWidth=max(1.0, 11.0 * w * b3[2]), StrokeCap=skia.Paint.kRound_Cap,
                                                                 BlendMode=skia.BlendMode.kPlus))
        elif kind == "dust":
            u = age / 0.5
            if not 0 <= u <= 1:
                return
            p = self.P(e["x"], e["y"], 0)
            self._glow(c, (p[0], p[1]), (12 + 30 * u) * p[2], (200, 220, 230), 0.25 * (1 - u))

    # ------------------------------------------------------------ Milestone 3: smears and screen effects
    SMEAR_MIN = 9.0  # world units a limb end must travel in the smear interval before it smears

    def _smear(self, c: skia.Canvas, cid: str, pose: Pose, prev: Pose) -> None:
        """A tapered smear behind each fast limb segment: the quad between where the bone was a moment ago and where it
        is now, bright at the leading edge and fading out behind (the classic action-animation smear frame)."""
        rig = self.rigs[cid]
        j, jp = rig.world_joints(pose), rig.world_joints(prev)
        rgb = hex_rgb(self.styles[cid].glow_color)
        dz = self.depth.get(cid, 0.0)
        for chain in (("shoulder_n", "elbow_n", "hand_n"), ("shoulder_f", "elbow_f", "hand_f"), ("hip_n", "knee_n", "ankle_n", "toe_n"),
                      ("hip_f", "knee_f", "ankle_f", "toe_f")):
            for a, b in zip(chain, chain[1:]):
                if a not in j or b not in j:
                    continue
                move = max(math.dist(j[b], jp[b]), math.dist(j[a], jp[a]))
                if move < self.SMEAR_MIN:
                    continue
                k = min(1.0, (move - self.SMEAR_MIN) / 40.0)
                pts = [self.P(*j[a], dz), self.P(*j[b], dz), self.P(*jp[b], dz), self.P(*jp[a], dz)]
                path = skia.Path()
                path.moveTo(pts[0][0], pts[0][1])
                for p in pts[1:]:
                    path.lineTo(p[0], p[1])
                path.close()
                mid_now = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
                mid_old = ((pts[2][0] + pts[3][0]) / 2, (pts[2][1] + pts[3][1]) / 2)
                sh = skia.GradientShader.MakeLinear([skia.Point(*mid_now), skia.Point(*mid_old)],
                                                    [col(rgb, 0.55 * k), col(rgb, 0.0)])
                c.drawPath(path, skia.Paint(AntiAlias=True, Shader=sh))

    def _prop_ghost(self, c: skia.Canvas, pr, x: float, y: float, a: float, alpha: float) -> None:
        from ..scene import glyphs
        sp = next((p for p in self.env.props if p.id == pr.id), None)
        if sp is None or sp.kind != "glyph":
            return
        ca, sa = math.cos(a), math.sin(a)
        strokes = [[(x + u * ca - v * sa, y + u * sa + v * ca) for u, v in st] for st in glyphs.strokes(getattr(pr, "glyph", None) or sp.glyph, sp.size)]
        path, k = self._glyph_strokes_path(strokes, pr.z)
        rgb = hex_rgb(sp.color) if sp.color else self.accent
        w = max(1.5, (sp.weight or glyphs.default_weight(sp.size)) * k)
        c.drawPath(path, skia.Paint(AntiAlias=True, Color=col(rgb, alpha), Style=skia.Paint.kStroke_Style, StrokeWidth=w,
                                    StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join,
                                    MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, max(1.0, 0.3 * w))))

    def _screen_fx(self, c: skia.Canvas, s: Dict[str, float]) -> None:
        W, H = self.W, self.H
        lines = s.get("lines", 0.0)
        if lines > 0.01:  # slow motion: thin radial speed lines toward the frame edge
            import random
            rnd = random.Random(int(s.get("seed", 0)))
            cx, cy = W / 2, H / 2
            for _ in range(46):
                ang = rnd.uniform(0, 2 * math.pi)
                r0 = rnd.uniform(0.42, 0.6) * H
                r1 = r0 + rnd.uniform(0.25, 0.6) * H
                c.drawLine(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0, cx + math.cos(ang) * r1, cy + math.sin(ang) * r1,
                           skia.Paint(AntiAlias=True, Color=col((235, 240, 255), 0.16 * lines * rnd.uniform(0.4, 1.0)),
                                      StrokeWidth=max(1.0, H / 720 * rnd.uniform(0.8, 2.2))))
        vig = s.get("vignette", 0.0)
        if vig > 0.01:  # a blow: the edges darken for an instant (focus on the impact)
            sh = skia.GradientShader.MakeRadial(skia.Point(W / 2, H / 2), H * 0.95, [col((0, 0, 0), 0.0), col((0, 0, 0), 0.55 * vig)], [0.45, 1.0])
            c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=sh))
        fl = s.get("flash", 0.0)
        if fl > 0.01:  # impact flash: brightest at the blow, fading toward the edges, so the characters keep their detail
            fx_, fy_ = W / 2, H / 2
            if s.get("world") is not None:  # centred on the blow
                px, py, _ = self.P(*s["world"], 0.0)
                fx_, fy_ = W / 2 + px, H / 2 + py
            sh = skia.GradientShader.MakeRadial(skia.Point(fx_, fy_), H * 0.75,
                                                [col((255, 250, 240), min(0.3, fl)), col((255, 250, 240), 0.35 * min(0.3, fl)),
                                                 col((255, 250, 240), 0.0)], [0.0, 0.35, 1.0])
            c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=sh, BlendMode=skia.BlendMode.kScreen))

    def _post(self, c: skia.Canvas, red: float) -> None:
        if self.bloom:
            img = self.surface.makeImageSnapshot()
            sc = self.small.getCanvas()
            sc.clear(skia.ColorTRANSPARENT)
            p = skia.Paint(ImageFilter=skia.ImageFilters.Blur(6, 6), ColorFilter=skia.ColorFilters.Matrix([
                2.4, 0, 0, 0, -0.65, 0, 2.4, 0, 0, -0.65, 0, 0, 2.4, 0, -0.65, 0, 0, 0, 1, 0]))
            sc.drawImageRect(img, skia.Rect(0, 0, self.W / 4, self.H / 4), skia.SamplingOptions(skia.FilterMode.kLinear), p)
            small = self.small.makeImageSnapshot()
            c.drawImageRect(small, skia.Rect(0, 0, self.W, self.H), skia.SamplingOptions(skia.FilterMode.kLinear),
                            skia.Paint(BlendMode=skia.BlendMode.kPlus, Color=col((255, 255, 255), 0.55)))
        if red > 0.01:
            c.drawRect(skia.Rect(0, 0, self.W, self.H), skia.Paint(Color=col((255, 30, 45), 0.26 * red), BlendMode=skia.BlendMode.kScreen))
        sh = skia.GradientShader.MakeRadial(skia.Point(self.W / 2, self.H / 2), self.H * 1.05, [col((0, 0, 0), 0.0), col((0, 0, 0), 0.0), col((0, 0, 0), 0.6)], [0.0, 0.33, 1.0])
        c.drawRect(skia.Rect(0, 0, self.W, self.H), skia.Paint(Shader=sh))
