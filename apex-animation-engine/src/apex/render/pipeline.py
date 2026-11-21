"""End-to-end scene production: simulate -> direct camera -> render frames -> sound -> encode -> QA.

Scenes are independent units: re-rendering one scene never requires re-simulating others.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np

from ..audio.sound_director import SoundDirector
from ..camera.director import CameraDirector
from ..qa.inspector import Inspector, QAReport
from ..scene.runtime import SceneRuntime
from ..scene.schema import ProjectSpec
from .skia_renderer import SkiaRenderer
from .video import VideoWriter

ProgressFn = Callable[[str, float, str], None]  # (stage, fraction 0..1, message)


@dataclass
class RenderResult:
    video: str
    qa: Optional[QAReport]
    frames: int
    seconds: float
    events: List[dict]


def _surface_ring(env, surface: str, x: float, y: float, t: float, **kw) -> dict:
    hw, rh = env.room.width / 2, env.room.height
    if surface in ("wall_right", "wall_left"):
        return {"kind": "ring_wall", "t": t, "x": (hw - 0.5) if surface == "wall_right" else (-hw + 0.5), "y": y, **kw}
    return {"kind": "ring_floor", "t": t, "x": x, "y": 0.0 if surface == "floor" else rh, **kw}


def _effects_from_events(events, switches, env=None) -> List[dict]:
    from ..scene.targets import exit_world, switch_base
    fx = []
    for e in events:
        if e.type == "switch_activated":
            sw = switches[e.data["switch"]]
            if env is None or sw.surface == "floor":
                fx += [{"kind": "ring_floor", "t": e.t, "x": sw.x, "r0": 30, "speed": 1500, "life": 0.9},
                       {"kind": "ring_floor", "t": e.t + 0.12, "x": sw.x, "r0": 30, "speed": 1100, "life": 0.9, "rgb": (255, 140, 150)}]
            else:
                bx, by = switch_base(env, sw)
                fx += [_surface_ring(env, sw.surface, bx, by, e.t, r0=30, speed=600, life=0.8)]
                fx += [{"kind": "flash", "t": e.t, "x": bx, "y": by, "r": 40, "grow": 260, "rgb": (255, 70, 80), "a": 0.8, "life": 0.6}]
        elif e.type == "gravity_shift":
            fx.append({"kind": "sweep", "t": e.t, "life": 0.45})
        elif e.type == "impact":
            px, py = e.data["point"]
            surf = e.data["surface"]
            if env is not None:
                kw = dict(r0=20, speed=380, life=0.7) if surf.startswith("wall") else dict(r0=10, speed=260, life=0.45, rgb=(180, 250, 255), z=0)
                fx.append(_surface_ring(env, surf, px, py, e.t, **kw))
                if e.data.get("normal_speed", 0) > 1000:  # hard impact: speed streaks + debris along the surface
                    from ..scene.targets import surface_normal
                    fx.append({"kind": "burst", "t": e.t, "x": px, "y": py, "n": surface_normal(surf), "life": 0.32,
                               "strength": min(1.5, e.data["normal_speed"] / 1200.0), "seed": int(e.t * 1000) % 997})
            elif surf == "wall_right":
                fx.append({"kind": "ring_wall", "t": e.t, "y": py, "r0": 20, "speed": 380, "life": 0.7})
            else:
                fx.append({"kind": "ring_floor", "t": e.t, "x": px, "z": 0, "r0": 10, "speed": 260, "life": 0.45, "rgb": (180, 250, 255)})
        elif e.type == "grab":
            bx, by = e.data["point"]
            fx.append({"kind": "flash", "t": e.t, "x": bx, "y": by, "r": 20, "grow": 90, "rgb": (255, 225, 140), "a": 0.9, "life": 0.35})
        elif e.type in ("door_unlocking", "door_open") and env is not None:
            dx, dy = exit_world(env, e.data["exit"])
            rgb = (90, 255, 160) if e.type == "door_unlocking" else (235, 252, 255)
            fx.append({"kind": "flash", "t": e.t, "x": dx, "y": dy, "r": 80, "grow": 320, "rgb": rgb, "a": 0.7, "life": 0.8})
        elif e.type == "hit":  # a blow lands: impact star + flash, sized by the power
            px, py = e.data["point"]
            st = min(1.6, 0.55 + 0.6 * e.data.get("power", 1.0))
            fx.append({"kind": "impact", "t": e.t, "x": px, "y": py, "strength": st, "dir": e.data.get("dir", 1.0), "life": 0.24,
                       "seed": int(e.t * 1000) % 997})
            fx.append({"kind": "flash", "t": e.t, "x": px, "y": py, "r": 30 * st, "grow": 140 * st, "rgb": (255, 245, 225), "a": 0.85, "life": 0.22})
        elif e.type == "block_hit":  # stopped by the guard: sparks off the forearms
            px, py = e.data["point"]
            fx.append({"kind": "spark", "t": e.t, "x": px, "y": py, "strength": min(1.4, 0.6 + 0.5 * e.data.get("power", 1.0)),
                       "life": 0.3, "seed": int(e.t * 1000) % 991})
            fx.append({"kind": "flash", "t": e.t, "x": px, "y": py, "r": 18, "grow": 70, "rgb": (255, 210, 120), "a": 0.7, "life": 0.2})
        elif e.type == "body_fall" and "point" in e.data:  # a body slams into the floor
            px, _ = e.data["point"]
            fx.append({"kind": "ring_floor", "t": e.t, "x": px, "z": 0, "r0": 12, "speed": 300, "life": 0.5, "rgb": (200, 230, 240)})
            fx.append({"kind": "dust", "t": e.t, "x": px, "y": 0})
        elif e.type == "footstep" and e.data.get("speed", 0) > 300 and e.data.get("surface", "floor") == "floor":
            fx.append({"kind": "dust", "t": e.t, "x": e.data.get("x", 0), "y": 0})
    return fx


def strike_swooshes(res) -> List[dict]:
    """A swoosh arc along the striking fist / foot, from the snap to just after contact (sampled from the poses)."""
    out = []
    for cid, an in res.animators.items():
        rig = an.rig
        for seg in an.segments:
            if seg.kind != "strike":
                continue
            d = seg.data
            limb = d["limb"]
            joint = ("wrist_" if limb.startswith("hand") else "ankle_") + limb[-1]
            t0, t1 = seg.t0 + d["t_a"], min(seg.t1, seg.t0 + d["t_c"] + 0.05)
            n = 10
            pts = [(t0 + (t1 - t0) * k / (n - 1), rig.world_joints(an.pose_at(t0 + (t1 - t0) * k / (n - 1)))[joint]) for k in range(n)]
            out.append({"kind": "swoosh", "t": t0, "t_end": t1, "pts": pts, "life": (t1 - t0) + 0.16,
                        "rgb": tuple(int(c) for c in bytes.fromhex(an.style.glow_color.lstrip("#")))})
    return out


def red_flash(events, t: float) -> float:
    r = 0.0
    for e in events:
        if e.type == "switch_activated" and t >= e.t:
            r += 0.5 * math.exp(-(t - e.t) * 5) + 0.3 * math.exp(-max(0.0, t - e.t - 0.15) * 3.5) * (t > e.t + 0.15)
    return r


def _resolve_target(env, target: str, rt=None, t: float = 0.0):
    """A target's world point at time t: static targets from the environment; props and characters from the
    simulation (`prop:<id>` = the prop's centre, `char:<id>` = the character's chest)."""
    from ..scene.targets import resolve
    kind, _, ref = target.partition(":")
    if rt is not None and rt.result is not None:
        if kind == "prop" and ref in rt.result.prop_tracks:
            an = next(iter(rt.result.animators.values()))
            x, y, _ = an.prop_at(ref, t)
            return (x, y)
        if kind == "char" and ref in rt.result.animators:
            an = rt.result.animators[ref]
            x, y = an.root_at(t)
            return (x, y + 0.45 * an.stand_h)
    try:
        return resolve(env, target)
    except (StopIteration, ValueError):
        return None


def prop_ghosts(res, t: float) -> dict:
    """Earlier positions of fast-moving props (a thrown glyph leaves fading ghosts)."""
    out = {}
    if not res.animators:
        return out
    an = next(iter(res.animators.values()))
    for pid in res.prop_tracks:
        x, y, a = an.prop_at(pid, t)
        xs = []
        for k, alpha in ((1, 0.32), (2, 0.18), (3, 0.08)):
            px, py, pa = an.prop_at(pid, max(0.0, t - k * SMEAR_DT))
            if math.hypot(x - px, y - py) > 10.0 * k:
                xs.append((px, py, pa, alpha))
        if xs:
            out[pid] = xs
    return out


def motion_trails(res, t: float) -> dict:
    """Earlier poses for motion trails (the renderer draws only the limbs that moved fast)."""
    return {cid: [(an.pose_at(t - 1.0 / 60.0), 0.3), (an.pose_at(t - 1.0 / 30.0), 0.15)] for cid, an in res.animators.items()}


# ------------------------------------------------------------ Milestone 3: film-time effects
SMEAR_DT = 1.0 / 48.0  # story seconds a smear reaches back


def warp_effects(fx: List[dict], warp) -> List[dict]:
    """Effects run on the film clock (they keep animating through a hit-stop and stretch with slow motion)."""
    if warp.is_identity():
        return fx
    out = []
    for e in fx:
        e = dict(e)
        e["t"] = warp.film_at(e["t"])
        if "t_end" in e:
            e["t_end"] = warp.film_at(e["t_end"])
        if "pts" in e:
            e["pts"] = [(warp.film_at(tp), p) for tp, p in e["pts"]]
        out.append(e)
    return out


def warp_events(events, warp):
    """Copies of the engine events placed on the film clock (for the sound track)."""
    from ..motion.controller import Event
    if warp.is_identity():
        return list(events)
    out = [Event(warp.film_at(e.t), e.type, e.character, e.data) for e in events]
    for sl in warp.slows:  # a low whoosh as time slows down
        out.append(Event(warp.film_at(sl.t0), "slowmo", "", {"label": sl.label}))
    return sorted(out, key=lambda e: (e.t, e.type))


def film_camera(c, warp, tf: float, tfx) -> object:
    """Camera moves that live in film time: shake through a hit-stop, a punch-in on heavy blows, a slow push-in during
    slow motion."""
    from dataclasses import replace
    if warp.is_identity() or tfx is None:
        return c
    sx, sy, zoom = 0.0, 0.0, 1.0
    for h in warp.holds:
        f0 = warp.film_at(h.t)
        age = tf - f0
        if age < 0 or age > h.film + 0.35:
            continue
        amp = (5.0 + 7.0 * min(1.6, h.power)) * (1.0 if age < h.film else max(0.0, 1.0 - (age - h.film) / 0.35))
        sx += amp * math.sin(age * 2 * math.pi * 23.0)
        sy += amp * 0.7 * math.cos(age * 2 * math.pi * 19.0)
        if tfx.punch_in and h.power >= 0.9 and h.kind != "block_hit":
            env = min(1.0, age / 0.03) * math.exp(-max(0.0, age - h.film) / (0.45 if h.heavy else 0.25))
            if h.heavy and h.point is not None:  # a knockdown: the camera closes in on the blow for the held frame
                zoom = min(zoom, 1.0 - 0.3 * env)
                fx_ = (h.point[0] - c.cx) * 0.45 * env
                fy_ = (h.point[1] - c.cy) * 0.45 * env
                c = replace(c, cx=c.cx + fx_, cy=c.cy + fy_)
            else:
                zoom = min(zoom, 1.0 - 0.1 * min(1.0, h.power / 1.4) * env)
    if tfx.punch_in:
        zoom *= 1.0 - 0.12 * warp.slow_weight(tf)
    return replace(c, shx=c.shx + sx, shy=c.shy + sy, view_h=c.view_h * zoom)


def screen_effects(warp, tf: float, tfx) -> dict:
    if warp.is_identity() or tfx is None or not tfx.screen_fx:
        return {}
    s = {"lines": warp.slow_weight(tf), "seed": int(tf * 24) // 2}
    for h in warp.holds:
        age = tf - warp.film_at(h.t)
        if 0 <= age < h.film + 0.3:
            s["vignette"] = max(s.get("vignette", 0.0), min(1.0, 0.5 + 0.35 * h.power) * (1.0 if age < h.film else 1 - (age - h.film) / 0.3))
            if h.power >= 1.0 and h.kind != "block_hit" and age < 2.0 / 24.0:  # heavy blows only, two frames at most
                s["flash"] = max(s.get("flash", 0.0), 0.26 if age < 1.0 / 24.0 else 0.12)
                s["at"] = h.t
    return s


def chroma_split(frame: np.ndarray, px: int) -> np.ndarray:
    """Red right, blue left by px pixels (the impact frame of a hit-stop)."""
    if px <= 0:
        return frame
    out = frame.copy()
    out[:, px:, 0] = frame[:, :-px, 0]
    out[:, :-px, 2] = frame[:, px:, 2]
    return out


def shot_fade(cam: CameraDirector, t: float) -> float:
    """Fade-to-black amount at time t (ShotSpec.fade_out: seconds at the end of the shot)."""
    sh = cam.shot_at(t)
    if sh.fade_out <= 0:
        return 0.0
    return max(0.0, min(1.0, (t - (sh.end - sh.fade_out)) / sh.fade_out))


def build_camera(rt: SceneRuntime, aspect: float) -> CameraDirector:
    res = rt.result or rt.simulate()
    rigs = rt.rigs

    def bbox(cid: str, t: float):
        j = rigs[cid].world_joints(res.animators[cid].pose_at(t))
        xs = [p[0] for p in j.values()]
        ys = [p[1] for p in j.values()]
        return min(xs) - 12, min(ys) - 6, max(xs) + 12, max(ys) + 14

    def focus(cid: str, t: float, kind: str):
        j = rigs[cid].world_joints(res.animators[cid].pose_at(t))
        if kind == "head":
            c = j["head_center"]
            return c[0] - 34, c[1] - 30, c[0] + 34, c[1] + 30
        keys = ["pelvis", "neck_base", "head_center", "head_top", "shoulder_n", "elbow_n", "wrist_n", "hand_n", "elbow_f", "wrist_f"]
        xs, ys = [j[k][0] for k in keys], [j[k][1] for k in keys]
        return min(xs) - 14, min(ys) - 10, max(xs) + 14, max(ys) + 16

    def vel(cid: str, t: float):
        a, b = res.animators[cid].pose_at(t - 0.05).root, res.animators[cid].pose_at(t + 0.05).root
        return ((b[0] - a[0]) / 0.1, (b[1] - a[1]) / 0.1)

    shake = []
    for e in res.events:
        if e.type in ("impact", "grab"):
            shake.append((e.t, 10.0 * min(2.0, e.data.get("normal_speed", 600) / 700)))
        elif e.type == "gravity_shift":
            shake.append((e.t, 7.0))
        elif e.type == "switch_activated":
            shake.append((e.t, 4.0))
        elif e.type == "prop_impact":
            shake.append((e.t, 2.0))
        elif e.type == "hit":
            shake.append((e.t, 3.0 + 4.0 * min(1.6, e.data.get("power", 1.0))))
        elif e.type == "block_hit":
            shake.append((e.t, 2.0))
        elif e.type == "body_fall" and e.character and "point" in e.data:
            shake.append((e.t, 4.0))
    return CameraDirector(rt.scene.shots, aspect, bbox, vel, gravity=res.gravity.at, focus_bbox=focus, shake_events=shake,
                          gravity_angle=res.gravity.angle_unwrapped, resolve=lambda tg, t=0.0: _resolve_target(rt.env, tg, rt, t))


def compute_diagnostics(rt: SceneRuntime, cam: CameraDirector, fps: int) -> List[dict]:
    """Per-frame character/physics/camera diagnostics (for review charts and regression comparison)."""
    res = rt.result or rt.simulate()
    out = []
    n = int(round(res.duration * fps))
    for cid, an in res.animators.items():
        planted = an.planted_intervals()
        prev = None
        for i in range(n):
            t = i / fps
            pose = an.pose_at(t)
            seg = an.segments[an.segment_at(t)]
            F = res.frames[seg.frame]
            g = res.gravity.at(t)
            s, h = F.to_frame(pose.root)
            speed = 0.0 if prev is None else math.dist(prev, pose.root) * fps
            prev = pose.root
            feet = {leg: any(iv.leg == leg and iv.t0 <= t <= iv.t1 for iv in planted) for leg in "nf"}
            sc = res.scarves.get(cid)
            tip = 0.0
            if sc is not None:
                a, b = sc.at(t - 0.02)[0][-1], sc.at(t + 0.02)[0][-1]
                tip = math.dist(a, b) / 0.04
            c = cam.at(t)
            out.append({"t": round(t, 4), "character": cid, "shot": c.shot, "state": seg.kind, "surface": seg.frame,
                        "speed": round(speed, 2), "height": round(h, 2), "tilt": round(math.degrees(pose.body_angle - F.body_angle), 3),
                        "gravity_deg": round(math.degrees(math.atan2(g[1], g[0])), 2), "gravity_state": res.gravity.state_label(t),
                        "planted_n": feet["n"], "planted_f": feet["f"], "eye": round(pose.eye, 3), "head_facing": pose.head_facing,
                        "scarf_tip_speed": round(tip, 1), "roll": round(c.roll, 2), "view_h": round(c.view_h, 1)})
    return out


def render_scene(project: ProjectSpec, scene_id: str, out_path: str, samples: int = 1, qa: bool = True, preview_scale: float = 1.0,
                 progress: Optional[ProgressFn] = None, qa_path: Optional[str] = None, review_dir: Optional[str] = None) -> RenderResult:
    """Simulate, render, encode and (optionally) inspect one scene. `review_dir` additionally writes a timestamped
    contact sheet, per-frame diagnostics (JSON + chart) and a full-decode report."""
    say = progress or (lambda *a: None)
    t_start = time.time()
    rt = SceneRuntime(project, scene_id)
    say("simulate", 0.0, "physics + motion + secondary motion")
    res = rt.simulate()
    say("simulate", 1.0, f"{len(res.events)} events")
    rigs = rt.rigs
    W, H = int(project.width * preview_scale), int(project.height * preview_scale)
    scene = rt.scene
    cam = build_camera(rt, W / H)
    styles = {cid: project.character(cid).style for cid in rigs}
    renderer = SkiaRenderer(W, H, rt.env, styles, rigs)
    renderer.depth = {pl.character: pl.z for pl in scene.placements if pl.z}
    switches = {s.id: s for s in rt.env.switches}
    for e in res.events:  # attach world x to footsteps for dust placement
        if e.type == "footstep":
            e.data.setdefault("x", rt.evaluate(e.t).poses[e.character].root[0] if e.character in res.animators else 0.0)
    from .timewarp import build_warp
    warp = build_warp(scene, res.events, res.duration, project.fps)
    tfx = scene.time_fx
    fx = warp_effects(_effects_from_events(res.events, switches, rt.env) + strike_swooshes(res), warp)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wav = os.path.splitext(out_path)[0] + ".wav"
    sd = SoundDirector(project.seed, {c.on_event: c.sound for sh in scene.shots for c in sh.sound_cues})
    n = int(round(warp.film_duration * project.fps))
    film_events = warp_events(res.events, warp)
    cues = sd.render(film_events, n / project.fps, wav)  # audio length == frame-quantised video length (no dropped frames)
    say("audio", 1.0, f"{len(cues)} cues")
    writer = VideoWriter(out_path, W, H, project.fps, audio=wav)
    try:
        for i in range(n):
            tf = i / project.fps
            t = warp.sim_at(tf)  # the story instant this film frame shows
            fade = shot_fade(cam, t)
            smears = ghosts = None
            if tfx is not None and tfx.smears:
                smears = {cid: an.pose_at(max(0.0, t - SMEAR_DT)) for cid, an in res.animators.items()}
                ghosts = prop_ghosts(res, t)
            hold = warp.holding(tf)
            scr = screen_effects(warp, tf, tfx)
            if "at" in scr:
                scr["world"] = next((e.data["point"] for e in res.events if abs(e.t - scr["at"]) < 0.07 and e.type in ("hit", "prop_hit")
                                     and "point" in e.data), None)
            if samples <= 1:
                frame = renderer.render(rt.evaluate(t), film_camera(cam.at(t), warp, tf, tfx), red_flash(res.events, t), fx, fade,
                                        motion_trails(res, t), fx_t=tf if not warp.is_identity() else None, smears=smears,
                                        prop_ghosts=ghosts, screen=scr)
            else:
                acc = None
                sh = cam.shot_at(t)
                for k in range(samples):
                    ts = t + (k / (samples - 1) - 0.5) * 0.4 / project.fps
                    ts = min(max(ts, sh.start), sh.end - 1e-4)
                    tfk = tf + (k / (samples - 1) - 0.5) * 0.4 / project.fps
                    ts = min(max(warp.sim_at(tfk), sh.start), sh.end - 1e-4)
                    f = renderer.render(rt.evaluate(ts), film_camera(cam.at(ts), warp, tfk, tfx), red_flash(res.events, ts), fx, fade,
                                        motion_trails(res, ts) if k == samples // 2 else None, fx_t=tfk if not warp.is_identity() else None,
                                        smears=smears if k == samples // 2 else None, prop_ghosts=ghosts if k == samples // 2 else None,
                                        screen=screen_effects(warp, tfk, tfx)).astype(np.float32)
                    acc = f if acc is None else acc + f
                frame = (acc / samples).astype(np.uint8)
            if hold is not None and tfx is not None and tfx.screen_fx and hold[0].kind != "block_hit":
                frame = chroma_split(frame, int(round((2 + 3 * min(1.5, hold[0].power)) * (1 - hold[1]) * H / 720)))
            writer.write(frame)
            if i % 24 == 0 or i == n - 1:
                say("render", (i + 1) / n, f"frame {i + 1}/{n}")
    finally:
        writer.close()
    report = None
    if qa:
        say("qa", 0.0, "running inspector")
        report = Inspector(rt, cam, project.fps, size=(W, H), warp=warp).run(video=out_path, cues=cues)
        if qa_path:
            with open(qa_path, "w") as fh:
                json.dump(report.to_dict(), fh, indent=1, default=str)
        say("qa", 1.0, "PASSED" if report.passed else "FAILED")
    if review_dir:
        from ..qa.media import contact_sheet, decode_check, diagnostics_chart
        os.makedirs(review_dir, exist_ok=True)
        base = os.path.join(review_dir, os.path.splitext(os.path.basename(out_path))[0])
        diag = compute_diagnostics(rt, cam, project.fps)
        with open(base + "_diagnostics.json", "w") as fh:
            json.dump(diag, fh)
        shots = [(sh.id, sh.start, sh.end) for sh in scene.shots]
        diagnostics_chart(diag, base + "_diagnostics.png", shots, f"{project.title} - {scene_id} - character / physics / camera diagnostics")
        times = [round(x * 0.5, 2) for x in range(int(n / project.fps / 0.5) + 1) if x * 0.5 < n / project.fps]  # film times
        labels = []
        an = next(iter(res.animators.values()))
        for tf in times:
            t = warp.sim_at(tf)
            story = "" if warp.is_identity() else f" | story {t:.2f}s"
            labels.append(f"{cam.shot_at(t).id} | {an.segments[an.segment_at(t)].kind}{story}")
        contact_sheet(out_path, base + "_contact_sheet.png", times, labels, title=f"{project.title} - {scene_id} (film t | shot | state | story t)")
        with open(base + "_decode.json", "w") as fh:
            json.dump(decode_check(out_path), fh, indent=1)
        say("review", 1.0, f"review artefacts in {review_dir}")
    evs = [{"t": round(e.t, 4), "type": e.type, "character": e.character} for e in res.events]
    return RenderResult(out_path, report, n, time.time() - t_start, evs)
