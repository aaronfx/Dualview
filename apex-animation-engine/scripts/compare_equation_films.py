"""Compare the original balance animation with the upgraded autonomous equation film.

Motion analysis is computed from the native simulation (deterministic, exact), not estimated from pixels: duration,
how much of the film the character is actually moving vs idle, total distance travelled, and the transformation events.
A synchronised side-by-side contact sheet (original | upgraded) is built from the two MP4s at matched normalised times.

    PYTHONPATH=src python scripts/compare_equation_films.py \
        OLD.json OLD.mp4 NEW.json NEW.mp4 OUT_sheet.png
"""
from __future__ import annotations

import json
import math
import subprocess
import sys

import numpy as np
import skia

from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.render.video import ffmpeg_bin

IDLE_SPEED = 40.0   # u/s below which the character counts as standing still


def motion(path_json: str) -> dict:
    p = ProjectSpec.model_validate(json.load(open(path_json)))
    sc = p.scenes[0]
    res = SceneRuntime(p, sc.id).simulate()
    c = next(iter(res.controllers.values()))
    recs = c.records
    moving_t = travel = 0.0
    for a, b in zip(recs, recs[1:]):
        dt = b.t - a.t
        if dt <= 0:
            continue
        d = math.dist(a.pos, b.pos)
        travel += d
        if d / dt >= IDLE_SPEED:
            moving_t += dt
    dur = res.duration
    ev = [e.type for e in res.events]
    return {"duration": round(dur, 1), "moving_frac": round(moving_t / dur, 2), "idle_frac": round(1 - moving_t / dur, 2),
            "travel": round(travel), "throws": ev.count("throw"), "morphs": ev.count("morph"),
            "actions": len(sc.actions)}


def _grab(path: str, t: float, w: int, h: int) -> np.ndarray:
    out = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.uint8).reshape(h, w, 4)


def _dur(path: str) -> float:
    out = subprocess.run([ffmpeg_bin().replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return float(out)


def side_by_side(old_mp4: str, new_mp4: str, out_png: str, rows: int = 6, tw: int = 420):
    th = tw * 9 // 16
    od, nd = _dur(old_mp4), _dur(new_mp4)
    pad, head = 8, 60
    W = 2 * tw + 3 * pad
    H = head + rows * (th + 26) + pad
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.ColorSetRGB(12, 14, 18))
    font = skia.Font(None, 24)
    small = skia.Font(None, 15)
    gold = skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(255, 207, 58))
    white = skia.Paint(AntiAlias=True, Color=skia.ColorSetRGB(220, 235, 240))
    c.drawString("ORIGINAL (balance_final)", pad, 38, font, gold)
    c.drawString("UPGRADED (autonomous x+2=5)", tw + 2 * pad, 38, font, gold)
    for i in range(rows):
        u = i / (rows - 1)
        for col, (path, dur) in enumerate(((old_mp4, od), (new_mp4, nd))):
            img = _grab(path, u * dur * 0.98, tw, th)
            x = pad + col * (tw + pad)
            y = head + i * (th + 26)
            sk = skia.Image.fromarray(np.ascontiguousarray(img), colorType=skia.ColorType.kRGBA_8888_ColorType)
            c.drawImage(sk, x, y)
            c.drawString(f"{u * dur * 0.98:5.1f}s ({u:.0%})", x + 4, y + th + 18, small, white)
    surf.makeImageSnapshot().save(out_png, skia.kPNG)
    return out_png


if __name__ == "__main__":
    old_json, old_mp4, new_json, new_mp4, out_png = sys.argv[1:6]
    mo, mn = motion(old_json), motion(new_json)
    print(f"{'metric':14s} {'ORIGINAL':>12s} {'UPGRADED':>12s}")
    for k in ("duration", "idle_frac", "moving_frac", "travel", "actions", "throws", "morphs"):
        print(f"{k:14s} {str(mo[k]):>12s} {str(mn[k]):>12s}")
    print("sheet:", side_by_side(old_mp4, new_mp4, out_png))
