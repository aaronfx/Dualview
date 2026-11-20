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

FOV_K = 1.1  # camera distance = view_h * FOV_K  (vertical FOV ~ 49deg)
CYAN = (70, 236, 255)
RED = (255, 50, 62)
WHITE = (235, 252, 255)


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
    def render(self, fs: FrameState, cam: CameraState, red_flash: float = 0.0, fx: Optional[List[dict]] = None) -> np.ndarray:
        self._setup(cam)
        c = self.surface.getCanvas()
        c.clear(col((5, 6, 8)))
        c.save()
        c.translate(self.W / 2, self.H / 2)
        c.rotate(cam.roll)
        self._room(c, fs, red_flash)
        self._switches(c, fs)
        for pr in fs.props:
            self._prop(c, pr)
        for cid, pose in fs.poses.items():
            self._reflection(c, cid, pose)
            self._contact_shadow(c, cid, pose)
        for e in fx or []:
            self._effect(c, e, fs.t)
        for cid, pose in fs.poses.items():
            self._character(c, cid, pose)
        self._cutaway(c, red_flash)
        c.restore()
        self._post(c, red_flash)
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

    def _switches(self, c: skia.Canvas, fs: FrameState) -> None:
        g_ang = math.atan2(fs.gravity[1], fs.gravity[0])
        for sw in self.env.switches:
            glow = fs.switch_glow.get(sw.id, 0.6)
            x, z0, z1, top = sw.x, 20.0, 76.0, sw.height - 6
            fl = self.P(x, 0, 48)
            self._glow(c, (fl[0], fl[1]), (220 + 120 * min(glow, 2.5)) * fl[2], RED, 0.16 * min(glow, 2.5), squash=0.25)
            body = (34, 38, 46)
            faces = []
            if self.cam.cx > x + 30:
                faces.append([(x + 30, 0, z0), (x + 30, 0, z1), (x + 30, top, z1), (x + 30, top, z0)])
            if self.cam.cx < x - 30:
                faces.append([(x - 30, 0, z0), (x - 30, 0, z1), (x - 30, top, z1), (x - 30, top, z0)])
            if self.cam.cy > top:
                faces.append([(x - 30, top, z0), (x + 30, top, z0), (x + 30, top, z1), (x - 30, top, z1)])
            for f in faces:
                c.drawPath(self.poly(f), skia.Paint(AntiAlias=True, Color=col(mix(body, (0, 0, 0), 0.3))))
            front = self.poly([(x - 30, 0, z0), (x + 30, 0, z0), (x + 30, top, z0), (x - 30, top, z0)])
            c.drawPath(front, skia.Paint(AntiAlias=True, Color=col(body)))
            c.drawPath(front, skia.Paint(AntiAlias=True, Color=col((255, 80, 90), 0.5 * min(1, glow)), Style=skia.Paint.kStroke_Style, StrokeWidth=1.5))
            strip = self.poly([(x - 30, 2, z0 - 0.5), (x + 30, 2, z0 - 0.5), (x + 30, 6, z0 - 0.5), (x - 30, 6, z0 - 0.5)])
            c.drawPath(strip, skia.Paint(AntiAlias=True, Color=col(RED, 0.9 * min(1.2, glow))))
            # display: arrow showing the current gravity direction
            sc = self.P(x, top * 0.55, z0 - 0.5)
            k = sc[2]
            c.save()
            c.translate(sc[0], sc[1])
            c.scale(k, k)
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(Color=col((8, 14, 18))))
            c.drawRect(skia.Rect(-20, -14, 20, 14), skia.Paint(AntiAlias=True, Color=col(CYAN, 0.9), Style=skia.Paint.kStroke_Style, StrokeWidth=1.2))
            c.rotate(-math.degrees(g_ang) - 90)
            p = skia.Paint(AntiAlias=True, Color=col(CYAN), Style=skia.Paint.kStroke_Style, StrokeWidth=2.6, StrokeCap=skia.Paint.kRound_Cap)
            path = skia.Path()
            path.moveTo(0, -9); path.lineTo(0, 9); path.moveTo(-6, 3); path.lineTo(0, 9); path.lineTo(6, 3)
            c.drawPath(path, p)
            c.restore()
            # button dome
            pressed = clamp((glow - 0.7) / 2.0, 0, 1) * 4.0
            b = self.P(x, sw.height - 6 - pressed * 0.6, 34)
            kb = b[2]
            c.drawOval(skia.Rect(b[0] - 14 * kb, b[1] - 5.5 * kb, b[0] + 14 * kb, b[1] + 3.5 * kb), skia.Paint(AntiAlias=True, Color=col((40, 10, 12))))
            dome = skia.Path()
            dome.addArc(skia.Rect(b[0] - 11 * kb, b[1] - 10 * kb, b[0] + 11 * kb, b[1] + 6 * kb), 180, 180)
            dome.close()
            sh = skia.GradientShader.MakeRadial(skia.Point(b[0], b[1] - 5 * kb), 14 * kb, [col((255, 220, 220), min(1, 0.6 + glow * 0.4)), col(RED), col((140, 10, 20))], [0.0, 0.45, 1.0])
            c.drawPath(dome, skia.Paint(AntiAlias=True, Shader=sh))
            h = self.P(x, sw.height, 34)
            self._glow(c, (h[0], h[1]), (40 + 45 * min(glow, 2.5)) * h[2], (255, 70, 80), 0.42 * min(1.0, glow))

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

    def _cutaway(self, c: skia.Canvas, red: float) -> None:
        hw, rh, z = self.hw, self.rh, self.near - 0.5
        th, M = 46.0, 1600.0
        oc = mix((13, 15, 19), (40, 8, 11), red * 0.5)
        for f in ([(-hw - M, 0, z), (hw + M, 0, z), (hw + M, -M, z), (-hw - M, -M, z)],
                  [(hw, -M, z), (hw + M, -M, z), (hw + M, rh + M, z), (hw, rh + M, z)],
                  [(-hw - M, -M, z), (-hw, -M, z), (-hw, rh + M, z), (-hw - M, rh + M, z)],
                  [(-hw - M, rh, z), (hw + M, rh, z), (hw + M, rh + M, z), (-hw - M, rh + M, z)]):
            c.drawPath(self.poly(f), skia.Paint(AntiAlias=True, Color=col(oc)))
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

    def _character(self, c: skia.Canvas, cid: str, pose: Pose, alpha: float = 1.0, mirror_y: Optional[float] = None) -> None:
        rig, st, j, k, S0 = self._char_paths(cid, pose)
        if mirror_y is not None:
            S = lambda p: S0((p[0], 2 * mirror_y - p[1]))
        else:
            S = S0
        near, far, vis = hex_rgb(st.body_color), hex_rgb(st.far_color), hex_rgb(st.visor_color)
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
                          ["shoulder", "elbow_n", "wrist_n"], ["shoulder", "elbow_f", "wrist_f"]):
                for i, n in enumerate(chain):
                    q = S(j[n])
                    (path.lineTo if i else path.moveTo)(q[0], q[1])
            c.drawPath(path, glow)
        # far limbs
        stroke([j["shoulder"], j["elbow_f"], j["wrist_f"]], far, lw * 0.92)
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
        stroke([j["shoulder"], j["elbow_n"], j["wrist_n"]], near, lw * 0.98)
        self._hand(c, pose, "n", j, S, near, lw, alpha)

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

    def _reflection(self, c: skia.Canvas, cid: str, pose: Pose) -> None:
        hw = self.hw
        floor = self.poly([(-hw, 0, self.near), (hw, 0, self.near), (hw, 0, self.back), (-hw, 0, self.back)])
        c.save()
        c.clipPath(floor, doAntiAlias=True)
        self._character(c, cid, pose, alpha=0.16, mirror_y=0.0)
        c.restore()

    def _contact_shadow(self, c: skia.Canvas, cid: str, pose: Pose) -> None:
        px, py = pose.root
        d_floor = py
        if d_floor < 260:
            p = self.P(px, 0, 4)
            self._shadow(c, p, 70 * p[2], 0.55 * (1 - d_floor / 260), squash=0.22)
        d_wall = self.hw - px
        if d_wall < 260:
            p = self.P(self.hw - 0.5, py, 4)
            self._shadow(c, p, 70 * p[2], 0.55 * (1 - d_wall / 260), squash=1.0, sx=0.25)

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
            p = self.P(self.hw - 0.5, e["y"], 0)
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
