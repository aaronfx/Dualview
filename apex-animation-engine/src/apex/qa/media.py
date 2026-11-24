"""Media verification and review artefacts: full-decode check, timestamped contact sheet, diagnostics chart."""
from __future__ import annotations

import json
import math
import subprocess
from typing import Dict, List, Optional, Sequence

import numpy as np
import skia

from ..render.video import ffmpeg_bin


def decode_check(path: str) -> Dict[str, object]:
    """Decode every frame of the file; report decoder errors and the number of frames actually decoded."""
    p = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", path, "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "64x36", "-"],
                       capture_output=True)
    frames = len(p.stdout) // (64 * 36)
    errors = p.stderr.decode(errors="replace").strip()
    a = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", path, "-map", "0:a:0", "-f", "null", "-"], capture_output=True)
    return {"video_frames_decoded": frames, "video_errors": errors, "audio_errors": a.stderr.decode(errors="replace").strip(),
            "ok": p.returncode == 0 and a.returncode == 0 and not errors}


def _grab(path: str, t: float, w: int, h: int) -> np.ndarray:
    out = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{t:.4f}", "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgba",
                          "-s", f"{w}x{h}", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(h, w, 4)


# events worth looking at frame by frame (impacts, hand-overs, decisive story beats)
KEY_REVIEW_EVENTS = ("knockdown", "hit", "blocked", "throw", "place", "pick_up", "carried_out", "disarm", "break",
                     "creature_break", "morph", "ledge_catch", "pulled_up", "collapse", "portal_exit", "orb_jump",
                     "switch_activated", "settled", "vault", "flip", "exit_reached")


def review_frame_times(duration: float, key_times: Sequence[float], fps: int, base_dt: float = 1.0,
                       dense_window: float = 0.4, dense_step_frames: int = 2):
    """Frames for a review contact sheet: a one-second grid over the whole film, plus high-frequency frames (every
    `dense_step_frames` frames) in a +/- `dense_window` s window around each key event time. Returns (times, is_dense)
    with times sorted and de-duplicated; is_dense[i] marks a frame added for an event rather than the base grid."""
    frame = 1.0 / fps
    grid = {round(x * base_dt, 4) for x in range(int(duration / base_dt) + 1) if x * base_dt < duration}
    dense = set()
    for kt in key_times:
        k = kt - dense_window
        while k <= kt + dense_window + 1e-9:
            if 0.0 <= k < duration:
                dense.add(round(k, 4))
            k += dense_step_frames * frame
    allt = sorted(grid | dense)
    return allt, [t in dense and t not in grid for t in allt]


def contact_sheet(path: str, out_png: str, times: Sequence[float], labels: Optional[Sequence[str]] = None, cols: int = 5,
                  thumb_w: int = 384, title: str = "") -> str:
    thumb_h = thumb_w * 9 // 16
    rows = int(math.ceil(len(times) / cols))
    pad, head = 6, 44
    W, H = cols * (thumb_w + pad) + pad, rows * (thumb_h + pad + 22) + pad + head
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.ColorSetRGB(11, 13, 16))
    font = skia.Font(None, 22)
    small = skia.Font(None, 15)
    c.drawString(title, pad, 30, font, skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(255, 207, 58)))
    for i, t in enumerate(times):
        img = _grab(path, t, thumb_w, thumb_h)
        x = pad + (i % cols) * (thumb_w + pad)
        y = head + (i // cols) * (thumb_h + pad + 22)
        sk = skia.Image.fromarray(np.ascontiguousarray(img), colorType=skia.ColorType.kRGBA_8888_ColorType)
        c.drawImage(sk, x, y)
        lab = f"{t:6.2f}s" + (f"  {labels[i]}" if labels else "")
        c.drawString(lab, x + 4, y + thumb_h + 17, small, skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(220, 240, 245)))
    surf.makeImageSnapshot().save(out_png, skia.kPNG)
    return out_png


def diagnostics_chart(diag: List[dict], out_png: str, shots: Sequence[tuple], title: str = "") -> str:
    """Stacked time-series chart (pure Skia, no plotting dependency)."""
    series = [("root speed (u/s)", "speed", (255, 207, 58)), ("pelvis height above support", "height", (95, 246, 255)),
              ("body tilt vs. support (deg)", "tilt", (255, 120, 120)), ("gravity angle (deg)", "gravity_deg", (180, 160, 255)),
              ("scarf tip speed (u/s)", "scarf_tip_speed", (25, 220, 198)), ("camera roll (deg)", "roll", (200, 200, 200))]
    W, rowh, left, top = 1600, 120, 230, 50
    H = top + rowh * (len(series) + 1) + 30
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.ColorSetRGB(11, 13, 16))
    font, small = skia.Font(None, 20), skia.Font(None, 14)
    white = skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(225, 235, 240))
    c.drawString(title, 12, 30, font, skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(255, 207, 58)))
    T = [d["t"] for d in diag]
    t0, t1 = T[0], T[-1]
    X = lambda t: left + (t - t0) / max(1e-6, t1 - t0) * (W - left - 20)
    for sid, a, b in shots:  # shot bands
        c.drawLine(X(a), top, X(a), H - 30, skia.Paint(Color=skia.ColorSetARGB(90, 255, 255, 255)))
        c.drawString(sid, X(a) + 3, top - 6, small, white)
    states = ["idle", "loco", "turn", "press", "point", "airborne", "landing"]
    pal = {"idle": (90, 90, 100), "loco": (60, 140, 200), "turn": (150, 150, 60), "press": (220, 80, 80), "point": (80, 200, 120),
           "airborne": (240, 160, 40), "landing": (200, 90, 200)}
    y = top
    c.drawString("state", 12, y + 18, small, white)
    for i in range(len(diag) - 1):
        r, g, b = pal.get(diag[i]["state"], (120, 120, 120))
        c.drawRect(skia.Rect(X(T[i]), y + 4, X(T[i + 1]) + 1, y + 28), skia.Paint(Color=skia.ColorSetRGB(r, g, b)))
    for k, st in enumerate(states):
        r, g, b = pal[st]
        c.drawRect(skia.Rect(left + k * 110, y + 34, left + k * 110 + 12, y + 46), skia.Paint(Color=skia.ColorSetRGB(r, g, b)))
        c.drawString(st, left + k * 110 + 16, y + 45, small, white)
    for i, (name, key, rgb) in enumerate(series):
        y0 = top + rowh * (i + 1)
        vals = [d.get(key, 0.0) or 0.0 for d in diag]
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-6:
            hi = lo + 1.0
        c.drawString(name, 12, y0 + 20, small, white)
        c.drawString(f"{hi:.0f}", 12, y0 + 40, small, white)
        c.drawString(f"{lo:.0f}", 12, y0 + rowh - 16, small, white)
        c.drawLine(left, y0 + rowh - 12, W - 20, y0 + rowh - 12, skia.Paint(Color=skia.ColorSetARGB(60, 255, 255, 255)))
        path = skia.Path()
        for j, (t, v) in enumerate(zip(T, vals)):
            py = y0 + rowh - 12 - (v - lo) / (hi - lo) * (rowh - 30)
            (path.lineTo if j else path.moveTo)(X(t), py)
        c.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(*rgb), Style=skia.Paint.kStroke_Style, StrokeWidth=2))
    surf.makeImageSnapshot().save(out_png, skia.kPNG)
    return out_png
