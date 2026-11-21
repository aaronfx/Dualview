"""Character and interaction diagnostics for a multi-character scene (JSON + chart).

    PYTHONPATH=src python scripts/interaction_diagnostics.py examples/the_rescue.json out/diag

Writes `interaction_diagnostics.json` and `interaction_diagnostics.png`:
- per-character state timeline (segments);
- prop tracks (position, and the height of each long prop's free end);
- hand-to-contact error while pushing, lifting and working a lever (how far the hands are from the simulated grip);
- minimum joint clearance above the floor per character;
- the interaction events.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
import skia

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

STATE_COL = {"idle": (90, 100, 115), "loco": (80, 160, 220), "push": (255, 150, 60), "fall": (255, 70, 70), "prone": (200, 80, 80),
             "crawl": (255, 120, 120), "getup": (250, 200, 90), "lift": (255, 205, 60), "lever": (120, 230, 140), "offer": (150, 220, 255),
             "gesture": (220, 150, 255), "turn": (130, 130, 150)}


def collect(path: str):
    proj = ProjectSpec.model_validate(json.load(open(path)))
    sc = proj.scenes[0]
    rt = SceneRuntime(proj, sc.id)
    r = rt.simulate()
    D = sc.duration
    ts = np.arange(0.0, D, 1 / 24)
    out = {"scene": sc.id, "duration": D, "characters": {}, "props": {}, "events": []}
    for cid, an in r.animators.items():
        rig = rt.rigs[cid]
        segs = [{"kind": s.kind, "t0": round(s.t0, 3), "t1": round(s.t1, 3)} for s in an.segments]
        clearance, contact_err = [], []
        for t in ts:
            pose = an.pose_at(float(t))
            j = rig.world_joints(pose)
            clearance.append(min(p[1] for p in j.values()))
            seg = an.segments[an.segment_at(float(t))]
            err = None
            if seg.kind == "push":
                g = an._prop_world(seg.data["prop"], float(t), seg.data["grip_local"])
                err = min(math.dist(j["hand_n"], g), math.dist(j["hand_f"], g))
            elif seg.kind == "lift" and 0.5 < t - seg.t0 < seg.data.get("dur", 2.4) - 0.45:  # while gripping
                g = an._prop_world(seg.data["prop"], float(t), seg.data["grip_local"])
                err = min(math.dist(j["wrist_n"], g), math.dist(j["wrist_f"], g), math.dist(j["hand_n"], g))
            elif seg.kind == "lever" and seg.data.get("phase") in ("press", "hold"):
                g, _ = an._bar_grips(seg.data["bar"], float(t), "handle")
                err = max(0.0, min(math.dist(j["hand_n"], g), math.dist(j["wrist_n"], g) - rig.p.hand))
            contact_err.append(err)
        ce = [e for e in contact_err if e is not None]
        out["characters"][cid] = {
            "segments": segs, "min_joint_height": round(float(min(clearance)), 2),
            "contact_error": {"samples": len(ce), "max": round(max(ce), 2) if ce else None, "mean": round(float(np.mean(ce)), 2) if ce else None},
            "series": {"t": [round(float(t), 3) for t in ts], "min_joint_height": [round(float(c), 2) for c in clearance],
                       "contact_error": [None if e is None else round(e, 2) for e in contact_err]},
        }
    for p in proj.environment(sc.environment).props:
        x, y, a = [], [], []
        free = []
        for t in ts:
            px, py, pa = next(iter(r.animators.values())).prop_at(p.id, float(t))
            x.append(round(px, 1)); y.append(round(py, 1)); a.append(round(pa, 3))
            hx, hy = p.size[0] / 2, p.size[1] / 2
            ends = [(px + l[0] * math.cos(pa) - l[1] * math.sin(pa), py + l[0] * math.sin(pa) + l[1] * math.cos(pa))
                    for l in (((hx, 0), (-hx, 0)) if p.size[0] >= p.size[1] else ((0, hy), (0, -hy)))]
            free.append(round(max(e[1] for e in ends), 1))
        out["props"][p.id] = {"kind": p.kind, "x": x, "y": y, "angle": a, "highest_end": free}
    out["events"] = [{"t": round(e.t, 3), "type": e.type, "who": e.character} for e in r.events if e.type not in ("footstep",)]
    return out


def chart(d: dict, path: str) -> None:
    W, H = 1600, 900
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color(14, 16, 20))
    font, small = skia.Font(None, 22), skia.Font(None, 15)
    white = skia.Paint(Color=skia.Color(230, 235, 240), AntiAlias=True)
    D = d["duration"]
    x0, x1 = 160, W - 30
    X = lambda t: x0 + (x1 - x0) * t / D
    c.drawString(f"Interaction diagnostics - {d['scene']}", 20, 34, font, white)
    y = 70
    for cid, ch in d["characters"].items():  # state bands
        c.drawString(cid, 20, y + 20, font, white)
        for s in ch["segments"]:
            rgb = STATE_COL.get(s["kind"], (120, 120, 120))
            c.drawRect(skia.Rect(X(s["t0"]), y, X(min(D, s["t1"])), y + 28), skia.Paint(Color=skia.Color(*rgb)))
            if X(s["t1"]) - X(s["t0"]) > 44:
                c.drawString(s["kind"], X(s["t0"]) + 3, y + 19, small, skia.Paint(Color=skia.Color(10, 10, 12)))
        y += 40

    def plot(series, ts, top, h, lo, hi, rgb, label):
        c.drawRect(skia.Rect(x0, top, x1, top + h), skia.Paint(Color=skia.Color(26, 30, 36)))
        c.drawString(label, 20, top + 18, small, white)
        c.drawString(f"{hi:g}", x0 - 40, top + 12, small, white)
        c.drawString(f"{lo:g}", x0 - 40, top + h, small, white)
        path, pen = skia.Path(), False
        for t, v in zip(ts, series):
            if v is None:
                pen = False
                continue
            yy = top + h - h * (min(hi, max(lo, v)) - lo) / (hi - lo)
            (path.lineTo if pen else path.moveTo)(X(t), yy)
            pen = True
        c.drawPath(path, skia.Paint(Color=skia.Color(*rgb), Style=skia.Paint.kStroke_Style, StrokeWidth=2.2, AntiAlias=True))

    ts = next(iter(d["characters"].values()))["series"]["t"]
    top = y + 20
    for pid in ("post", "container"):
        if pid in d["props"]:
            pr = d["props"][pid]
            ser = pr["highest_end"] if pid == "post" else pr["x"]
            plot(ser, ts, top, 110, min(ser) - 5, max(ser) + 5, (255, 200, 80) if pid == "post" else (120, 190, 255),
                 f"{pid}: {'highest end (height)' if pid == 'post' else 'x position'}")
            top += 130
    for cid, ch in d["characters"].items():
        plot(ch["series"]["contact_error"], ts, top, 80, 0, 20, (120, 255, 160), f"{cid}: hand-contact error (0-20)")
        top += 100
    for cid, ch in d["characters"].items():
        plot(ch["series"]["min_joint_height"], ts, top, 60, -5, 60, (255, 120, 120), f"{cid}: lowest joint height")
        top += 75
    for e in d["events"]:  # event ticks
        if e["type"] in ("push_lost", "rope_snap", "pinned", "lift_fail", "lever_engage", "freed", "stood_up", "fist_bump"):
            c.drawLine(X(e["t"]), y + 10, X(e["t"]), H - 10, skia.Paint(Color=skia.Color(255, 255, 255, 60)))
            c.drawString(e["type"], X(e["t"]) + 2, y + 14, small, skia.Paint(Color=skia.Color(255, 255, 255, 170)))
    surf.makeImageSnapshot().save(path, skia.kPNG)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    d = collect(src)
    with open(os.path.join(out, "interaction_diagnostics.json"), "w") as fh:
        json.dump(d, fh)
    chart(d, os.path.join(out, "interaction_diagnostics.png"))
    for cid, ch in d["characters"].items():
        print(cid, "min joint height", ch["min_joint_height"], "contact error", ch["contact_error"])
