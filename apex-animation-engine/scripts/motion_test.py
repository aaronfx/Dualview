"""Motion test: render the same action window from two engine versions side by side with a pose timeline, contact
points and motion diagnostics (1920x1080 MP4).

Two phases, so the baseline can be rendered by an older engine checkout:

  # 1) export each version (run with that version's `src` on PYTHONPATH)
  PYTHONPATH=<old>/src python scripts/motion_test.py export examples/scene.json out/base  --event lost_support --pre 0.45
  PYTHONPATH=src       python scripts/motion_test.py export examples/scene.json out/new   --event lost_support --pre 0.45
  # 2) compose
  python scripts/motion_test.py compose out/base out/new out/motion_test.mp4 --title "..."

The export only uses engine APIs that exist in both versions (segments, pose_at, planted_intervals, world_joints),
so it can compare any two revisions. Windows are aligned on an engine event (e.g. the first `lost_support`).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys

import numpy as np

FPS = 24
PW, PH = 948, 534  # panel size in the composed frame (even, for H.264)


def export(project_path: str, out_dir: str, event: str, pre: float, dur: float, center, view_h: float, roll: float = 0.0) -> None:
    import skia
    from apex.camera.director import CameraState
    from apex.render.pipeline import _effects_from_events, red_flash
    from apex.render.skia_renderer import SkiaRenderer
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec

    os.makedirs(out_dir, exist_ok=True)
    proj = ProjectSpec.model_validate(json.load(open(project_path)))
    rt = SceneRuntime(proj, proj.scenes[0].id)
    res = rt.simulate()
    cid = next(iter(res.animators))
    an, rig = res.animators[cid], rt.rigs[cid]
    t_ev = next(e.t for e in res.events if e.type == event)
    t0 = t_ev - pre
    n = int(round(dur * FPS))
    try:
        fx = _effects_from_events(res.events, {s.id: s for s in rt.env.switches}, rt.env)
    except TypeError:  # older engine signature
        fx = _effects_from_events(res.events, {s.id: s for s in rt.env.switches})
    r = SkiaRenderer(PW, PH, rt.env, {c: proj.character(c).style for c in rt.rigs}, rt.rigs)
    cam = CameraState(center[0], center[1], view_h, roll, "motion_test")
    planted = an.planted_intervals()
    hw, rh = rt.env.room.width / 2, rt.env.room.height
    vid = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{PW}x{PH}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "14", os.path.join(out_dir, "panel.mp4")], stdin=subprocess.PIPE)
    diag = []
    prev = None
    for i in range(n):
        t = t0 + i / FPS
        fs = rt.evaluate(t)
        try:
            from apex.render.pipeline import motion_trails
            img = r.render(fs, cam, red_flash(res.events, t), fx, 0.0, motion_trails(res, t)).copy()
        except (ImportError, TypeError):  # older engine: no trails
            img = r.render(fs, cam, red_flash(res.events, t), fx).copy()
        pose = fs.poses[cid]
        j = rig.world_joints(pose)
        seg = an.segments[an.segment_at(t)]
        F = res.frames[seg.frame]
        s_, h_ = F.to_frame(pose.root)
        feet = {leg: any(iv.leg == leg and iv.t0 <= t <= iv.t1 for iv in planted) for leg in "nf"}
        hands = {}
        for side in "nf":
            hx, hy = j[f"hand_{side}"]
            hands[side] = min(hx + hw, hw - hx, hy, rh - hy) < 6.0  # touching a room surface
        speed = 0.0 if prev is None else math.dist(prev, pose.root) * FPS
        prev = pose.root
        # centre of mass proxy (segment midpoints, weighted) vs the middle of the support in the surface frame
        pts = [j["pelvis"], j["spine_mid"], j["neck_base"], j["head_center"], j["knee_n"], j["knee_f"], j["elbow_n"], j["elbow_f"]]
        wts = [3, 3, 2, 1.5, 1.5, 1.5, 0.7, 0.7]
        com = (sum(p[0] * w for p, w in zip(pts, wts)) / sum(wts), sum(p[1] * w for p, w in zip(pts, wts)) / sum(wts))
        cs, _ = F.to_frame(com)
        fs_n, _ = F.to_frame(j["ankle_n"])
        fs_f, _ = F.to_frame(j["ankle_f"])
        bal = cs - (fs_n + fs_f) / 2 if seg.kind not in ("airborne", "swing") else None
        diag.append({"t": round(t - t0, 4), "state": seg.kind, "h": round(h_, 2), "speed": round(speed, 1), "balance": None if bal is None else round(bal, 2),
                     "foot_n": feet["n"], "foot_f": feet["f"], "hand_n": hands["n"], "hand_f": hands["f"]})
        # contact markers on the panel
        surf = skia.Surface.MakeRasterDirect(skia.ImageInfo.Make(PW, PH, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType), img)
        c = surf.getCanvas()
        c.translate(PW / 2, PH / 2)
        c.rotate(roll)
        for name, on, rgb in (("ankle_n", feet["n"], (80, 255, 140)), ("ankle_f", feet["f"], (80, 255, 140)),
                              ("hand_n", hands["n"], (255, 150, 60)), ("hand_f", hands["f"], (255, 150, 60))):
            if on:
                px, py, _ = r.P(*j[name], 0)
                c.drawCircle(px, py, 9, skia.Paint(AntiAlias=True, Color=skia.ColorSetARGB(255, *rgb), Style=skia.Paint.kStroke_Style, StrokeWidth=3))
        vid.stdin.write(img.tobytes())
    vid.stdin.close()
    vid.wait()
    # pose timeline: state bands + named key poses (motion-library clips when the engine has them)
    keys = []
    try:
        from apex.motion.library import Performance, get_clip, landing_clip
        for seg in an.segments:
            if seg.t1 < t0 or seg.t0 > t0 + dur:
                continue
            clips = []
            if seg.kind == "landing":
                clips.append(landing_clip(seg.data.get("approach", 600.0)))
            elif seg.kind == "idle" and seg.data.get("settle"):
                clips.append(("recover_relief_shake" if seg.data.get("variant", 0) % 2 else "recover_relief",
                              Performance(intensity=seg.data.get("settle_k", 1.0), emotion="relieved")))
            elif seg.kind == "airborne" and seg.data.get("intent") == "fall":
                clips.append(("fall_flail", Performance(emotion="afraid")))
            for name, perf in clips:
                cl = get_clip(name)
                for kt, kn in cl.key_times(perf):
                    if seg.t0 + kt <= min(seg.t1, t0 + dur) and (not cl.loop or kt < cl.length(perf)):
                        keys.append({"t": round(seg.t0 + kt - t0, 4), "name": kn, "clip": name})
    except ImportError:
        pass
    bands = [{"state": seg.kind, "t0": round(max(seg.t0, t0) - t0, 4), "t1": round(min(seg.t1, t0 + dur) - t0, 4)}
             for seg in an.segments if seg.t1 > t0 and seg.t0 < t0 + dur]
    events = [{"t": round(e.t - t0, 4), "type": e.type} for e in res.events if t0 <= e.t <= t0 + dur and e.type in
              ("lost_support", "brace", "impact", "recovered", "notice", "point", "grab", "release")]
    json.dump({"diag": diag, "keys": keys, "bands": bands, "events": events, "t_event": t_ev, "t0": t0}, open(os.path.join(out_dir, "diag.json"), "w"))
    print(f"exported {n} frames from t={t0:.2f} to {out_dir}")


STATE_RGB = {"idle": (95, 100, 110), "loco": (70, 140, 220), "airborne": (240, 160, 40), "landing": (200, 90, 200), "press": (220, 80, 80),
             "point": (90, 200, 120), "turn": (160, 160, 60), "swing": (60, 200, 200), "slide": (120, 90, 220), "crouch": (200, 200, 90)}


def compose(base_dir: str, new_dir: str, out_path: str, title: str, labels=("ORIGINAL (shipped 1D v2)", "IMPROVED (motion library)")) -> None:
    import skia
    A, B = json.load(open(os.path.join(base_dir, "diag.json"))), json.load(open(os.path.join(new_dir, "diag.json")))
    n = min(len(A["diag"]), len(B["diag"]))

    def frames(path):
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
        while True:
            buf = p.stdout.read(PW * PH * 4)
            if len(buf) < PW * PH * 4:
                return
            yield np.frombuffer(buf, dtype=np.uint8).reshape(PH, PW, 4)

    W, H = 1920, 1080
    out = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", out_path], stdin=subprocess.PIPE)
    tf = skia.Typeface("DejaVu Sans")
    f_t, f_l, f_s = skia.Font(tf, 24), skia.Font(tf, 18), skia.Font(tf, 13)
    P = lambda rgb, a=255: skia.Paint(AntiAlias=True, Color=skia.ColorSetARGB(a, *rgb))
    dur = n / FPS
    x0, x1 = 150, W - 30  # timeline x range

    def tx(t):
        return x0 + (x1 - x0) * t / dur

    for i, (fa, fb) in enumerate(zip(frames(os.path.join(base_dir, "panel.mp4")), frames(os.path.join(new_dir, "panel.mp4")))):
        if i >= n:
            break
        t = i / FPS
        surf = skia.Surface(W, H)
        c = surf.getCanvas()
        c.clear(skia.ColorSetRGB(10, 12, 15))
        c.drawString(title, 12, 30, f_t, P((255, 207, 58)))
        for k, (img, lab) in enumerate(((fa, labels[0]), (fb, labels[1]))):
            x = 8 + k * (PW + 8)
            c.drawImage(skia.Image.fromarray(np.ascontiguousarray(img), colorType=skia.ColorType.kRGBA_8888_ColorType), x, 44)
            c.drawString(lab, x + 10, 44 + 26, f_l, P((255, 255, 255)))
        c.drawString("green ring = planted foot   orange ring = hand on a surface", 8 + PW + 8 + 10, 44 + PH - 10, f_s, P((200, 220, 230)))
        y = 44 + PH + 14
        for k, (D, lab) in enumerate(((A, "original"), (B, "improved"))):
            # state bands + key poses
            c.drawString(lab, 10, y + 15, f_l, P((220, 230, 240)))
            for bd in D["bands"]:
                c.drawRect(skia.Rect(tx(bd["t0"]), y, tx(bd["t1"]), y + 20), P(STATE_RGB.get(bd["state"], (120, 120, 120)), 200))
                if tx(bd["t1"]) - tx(bd["t0"]) > 50:
                    c.drawString(bd["state"], tx(bd["t0"]) + 4, y + 15, f_s, P((10, 10, 10)))
            for kp in D["keys"]:
                xx = tx(kp["t"])
                c.drawLine(xx, y + 20, xx, y + 30, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE, StrokeWidth=1.5))
            last = -1e9
            for kp in D["keys"]:
                xx = tx(kp["t"])
                if xx - last > 64:
                    c.drawString(kp["name"], xx + 2, y + 42, f_s, P((255, 230, 160)))
                    last = xx
            # contacts
            cy = y + 50
            for row, (key, rgb) in enumerate((("foot_n", (80, 255, 140)), ("foot_f", (80, 255, 140)), ("hand_n", (255, 150, 60)), ("hand_f", (255, 150, 60)))):
                yy = cy + row * 9
                c.drawString(key, 90, yy + 8, skia.Font(tf, 10), P((170, 180, 190)))
                for d in D["diag"][:n]:
                    if d[key]:
                        c.drawRect(skia.Rect(tx(d["t"]), yy, tx(d["t"]) + (x1 - x0) / n + 0.5, yy + 7), P(rgb, 220))
            y = cy + 4 * 9 + 14
        # curves: pelvis height and balance
        ch = 120
        for k, (key, lab, lo, hi) in enumerate((("h", "pelvis height above support (units)", 0, 200), ("speed", "root speed (u/s)", 0, 1600))):
            gx0 = x0 + k * ((x1 - x0) // 2 + 10)
            gx1 = gx0 + (x1 - x0) // 2 - 10
            c.drawRect(skia.Rect(gx0, y, gx1, y + ch), P((22, 26, 32)))
            c.drawString(lab, gx0 + 6, y + 16, f_s, P((200, 210, 220)))
            for D, rgb in ((A, (150, 155, 165)), (B, (255, 190, 60))):
                path = skia.Path()
                for j, d in enumerate(D["diag"][:n]):
                    xx = gx0 + (gx1 - gx0) * d["t"] / dur
                    v = max(lo, min(hi, d[key]))
                    yy = y + ch - (v - lo) / (hi - lo) * (ch - 20) - 4
                    (path.lineTo if j else path.moveTo)(xx, yy)
                c.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.ColorSetARGB(255, *rgb), Style=skia.Paint.kStroke_Style, StrokeWidth=2))
            px = gx0 + (gx1 - gx0) * t / dur
            c.drawLine(px, y, px, y + ch, skia.Paint(Color=skia.ColorWHITE, StrokeWidth=1))
        c.drawString("grey = original   gold = improved", x0, y + ch + 18, f_s, P((200, 210, 220)))
        ptx = tx(t)
        c.drawLine(ptx, 44 + PH + 10, ptx, y - 8, skia.Paint(Color=skia.ColorSetARGB(220, 255, 255, 255), StrokeWidth=2))
        c.drawString(f"t = {t:4.2f} s (aligned on '{A.get('event', 'lost_support')}')", W - 330, 30, f_l, P((220, 230, 240)))
        out.stdin.write(surf.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType).tobytes())
    out.stdin.close()
    out.wait()
    print("wrote", out_path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("project")
    e.add_argument("out_dir")
    e.add_argument("--event", default="lost_support")
    e.add_argument("--pre", type=float, default=0.45)
    e.add_argument("--dur", type=float, default=5.0)
    e.add_argument("--center", type=float, nargs=2, default=[300.0, 300.0])
    e.add_argument("--view-h", type=float, default=640.0)
    e.add_argument("--roll", type=float, default=0.0, help="camera roll (deg); 90 = aligned with a right-wall landing")
    c = sub.add_parser("compose")
    c.add_argument("base")
    c.add_argument("new")
    c.add_argument("out")
    c.add_argument("--title", default="APEX motion test")
    a = ap.parse_args()
    if a.cmd == "export":
        export(a.project, a.out_dir, a.event, a.pre, a.dur, a.center, a.view_h, a.roll)
    else:
        compose(a.base, a.new, a.out, a.title)
