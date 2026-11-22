"""Worlds around open environments (cinematic upgrade): skies, distant layers with real parallax, weather, fog, a
corruption front, and styled structures (building roofs, rock cliffs, rope bridges, girders, rock pillars).

Everything here is drawn only; nothing collides. Layers are generated once from the environment's seed and recorded as
Skia pictures in world coordinates at their own depth. Every frame a layer is drawn through the camera's projection
for that depth (an affine map: scale `focal / (z + Fd)` about the camera), so near layers slide past and far ones
barely move, exactly as the characters' own perspective does.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import skia

from ..core.mathx import clamp, lerp, smoothstep


def _hex(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _c(rgb, a: float = 1.0) -> int:
    return skia.ColorSetARGB(int(clamp(a, 0, 1) * 255), int(clamp(rgb[0], 0, 255)), int(clamp(rgb[1], 0, 255)), int(clamp(rgb[2], 0, 255)))


def _mix(a, b, u: float):
    return (lerp(a[0], b[0], u), lerp(a[1], b[1], u), lerp(a[2], b[2], u))


# per-kind defaults: sky (top, middle, horizon), fog, sun position (far-sky units: x across, y height), weather tint
KINDS = {
    "city": dict(sky=["#04060f", "#140f33", "#3a1a55"], fog="#2a1640", sun=(900.0, 2200.0), sun_rgb=(220, 230, 255), sun_r=90.0,
                 accents=[(255, 70, 170), (70, 220, 255), (255, 190, 80), (160, 110, 255)]),
    "canyon": dict(sky=["#1c1a4a", "#b2456a", "#ffb35c"], fog="#c86a5a", sun=(-600.0, 300.0), sun_rgb=(255, 186, 96), sun_r=170.0,
                   accents=[(255, 170, 90)]),
    "tower": dict(sky=["#05080c", "#16242c", "#2c3f46"], fog="#1c2a30", sun=None, sun_rgb=(200, 220, 230), sun_r=0.0,
                  accents=[(255, 200, 60), (255, 60, 60)]),
    "void": dict(sky=["#000000", "#05030f", "#1a0a2a"], fog="#120820", sun=None, sun_rgb=(255, 255, 255), sun_r=0.0,
                 accents=[(70, 220, 255), (255, 70, 170)]),
    "summit": dict(sky=["#1d2a5c", "#d9789a", "#ffd18a"], fog="#f3c4b0", sun=(500.0, 380.0), sun_rgb=(255, 214, 140), sun_r=130.0,
                   accents=[(255, 220, 160)]),
}


class World:
    """Draws the world of one open environment for a renderer (uses its projection: `P`, `cam`, `Fd`, `focal`)."""

    def __init__(self, r, env):
        self.r, self.env = r, env
        self.bd = env.backdrop
        k = KINDS[self.bd.kind]
        self.kind = self.bd.kind
        sky = self.bd.sky or k["sky"]
        self.skyc = [_hex(s) for s in sky]
        if len(self.skyc) == 2:
            self.skyc.insert(1, _mix(self.skyc[0], self.skyc[1], 0.5))
        self.fog = _hex(self.bd.fog or k["fog"])
        self.sun = tuple(self.bd.sun) if self.bd.sun is not None else k["sun"]
        self.sun_rgb, self.sun_r = k["sun_rgb"], k["sun_r"]
        self.accents = k["accents"]
        self.bloom = {"city": 0.45, "canyon": 0.12, "tower": 0.4, "void": 0.55, "summit": 0.1}[self.kind]
        tops = [ob.center[1] + ob.size[1] / 2 for ob in env.obstacles if ob.kind == "platform"]
        self.level = max(tops) if tops else 300.0
        self.horizon = self.bd.horizon if self.bd.horizon is not None else self.level - 900.0
        self.rng = np.random.default_rng(self.bd.seed)
        self.layers: List[Tuple[float, skia.Picture]] = []  # (depth, picture), far first
        self._build()
        self._facades: Dict[str, skia.Picture] = {}

    # ------------------------------------------------------------ building the layers (once)
    def _rec(self, z: float, draw) -> None:
        rec = skia.PictureRecorder()
        c = rec.beginRecording(skia.Rect(-1e6, -1e6, 1e6, 1e6))
        draw(c)
        self.layers.append((z, rec.finishRecordingAsPicture()))

    def _span(self, z: float) -> Tuple[float, float]:
        hw = self.env.room.width / 2
        w = hw + 3000.0 + 1.7 * z
        return -w, w

    def _haze(self, rgb, z: float, far: float = 16000.0):
        return _mix(rgb, self.skyc[2], clamp(z / far, 0.0, 0.85))

    def _build(self) -> None:
        getattr(self, "_build_" + self.kind)()

    def _build_city(self) -> None:
        rng = self.rng
        for z, hmin, hmax, wmin, wmax, base, win, signs in ((14000, 900, 3200, 260, 700, (18, 14, 38), 0.05, 0),
                                                              (6500, 700, 2600, 200, 520, (12, 10, 26), 0.12, 6),
                                                              (2600, 200, 1300, 160, 380, (8, 8, 16), 0.18, 10)):
            x0, x1 = self._span(z)
            hz = self.horizon - 0.15 * z
            blds = []
            x = x0
            while x < x1:
                w = rng.uniform(wmin, wmax)
                h = rng.uniform(hmin, hmax) * (1.0 + 0.6 * rng.random() ** 4)
                blds.append((x, w, h, rng.integers(1 << 30)))
                x += w + rng.uniform(-0.1, 0.25) * w
            col_b = self._haze(base, z)
            def draw(c, blds=blds, hz=hz, col_b=col_b, z=z, win=win, signs=signs):
                body = skia.Paint(AntiAlias=True, Color=_c(col_b))
                for bx, bw, bh, s in blds:
                    rr = np.random.default_rng(int(s))
                    top = hz + bh
                    c.drawRect(skia.Rect(bx, -top, bx + bw, -(hz - 6000)), body)
                    step = rr.uniform(0.0, 1.0)
                    if step < 0.3:  # stepped crown
                        c.drawRect(skia.Rect(bx + bw * 0.2, -(top + bh * 0.08), bx + bw * 0.8, -top), body)
                    if step > 0.75:  # antenna with a red light
                        ax = bx + bw * rr.uniform(0.3, 0.7)
                        c.drawRect(skia.Rect(ax - 4, -(top + 260), ax + 4, -top), body)
                        c.drawCircle(ax, -(top + 265), 14, skia.Paint(AntiAlias=True, Color=_c((255, 60, 60), 0.9)))
                        c.drawCircle(ax, -(top + 265), 60, skia.Paint(AntiAlias=True, Color=_c((255, 60, 60), 0.12)))
                    # windows
                    wx, wy = max(26.0, bw / rr.integers(6, 14)), 46.0
                    nx, ny = int(bw / wx), int(min(bh, 3000) / wy)
                    lit = rr.random((ny, nx)) < win * rr.uniform(0.5, 2.0)
                    warm = rr.random() < 0.6
                    wc = (255, 196, 120) if warm else (150, 220, 255)
                    p = skia.Paint(AntiAlias=False, Color=_c(self._haze(wc, z, 30000), 0.85))
                    for j in range(ny):
                        for i in range(nx):
                            if lit[j, i]:
                                xx, yy = bx + (i + 0.25) * wx, top - (j + 1) * wy
                                c.drawRect(skia.Rect(xx, -yy, xx + wx * 0.5, -yy + wy * 0.45), p)
                # neon signs on some buildings
                for _ in range(signs):
                    bx, bw, bh, s = blds[int(rng.integers(len(blds)))]
                    acc = self.accents[int(rng.integers(len(self.accents)))]
                    sw, sh = rng.uniform(0.35, 0.8) * bw, rng.uniform(50, 140)
                    sx, sy = bx + rng.uniform(0.05, 0.3) * bw, hz + bh * rng.uniform(0.35, 0.85)
                    glow = skia.Paint(AntiAlias=True, Color=_c(acc, 0.22), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 40))
                    c.drawRect(skia.Rect(sx - 30, -(sy + sh + 30), sx + sw + 30, -(sy - 30)), glow)
                    c.drawRect(skia.Rect(sx, -(sy + sh), sx + sw, -sy), skia.Paint(AntiAlias=True, Color=_c(acc, 0.85)))
                    c.drawRect(skia.Rect(sx + 8, -(sy + sh - 8), sx + sw - 8, -(sy + 8)), skia.Paint(AntiAlias=True, Color=_c(_mix(acc, (255, 255, 255), 0.5), 0.9),
                                                                                              Style=skia.Paint.kStroke_Style, StrokeWidth=5))
            self._rec(z, draw)

    def _ridge(self, x0, x1, base, hmin, hmax, step, rng, mesa=False):
        pts = []
        x = x0
        h = rng.uniform(hmin, hmax)
        while x <= x1:
            if mesa:
                if rng.random() < 0.22 and pts:  # a new plateau, reached by a sloping scarp
                    h = rng.uniform(hmin, hmax)
                    x += step * rng.uniform(0.3, 0.7)
            else:
                h = clamp(h + rng.normal(0, (hmax - hmin) * 0.18), hmin, hmax)
            pts.append((x, base + h))
            x += step * rng.uniform(0.6, 1.4)
        return pts

    def _build_canyon(self) -> None:
        rng = self.rng
        for z, hmin, hmax, rgb, step, mesa in ((15000, 1800, 5200, (120, 60, 110), 900, True), (7000, 1200, 3600, (110, 50, 60), 500, True),
                                               (3000, 200, 1500, (70, 30, 32), 260, False)):
            x0, x1 = self._span(z)
            hz = self.horizon - 0.1 * z
            pts = self._ridge(x0, x1, hz, hmin, hmax, step, rng, mesa)
            colr = self._haze(rgb, z, 22000)
            def draw(c, pts=pts, hz=hz, colr=colr, z=z):
                path = skia.Path()
                path.moveTo(pts[0][0], -(hz - 8000))
                for x, y in pts:
                    path.lineTo(x, -y)
                path.lineTo(pts[-1][0], -(hz - 8000))
                path.close()
                top = max(p[1] for p in pts)
                sh = skia.GradientShader.MakeLinear([skia.Point(0, -top), skia.Point(0, -(hz - 600))],
                                                    [_c(_mix(colr, (255, 170, 110), 0.25)), _c(_mix(colr, (0, 0, 0), 0.35))])
                c.drawPath(path, skia.Paint(AntiAlias=True, Shader=sh))
                # strata: thin bands following the ridge
                rr = np.random.default_rng(int(z))
                for k in range(14):
                    dy = 60 + k * rr.uniform(70, 140)
                    sp = skia.Path()
                    sp.moveTo(pts[0][0], -(pts[0][1] - dy))
                    for x, y in pts[1:]:
                        sp.lineTo(x, -(y - dy))
                    c.drawPath(sp, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=6 + 8 * rr.random(),
                                              Color=_c(_mix(colr, (0, 0, 0), 0.3), 0.35)))
            self._rec(z, draw)
        # floating rocks hanging in the canyon air, far off
        z = 4200.0
        rocks = [(rng.uniform(*self._span(z)), self.level + rng.uniform(-600, 900), rng.uniform(40, 130), int(rng.integers(1 << 30)))
                 for _ in range(18)]
        def draw_rocks(c, rocks=rocks):
            for x, y, s, sd in rocks:
                rr = np.random.default_rng(sd)
                n = 9
                p = skia.Path()
                for i in range(n):  # a lumpy top, a long tapering underside
                    a = math.pi * i / (n - 1)
                    rad = s * rr.uniform(0.75, 1.15)
                    px, py = x - math.cos(a) * rad * 1.4, y + math.sin(a) * rad * 0.45
                    (p.lineTo if i else p.moveTo)(px, -py)
                for i in range(1, 6):
                    u = i / 6
                    p.lineTo(x + s * 1.4 * (1 - 2 * u) * (1 - u) + rr.uniform(-8, 8), -(y - s * 1.6 * math.sin(math.pi * u * 0.5) * (0.6 + 0.4 * u)))
                p.close()
                c.drawPath(p, skia.Paint(AntiAlias=True, Color=_c(self._haze((74, 36, 40), z, 12000))))
                c.drawLine(x - s * 1.3, -(y + 4), x + s * 1.3, -(y + 4), skia.Paint(AntiAlias=True, StrokeWidth=5, Color=_c((255, 170, 110), 0.45)))
        self._rec(z, draw_rocks)

    def _build_tower(self) -> None:
        rng = self.rng
        for z, rgb in ((12000, (30, 44, 52)), (5000, (16, 24, 30))):
            x0, x1 = self._span(z)
            hz = self.horizon - 0.1 * z
            towers = [(rng.uniform(x0, x1), rng.uniform(200, 600), rng.uniform(1500, 5000)) for _ in range(int((x1 - x0) / 1400))]
            colr = self._haze(rgb, z, 20000)
            def draw(c, towers=towers, hz=hz, colr=colr):
                for x, w, h in towers:
                    c.drawRect(skia.Rect(x, -(hz + h), x + w, -(hz - 8000)), skia.Paint(AntiAlias=True, Color=_c(colr)))
                    c.drawCircle(x + w / 2, -(hz + h + 40), 22, skia.Paint(AntiAlias=True, Color=_c((255, 60, 60), 0.8)))
            self._rec(z, draw)
        z = 1500.0  # a steel lattice: the tower's own scaffolding behind the action
        x0, x1 = self._span(z)
        def draw_lattice(c):
            steel = skia.Paint(AntiAlias=True, Color=_c(self._haze((40, 52, 60), z, 4000), 0.7), StrokeWidth=26, Style=skia.Paint.kStroke_Style)
            thin = skia.Paint(AntiAlias=True, Color=_c(self._haze((34, 44, 50), z, 4000), 0.5), StrokeWidth=12, Style=skia.Paint.kStroke_Style)
            bay = 520.0
            ybot, ytop = self.level - 4000, self.level + 4000
            x = x0
            while x < x1:
                c.drawLine(x, -ybot, x, -ytop, steel)
                y = ybot
                while y < ytop:
                    c.drawLine(x, -y, x + bay, -(y + bay), thin)
                    c.drawLine(x + bay, -y, x, -(y + bay), thin)
                    c.drawLine(x, -y, x + bay, -y, steel)
                    y += bay
                x += bay
        self._rec(z, draw_lattice)

    def _build_void(self) -> None:
        rng = self.rng
        for z, n, s in ((9000, 50, 260), (4000, 40, 160), (1600, 24, 90)):
            x0, x1 = self._span(z)
            cubes = [(rng.uniform(x0, x1), self.level + rng.uniform(-2500, 2500), rng.uniform(0.5, 1.5) * s, rng.uniform(0, 1)) for _ in range(n)]
            accs = self.accents
            def draw(c, cubes=cubes, z=z):
                for x, y, sz, a in cubes:
                    acc = accs[int(a * len(accs)) % len(accs)]
                    p = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=max(4.0, sz * 0.05),
                                   Color=_c(self._haze(acc, z, 14000), 0.55))
                    c.drawRect(skia.Rect(x, -(y + sz), x + sz, -y), p)
                    o = sz * 0.35
                    c.drawRect(skia.Rect(x + o, -(y + sz + o), x + sz + o, -(y + o)), p)
                    for dx, dy in ((0, 0), (sz, 0), (0, sz), (sz, sz)):
                        c.drawLine(x + dx, -(y + dy), x + dx + o, -(y + dy + o), p)
            self._rec(z, draw)

    def _build_summit(self) -> None:
        rng = self.rng
        for z, hmin, hmax, rgb, step in ((16000, 1200, 4200, (110, 100, 150), 1500), (7000, 600, 2600, (80, 70, 110), 700)):
            x0, x1 = self._span(z)
            hz = self.horizon - 0.1 * z
            peaks = []
            x = x0
            while x < x1:
                peaks.append((x, rng.uniform(hmin, hmax), rng.uniform(0.6, 1.4) * step))
                x += step * rng.uniform(0.5, 1.1)
            colr = self._haze(rgb, z, 26000)
            def draw(c, peaks=peaks, hz=hz, colr=colr):
                for x, h, w in peaks:
                    p = skia.Path()
                    p.moveTo(x - w, -(hz - 6000))
                    p.lineTo(x - w, -hz)
                    p.lineTo(x, -(hz + h))
                    p.lineTo(x + w, -hz)
                    p.lineTo(x + w, -(hz - 6000))
                    p.close()
                    c.drawPath(p, skia.Paint(AntiAlias=True, Color=_c(colr)))
                    snow = skia.Path()  # sunlit snow cap
                    snow.moveTo(x, -(hz + h))
                    snow.lineTo(x + w * 0.28, -(hz + h * 0.72))
                    snow.lineTo(x + w * 0.1, -(hz + h * 0.76))
                    snow.lineTo(x - w * 0.05, -(hz + h * 0.7))
                    snow.lineTo(x - w * 0.22, -(hz + h * 0.74))
                    snow.close()
                    c.drawPath(snow, skia.Paint(AntiAlias=True, Color=_c(_mix(colr, (255, 220, 200), 0.6))))
            self._rec(z, draw)
        # a sea of cloud below the summit, in bands
        for z, dy, rgb in ((5000, -700, (240, 180, 190)), (2200, -500, (250, 205, 200)), (900, -380, (255, 225, 210))):
            x0, x1 = self._span(z)
            blobs = [(rng.uniform(x0, x1), self.level + dy - 0.05 * z + rng.uniform(-120, 80), rng.uniform(300, 900)) for _ in range(int((x1 - x0) / 300))]
            def draw(c, blobs=blobs, rgb=rgb, z=z):
                p = skia.Paint(AntiAlias=True, Color=_c(rgb, 0.85), MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 60))
                for x, y, s in blobs:
                    c.drawOval(skia.Rect(x - s, -(y + s * 0.35), x + s, -(y - s * 0.35)), p)
                c.drawRect(skia.Rect(-1e5, -(min(b[1] for b in blobs) - 10), 1e5, 1e5), skia.Paint(Color=_c(rgb, 0.95)))
            self._rec(z, draw)

    # ------------------------------------------------------------ per frame
    def sky(self, c: skia.Canvas, t: float) -> None:
        """Screen-space sky (drawn before the camera transform), with the sun or moon, stars and lightning."""
        W, H, cam = self.r.W, self.r.H, self.r.cam
        top, mid, hor = self.skyc
        hy = self._screen_y(self.horizon - 600.0, 9000.0)  # the horizon glow sits behind the far layers
        sh = skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(0, max(hy, 2.0))], [_c(top), _c(mid), _c(hor)], [0.0, 0.55, 1.0])
        c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=sh))
        if hy < H:
            c.drawRect(skia.Rect(0, hy, W, H), skia.Paint(Color=_c(hor)))
        if self.kind in ("city", "void", "tower"):  # stars (fixed to the sky, a little parallax)
            rr = np.random.default_rng(self.bd.seed + 99)
            n = 160 if self.kind != "tower" else 30
            p = skia.Paint(AntiAlias=True)
            for _ in range(n):
                u, v, b = rr.random(), rr.random(), rr.random()
                x = (u * W * 1.4 - cam.cx * 0.004 * H / 720.0) % (W * 1.4) - W * 0.2
                y = v * hy * 0.8
                tw = 0.5 + 0.5 * math.sin(t * (1.0 + 3 * b) + u * 50)
                p.setColor(_c((230, 235, 255), (0.25 + 0.6 * b) * (0.6 + 0.4 * tw)))
                c.drawCircle(x, y, (0.6 + 1.4 * b) * H / 720.0, p)
        if self.sun is not None and self.sun_r > 0:
            sx = W / 2 + (self.sun[0] - cam.cx * 0.02) * H / 1080.0
            sy = hy - self.sun[1] * H / 1080.0 + (cam.cy - self.level) * 0.01
            r = self.sun_r * H / 1080.0
            for rad, a in ((r * 7, 0.35), (r * 2.4, 0.5), (r * 1.3, 0.6)):  # the glow around it (bright worlds have little bloom)
                halo = skia.GradientShader.MakeRadial(skia.Point(sx, sy), rad, [_c(self.sun_rgb, a), _c(self.sun_rgb, 0.0)])
                c.drawCircle(sx, sy, rad, skia.Paint(AntiAlias=True, Shader=halo, BlendMode=skia.BlendMode.kPlus))
            c.drawCircle(sx, sy, r, skia.Paint(AntiAlias=True, Color=_c(_mix(self.sun_rgb, (255, 255, 255), 0.25 if self.kind != "city" else 0.5), 0.97)))
            if self.kind == "city":  # moon craters
                for dx, dy, rr_ in ((-0.3, -0.2, 0.22), (0.25, 0.15, 0.15), (0.05, 0.4, 0.12)):
                    c.drawCircle(sx + dx * r, sy + dy * r, rr_ * r, skia.Paint(AntiAlias=True, Color=_c((190, 198, 225), 0.55)))
        if self.kind == "void":  # a retro grid on the horizon
            gp = skia.Paint(AntiAlias=True, StrokeWidth=1.5 * H / 720.0, Color=_c((255, 70, 170), 0.35))
            base = min(H * 1.2, hy + 10)
            for k in range(1, 14):
                yy = base + (H - base) * (k / 13.0) ** 2.2
                c.drawLine(0, yy, W, yy, gp)
            for k in range(-20, 21):
                c.drawLine(W / 2 + k * 18 * H / 720.0, base, W / 2 + k * 260 * H / 720.0 - cam.cx * 0.05, H, gp)
        if self.bd.lightning:
            f = self._flash(t)
            if f > 0:
                c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Color=_c((200, 220, 255), 0.55 * f), BlendMode=skia.BlendMode.kPlus))
                rr = np.random.default_rng(int(t * 3))
                x = rr.uniform(0.15, 0.85) * W
                y = 0.0
                path = skia.Path()
                path.moveTo(x, y)
                while y < hy:
                    x += rr.normal(0, 24) * H / 720.0
                    y += rr.uniform(20, 50) * H / 720.0
                    path.lineTo(x, y)
                c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3 * H / 720.0, Color=_c((235, 240, 255), f)))

    def _flash(self, t: float) -> float:
        """Deterministic lightning: a strike every few seconds, each a double flicker."""
        period = 4.3
        k = math.floor(t / period)
        rr = np.random.default_rng(int(k) + self.bd.seed * 7919)
        t0 = k * period + rr.uniform(0.2, 2.5)
        u = t - t0
        if 0 <= u < 0.35:
            return max(0.0, 1 - u / 0.12) + (0.6 * max(0.0, 1 - abs(u - 0.22) / 0.06))
        return 0.0

    def _screen_y(self, y: float, z: float) -> float:
        k = self.r.focal / max(z + self.r.Fd, 20.0)
        return self.r.H / 2 - (y - self.r.cam.cy) * k

    def backdrop(self, c: skia.Canvas, t: float) -> None:
        """The far layers through the camera (call inside the renderer's centred camera transform)."""
        cam = self.r.cam
        for z, pic in self.layers:
            k = self.r.focal / max(z + self.r.Fd, 20.0)
            drift = 0.0
            if self.kind == "void":
                drift = 25.0 * t * (2000.0 / (z + 500.0))
            c.save()
            c.translate(-(cam.cx - drift) * k, cam.cy * k)
            c.scale(k, k)
            c.drawPicture(pic)
            c.restore()
        # fog rising from the depths (over the far world, under the action)
        y0 = self.r.P(0, self.level - 250.0, 400.0)[1]
        y1 = self.r.P(0, self.level - 1100.0, 400.0)[1]
        sh = skia.GradientShader.MakeLinear([skia.Point(0, y0), skia.Point(0, max(y1, y0 + 1))], [_c(self.fog, 0.0), _c(self.fog, 0.92)])
        c.drawRect(skia.Rect(-1e4, y0, 1e4, 1e4), skia.Paint(Shader=sh))
        if self.kind == "city":  # a soft light haze across the horizon
            hy = self.r.P(0, self.horizon + 400.0, 6000.0)[1]
            sh = skia.GradientShader.MakeRadial(skia.Point(0, hy), self.r.W, [_c(self.skyc[2], 0.25), _c(self.skyc[2], 0.0)])
            c.drawRect(skia.Rect(-1e4, -1e4, 1e4, 1e4), skia.Paint(Shader=sh, BlendMode=skia.BlendMode.kScreen))

    def weather(self, c: skia.Canvas, t: float, front: bool) -> None:
        """Rain, embers, snow, motes or data, at several depths (deterministic in time; no state)."""
        kind = self.bd.weather
        if kind == "none" or self.bd.weather_amount <= 0:
            return
        cam = self.r.cam
        rr = np.random.default_rng(self.bd.seed + (1 if front else 2))
        n = int((70 if front else 160) * self.bd.weather_amount)
        H = self.r.H
        for _ in range(n):
            u, v, w = rr.random(), rr.random(), rr.random()
            z = (-80 + 70 * w) if front else (60 + 2400 * w * w)
            k = self.r.focal / max(z + self.r.Fd, 20.0)
            spanx = self.r.W / k * 1.2
            spany = H / k * 1.3
            if kind == "rain":
                vy, vx, ln, rgb, a, wd = 1500.0, -260.0, 46.0, (180, 200, 235), 0.32, 1.4
            elif kind == "snow":
                vy, vx, ln, rgb, a, wd = 90.0, 30.0, 0.0, (240, 245, 255), 0.7, 3.0
            elif kind == "embers":
                vy, vx, ln, rgb, a, wd = -70.0, 40.0, 6.0, (255, 150, 70), 0.8, 2.6
            elif kind == "data":
                vy, vx, ln, rgb, a, wd = 420.0, 0.0, 60.0, self.accents[int(v * 9) % len(self.accents)], 0.4, 2.0
            else:  # motes
                vy, vx, ln, rgb, a, wd = -18.0, 14.0, 0.0, (255, 236, 200), 0.55, 2.2
            sway = math.sin(t * 0.9 + u * 40) * (30.0 if kind in ("snow", "motes", "embers") else 0.0)
            x = cam.cx + ((u * spanx + vx * t + sway - cam.cx) % spanx) - spanx / 2
            y = cam.cy + ((v * spany - vy * t - cam.cy) % spany) - spany / 2
            a3 = self.r.P(x, y, z)
            if ln > 0:
                b3 = self.r.P(x - vx * ln / max(abs(vy), 1.0), y + ln * (1 if vy > 0 else -1), z)
                c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, StrokeWidth=max(0.8, wd * a3[2]), Color=_c(rgb, a * (0.5 + 0.5 * w))))
            else:
                c.drawCircle(a3[0], a3[1], max(0.8, wd * a3[2]), skia.Paint(AntiAlias=True, Color=_c(rgb, a * (0.5 + 0.5 * w))))

    def glitch(self, c: skia.Canvas, t: float) -> None:
        """The corruption front: everything behind it is eaten by red static."""
        g = self.bd.glitch
        if g is None or t < g.start:
            return
        xg = g.x0 + g.direction * g.speed * (t - g.start)
        rgb = _hex(g.color)
        r = self.r
        rr = np.random.default_rng(int(t * 30))
        a0, a1 = r.P(xg, r.cam.cy, 0.0), r.P(xg, r.cam.cy, 600.0)
        sx = a0[0]
        far = -1e4 if g.direction > 0 else 1e4
        rect = skia.Rect(min(far, sx), -1e4, max(far, sx), 1e4)
        c.drawRect(rect, skia.Paint(Color=_c(_mix(rgb, (0, 0, 0), 0.82), 0.92)))
        for _ in range(90):  # torn blocks and scanlines
            h = rr.uniform(2, 26) * r.H / 720.0
            y = rr.uniform(-r.H / 2, r.H / 2)
            w = rr.uniform(20, 400) * r.H / 720.0
            x = sx - g.direction * rr.uniform(-60, 700) * r.H / 720.0
            c.drawRect(skia.Rect(x - w / 2, y, x + w / 2, y + h), skia.Paint(Color=_c(_mix(rgb, (255, 255, 255), rr.random() * 0.4), rr.uniform(0.1, 0.6))))
        edge = skia.Paint(AntiAlias=True, Color=_c(rgb, 0.85), StrokeWidth=6 * r.H / 720.0, MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 14))
        c.drawLine(sx, -1e4, sx, 1e4, edge)
        c.drawLine(sx, -1e4, sx, 1e4, skia.Paint(AntiAlias=True, Color=_c((255, 235, 240), 0.9), StrokeWidth=2 * r.H / 720.0))

    # ------------------------------------------------------------ styled structures
    def structure(self, c: skia.Canvas, ob, back: bool) -> bool:
        """Draw a styled platform; False if it is not styled (the renderer draws its default slab)."""
        st = ob.style
        if st is None or st == "slab":
            return False
        r = self.r
        hx, hy = ob.size[0] / 2, ob.size[1] / 2
        x0, x1, y0, y1 = ob.center[0] - hx, ob.center[0] + hx, ob.center[1] - hy, ob.center[1] + hy
        nr, bk = r.near + 2, r.back
        col_ = _hex(ob.color) if ob.color else None
        if back:
            if st == "roof":
                self._building(c, ob, x0, x1, y1, nr, bk)
            elif st in ("rock", "pillar"):
                self._cliff(c, ob, x0, x1, y0, y1, nr, bk, st == "pillar")
            elif st == "girder":
                self._girder(c, ob, x0, x1, y0, y1, nr, bk)
            elif st == "bridge":
                self._bridge(c, ob, x0, x1, y0, y1, nr, bk)
        else:  # the near edge, drawn over the characters' feet
            edge = {"roof": (150, 160, 180), "rock": (230, 170, 120), "pillar": (230, 170, 120), "girder": (255, 200, 60),
                    "bridge": (200, 160, 110)}[st]
            if col_ is not None and st == "bridge":
                edge = col_
            a3, b3 = r.P(x0, y1, nr), r.P(x1, y1, nr)
            c.drawLine(a3[0], a3[1], b3[0], b3[1], skia.Paint(AntiAlias=True, Color=_c(edge, 0.9), StrokeWidth=max(1.2, 2.4 * a3[2])))
        return True

    def _face(self, c, pts, rgb, a=1.0, shader=None):
        p = skia.Paint(AntiAlias=True, Color=_c(rgb, a))
        if shader is not None:
            p.setShader(shader)
        c.drawPath(self.r.poly(pts), p)

    def _building(self, c, ob, x0, x1, top, nr, bk) -> None:
        """A rooftop: the roof surface, a parapet, and the facade falling away into the depths with lit windows."""
        r = self.r
        depth = 2600.0
        cam = r.cam
        roof = (54, 58, 72)
        self._face(c, [(x0, top, nr), (x1, top, nr), (x1, top, bk), (x0, top, bk)], roof)
        # side walls visible from the camera
        if cam.cx > x1:
            self._face(c, [(x1, top, nr), (x1, top - depth, nr), (x1, top - depth, bk), (x1, top, bk)], (16, 16, 28))
        if cam.cx < x0:
            self._face(c, [(x0, top, nr), (x0, top - depth, nr), (x0, top - depth, bk), (x0, top, bk)], (16, 16, 28))
        a, b = r.P(x0, top, nr), r.P(x0, top - depth, nr)
        sh = skia.GradientShader.MakeLinear([skia.Point(0, a[1]), skia.Point(0, b[1])], [_c((30, 28, 48)), _c((8, 8, 14))])
        self._face(c, [(x0, top, nr), (x1, top, nr), (x1, top - depth, nr), (x0, top - depth, nr)], (20, 20, 34), shader=sh)
        # windows on the facade (seeded by the building)
        rr = np.random.default_rng(abs(hash(ob.id)) % (1 << 30))
        wx, wy = 70.0, 90.0
        nx = max(1, int((x1 - x0 - 40) / wx))
        warm = (255, 200, 130) if rr.random() < 0.5 else (150, 220, 255)
        for j in range(1, 20):
            y = top - 60 - j * wy
            for i in range(nx):
                if rr.random() < 0.35:
                    xx = x0 + 30 + i * wx
                    pa, pb = r.P(xx, y, nr - 0.5), r.P(xx + 34, y - 46, nr - 0.5)
                    fade = clamp(1.0 - j / 18.0, 0.15, 1.0)
                    c.drawRect(skia.Rect(pa[0], pa[1], pb[0], pb[1]), skia.Paint(Color=_c(warm, 0.75 * fade)))
        # parapet: a low wall along the back and a lip at the front edge
        self._face(c, [(x0, top, bk - 30), (x1, top, bk - 30), (x1, top + 40, bk - 30), (x0, top + 40, bk - 30)], (70, 74, 92))
        # rooftop clutter at the back: vents and an antenna
        for k in range(int(rr.integers(1, 3))):
            vx = x0 + rr.uniform(0.15, 0.8) * (x1 - x0)
            self._box(c, vx, vx + rr.uniform(60, 130), top, top + rr.uniform(40, 90), bk - 160, bk - 60, (64, 68, 84))

    def _box(self, c, x0, x1, y0, y1, z0, z1, rgb) -> None:
        self._face(c, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], _mix(rgb, (255, 255, 255), 0.12))
        self._face(c, [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], rgb)

    def _cliff(self, c, ob, x0, x1, y0, top, nr, bk, pillar: bool) -> None:
        """A rock ledge: sunlit top, a jagged cliff face falling away (a pillar keeps its own height), strata."""
        r = self.r
        rr = np.random.default_rng(abs(hash(ob.id)) % (1 << 30))
        bottom = y0 if pillar else top - 2200.0
        self._face(c, [(x0, top, nr), (x1, top, nr), (x1, top, bk), (x0, top, bk)], (176, 112, 84))
        # jagged outline of the front face
        pts = [(x0, top, nr)]
        steps = 12
        for k in range(1, steps + 1):  # down the right side, inward
            u = k / steps
            pts.append((x1 - (0 if pillar else u * u * 0.35 * (x1 - x0)) + rr.uniform(-14, 14), top - u * (top - bottom), nr))
        for k in range(steps, 0, -1):
            u = k / steps
            pts.append((x0 + (0 if pillar else u * u * 0.35 * (x1 - x0)) + rr.uniform(-14, 14), top - u * (top - bottom), nr))
        a, b = r.P(x0, top, nr), r.P(x0, bottom, nr)
        sh = skia.GradientShader.MakeLinear([skia.Point(0, a[1]), skia.Point(0, b[1])], [_c((120, 64, 52)), _c((30, 14, 18))])
        self._face(c, pts, (90, 44, 40), shader=sh)
        # strata lines across the face
        for k in range(1, 9):
            y = top - k * (top - bottom) / 9.0 * rr.uniform(0.8, 1.1)
            pa, pb = r.P(x0 + 10, y, nr - 0.5), r.P(x1 - 10, y + rr.uniform(-20, 20), nr - 0.5)
            c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, StrokeWidth=max(1.0, 3 * pa[2]), Color=_c((60, 26, 24), 0.6)))
        # a lit lip along the top edge
        pa, pb = r.P(x0, top - 6, nr - 0.5), r.P(x1, top - 6, nr - 0.5)
        c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, StrokeWidth=max(1.5, 8 * pa[2]), Color=_c((210, 140, 100), 0.9)))

    def _girder(self, c, ob, x0, x1, y0, top, nr, bk) -> None:
        r = self.r
        self._face(c, [(x0, top, nr), (x1, top, nr), (x1, top, bk), (x0, top, bk)], (70, 80, 88))
        self._face(c, [(x0, y0, nr), (x1, y0, nr), (x1, top, nr), (x0, top, nr)], (40, 48, 54))
        n = max(2, int((x1 - x0) / 70))
        for k in range(n):  # lightening holes in the web
            xx = x0 + (k + 0.5) * (x1 - x0) / n
            p = r.P(xx, (y0 + top) / 2, nr - 0.5)
            c.drawCircle(p[0], p[1], max(1.0, 0.28 * (top - y0) * p[2]), skia.Paint(AntiAlias=True, Color=_c((14, 18, 22))))
        pa, pb = r.P(x0, top - 4, nr - 0.6), r.P(x1, top - 4, nr - 0.6)
        c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, StrokeWidth=max(1.5, 6 * pa[2]), Color=_c((255, 196, 40), 0.85)))

    def _bridge(self, c, ob, x0, x1, y0, top, nr, bk) -> None:
        """Planks on two ropes, with posts at the ends."""
        r = self.r
        rgb = _hex(ob.color) if ob.color else (150, 104, 70)
        n = max(3, int((x1 - x0) / 34))
        w = (x1 - x0) / n
        for k in range(n):
            xa = x0 + k * w + 2
            shade = 0.85 + 0.15 * ((k * 37) % 5) / 5
            self._face(c, [(xa, top, nr + 20), (xa + w - 4, top, nr + 20), (xa + w - 4, top, bk - 40), (xa, top, bk - 40)], _mix((0, 0, 0), rgb, shade))
            self._face(c, [(xa, y0, nr + 20), (xa + w - 4, y0, nr + 20), (xa + w - 4, top, nr + 20), (xa, top, nr + 20)], _mix((0, 0, 0), rgb, 0.6 * shade))
        rope = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, Color=_c((220, 190, 140), 0.9))
        for z in (nr + 20, bk - 40):
            path = skia.Path()
            for k in range(21):
                u = k / 20
                x = lerp(x0, x1, u)
                y = top + 110 - 40 * math.sin(math.pi * u)
                p = r.P(x, y, z)
                (path.lineTo if k else path.moveTo)(p[0], p[1])
            rope.setStrokeWidth(max(1.0, 3.0 * r.P(x0, top, z)[2]))
            c.drawPath(path, rope)
            for x in (x0, x1):
                pa, pb = r.P(x, top, z), r.P(x, top + 120, z)
                c.drawLine(pa[0], pa[1], pb[0], pb[1], skia.Paint(AntiAlias=True, StrokeWidth=max(2.0, 8 * pa[2]), Color=_c((90, 60, 40))))

    # ------------------------------------------------------------ light on the characters' ground
    def contact_shadow_y(self, x: float, y: float) -> Optional[float]:
        """The top under (x, y) that a character's shadow falls on, if one is close below."""
        best = None
        for ob in self.env.obstacles:
            if ob.kind != "platform" or ob.id in getattr(self.r, "_collapsed", ()):
                continue
            hx = ob.size[0] / 2
            top = ob.center[1] + ob.size[1] / 2
            if ob.center[0] - hx <= x <= ob.center[0] + hx and 0 <= y - top < 260 and (best is None or top > best):
                best = top
        return best
