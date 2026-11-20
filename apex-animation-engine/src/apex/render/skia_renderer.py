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
        self.focal = height * FOV_K
        info = skia.ImageInfo.Make(width, height, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
        self.surface = skia.Surface.MakeRaster(info)
        sinfo = skia.ImageInfo.Make(width // 4, height // 4, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
        self.small = skia.Surface.MakeRaster(sinfo)
        r = env.room
        self.hw, self.rh, self.back, self.near = r.width / 2, r.height, r.depth_back, r.depth_front
        self.grid = r.grid_spacing

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
    def render(self, fs: FrameState, cam: CameraState, red_flash: float = 0.0, fx: Optional[List[dict]] = None, fade: float = 0.0) -> np.ndarray:
        self._setup(cam)
        c = self.surface.getCanvas()
        c.clear(col((5, 6, 8)))
        c.save()
        sc = self.H / 1080.0
        c.translate(self.W / 2 + cam.shx * sc, self.H / 2 + cam.shy * sc)
        c.rotate(cam.roll)
        self._room(c, fs, red_flash)
        self._exits(c, fs)
        self._shafts(c, fs)
        self._switches(c, fs)
        self._obstacles(c, back=True)
        self._dust(c, fs, front=False)
        vis = {cid: self._exit_fade(pose, fs) for cid, pose in fs.poses.items()}
        for cid, pose in fs.poses.items():
            if vis[cid] > 0.99:
                self._back_shadow(c, cid, pose, fs)
        for pr in fs.props:
            self._prop(c, pr)
        for cid, pose in fs.poses.items():
            if vis[cid] > 0.99:
                self._reflection(c, cid, pose)
                self._contact_shadow(c, cid, pose)
        for e in fx or []:
            self._effect(c, e, fs.t)
        for cid, pose in fs.poses.items():
            if vis[cid] <= 0.0:
                continue
            c.save()
            clip = self._interior_clip(fs)
            if clip is not None:
                c.clipPath(clip, doAntiAlias=True)
            self._character(c, cid, pose, alpha=vis[cid], scarf=fs.scarves.get(cid))
            c.restore()
        self._obstacles(c, back=False)
        self._dust(c, fs, front=True)
        self._cutaway(c, red_flash, fs)
        c.restore()
        self._post(c, red_flash)
        if fade > 0.0:  # shot fade to black (end of film)
            c.drawRect(skia.Rect(0, 0, self.W, self.H), skia.Paint(Color=col((0, 0, 0), clamp(fade, 0.0, 1.0))))
        img = self.surface.makeImageSnapshot()
        return img.toarray(colorType=skia.ColorType.kRGBA_8888_ColorType)

    # ------------------------------------------------------------ environment
    def _room(self, c: skia.Canvas, fs: FrameState, red: float) -> None:
        hw, rh, bk, nr = self.hw, self.rh, self.back, self.near
        planes = {
            "back": ([(-hw, 0, bk), (hw, 0, bk), (hw, rh, bk), (-hw, rh, bk)], (21, 24, 30)),
            "floor": ([(-hw, 0, nr), (hw, 0, nr), (hw, 0, bk), (-hw, 0, bk)], (10, 12, 15)),
            "left": ([(-hw, 0, nr), (-hw, 0, bk), (-hw, rh, bk), (-hw, rh, nr)], (17, 20, 25)),
            "right": ([(hw, 0, nr), (hw, 0, bk), (hw, rh, bk), (hw, rh, nr)], (17, 20, 25)),
            "ceil": ([(-hw, rh, nr), (hw, rh, nr), (hw, rh, bk), (-hw, rh, bk)], (8, 9, 11)),
        }
        for name, (pts, rgb) in planes.items():
            c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(mix(rgb, (60, 10, 14), red * 0.5))))
        gcol = mix(CYAN, RED, clamp(red * 1.3, 0, 1))
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
        shader = skia.GradientShader.MakeLinear([skia.Point(0, top), skia.Point(0, mid)], [col((4, 5, 7), 0.85), col((4, 5, 7), 0.0)])
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
                self._glow(c, (fl[0], fl[1]), (220 + 120 * min(glow, 2.5)) * fl[2], RED, 0.16 * min(glow, 2.5), squash=0.25)
            else:
                c.save()
                c.translate(fl[0], fl[1])
                c.scale(0.25, 1.0)
                self._glow(c, (0, 0), (220 + 120 * min(glow, 2.5)) * fl[2], RED, 0.16 * min(glow, 2.5))
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
            c.drawPath(strip, skia.Paint(AntiAlias=True, Color=col(RED, 0.9 * min(1.2, glow))))
            # display: arrow showing the current gravity direction (absolute, world frame)
            sc = self.P(*SP(x, top * 0.55, z0 - 0.5))
            k = sc[2]
            c.save()
            c.translate(sc[0], sc[1])
            c.scale(k, k)
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(Color=col((8, 14, 18))))
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(AntiAlias=True, Color=col(CYAN, 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
            c.rotate(self.indicator_rotation(fs.gravity))
            p = skia.Paint(AntiAlias=True, Color=col(CYAN), Style=skia.Paint.kStroke_Style, StrokeWidth=2.6, StrokeCap=skia.Paint.kRound_Cap)
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
            sh = skia.GradientShader.MakeRadial(skia.Point(0, -5 * kb), 14 * kb, [col((255, 220, 220), min(1, 0.6 + glow * 0.4)), col(RED), col((140, 10, 20))], [0.0, 0.45, 1.0])
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
            cx_, cy_ = ob.center
            if ob.kind == "bar":
                self._rail(c, ob, back)
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
            base = (44, 50, 58)
            for pts, shade in faces:
                c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(mix((0, 0, 0), base, shade))))
                c.drawPath(self.poly(pts), skia.Paint(AntiAlias=True, Color=col(CYAN, 0.35), Style=skia.Paint.kStroke_Style, StrokeWidth=1.0))
            if not back:  # front cap with hazard stripes
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
                c.drawPath(cap, skia.Paint(AntiAlias=True, Color=col(CYAN, 0.6), Style=skia.Paint.kStroke_Style, StrokeWidth=1.4))

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
            c.drawRect(skia.Rect(q[0] - s_, q[1] - s_, q[0] + s_, q[1] + s_), skia.Paint(AntiAlias=True, Color=col(CYAN, 0.6), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
            for dx, dy in ((-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6), (0.6, 0.6)):
                c.drawCircle(q[0] + dx * s_, q[1] + dy * s_, max(1.0, 2.5 * q[2]), skia.Paint(AntiAlias=True, Color=col((200, 210, 220))))
        else:  # end cap at the front
            q = self.P(x, y, nr)
            c.drawCircle(q[0], q[1], max(2.0, 1.6 * r * q[2]), skia.Paint(AntiAlias=True, Color=col((255, 196, 40))))
            c.drawCircle(q[0], q[1], max(2.0, 1.6 * r * q[2]), skia.Paint(AntiAlias=True, Color=col((40, 30, 10)), Style=skia.Paint.kStroke_Style, StrokeWidth=1.5))

    def _prop(self, c: skia.Canvas, pr) -> None:
        sx, sy, k = self.P(pr.pos[0], pr.pos[1], 0)
        w, h = pr.size[0] * k, pr.size[1] * k
        c.save()
        c.translate(sx, sy)
        c.rotate(-math.degrees(pr.angle))
        sh = skia.GradientShader.MakeLinear([skia.Point(-w / 2, 0), skia.Point(w / 2, 0)], [col((60, 70, 78)), col((140, 155, 165)), col((50, 58, 66))], [0, 0.45, 1])
        r = skia.Rect(-w / 2, -h / 2, w / 2, h / 2)
        c.drawRect(r, skia.Paint(AntiAlias=True, Shader=sh))
        c.drawRect(r, skia.Paint(AntiAlias=True, Color=col(CYAN, 0.55), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
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
        e = mix(CYAN, RED, clamp(red * 1.3, 0, 1))
        for a, b in (((-hw, 0, z), (hw, 0, z)), ((hw, 0, z), (hw, rh, z)), ((-hw, 0, z), (-hw, rh, z))):
            self.line3(c, a, b, e, 1.0, 3.0)

    # ------------------------------------------------------------ characters
    def _zfn(self) -> float:
        return self.focal / self.Fd

    def _char_paths(self, cid: str, pose: Pose):
        rig, st = self.rigs[cid], self.styles[cid]
        j = rig.world_joints(pose)
        k = self._zfn()
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
                rgb = mix(RED, GREEN, smoothstep(0.0, 0.5, u) if state == "unlocking" else 0.0)
                for i in range(1, 5):
                    ss = lerp(a, b, i / 5)
                    zc, zh = (z0 + z1) / 2, (z1 - z0 - 16) / 2 * k
                    c.drawPath(self.poly([SP(ss - 5, 1.2, zc - zh), SP(ss - 5, 1.2, zc + zh), SP(ss + 5, 1.2, zc + zh), SP(ss + 5, 1.2, zc - zh)]),
                               skia.Paint(AntiAlias=True, Color=col(rgb, 0.9)))
            # status lights at the frame ends
            lamp = RED if state == "sealed" else GREEN
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
            paint = skia.Paint(AntiAlias=True, Color=col((190, 245, 255), alpha), StrokeWidth=sz, StrokeCap=skia.Paint.kRound_Cap, Style=skia.Paint.kStroke_Style)
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
        for d, at, horiz in ((py, (px, 0.0), True), (self.rh - py, (px, self.rh), True), (self.hw - px, (self.hw - 0.5, py), False),
                             (px + self.hw, (-self.hw + 0.5, py), False)):
            if 0 <= d < 260:
                p = self.P(at[0], at[1], 4)
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
            c.drawCircle(0, 0, R * p[2], skia.Paint(AntiAlias=True, Color=col(e.get("rgb", RED), 0.8 * (1 - u)), Style=skia.Paint.kStroke_Style, StrokeWidth=(6 * (1 - u) + 1) * 4))
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
        elif kind == "flash":  # short light burst (grab spark, door unlock, door open)
            u = age / e.get("life", 0.5)
            if not 0 <= u <= 1:
                return
            p = self.P(e["x"], e["y"], 0)
            self._glow(c, (p[0], p[1]), (e.get("r", 60) + e.get("grow", 120) * u) * p[2], e.get("rgb", (255, 230, 150)), e.get("a", 0.7) * (1 - u))
        elif kind == "dust":
            u = age / 0.5
            if not 0 <= u <= 1:
                return
            p = self.P(e["x"], e["y"], 0)
            self._glow(c, (p[0], p[1]), (12 + 30 * u) * p[2], (200, 220, 230), 0.25 * (1 - u))

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
