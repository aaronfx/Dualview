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


def _effects_from_events(events, switches) -> List[dict]:
    fx = []
    for e in events:
        if e.type == "switch_activated":
            sw = switches[e.data["switch"]]
            fx += [{"kind": "ring_floor", "t": e.t, "x": sw.x, "r0": 30, "speed": 1500, "life": 0.9},
                   {"kind": "ring_floor", "t": e.t + 0.12, "x": sw.x, "r0": 30, "speed": 1100, "life": 0.9, "rgb": (255, 140, 150)}]
        elif e.type == "gravity_shift":
            fx.append({"kind": "sweep", "t": e.t, "life": 0.45})
        elif e.type == "impact":
            if e.data["surface"] == "wall_right":
                fx.append({"kind": "ring_wall", "t": e.t, "y": e.data["point"][1], "r0": 20, "speed": 380, "life": 0.7})
            else:
                fx.append({"kind": "ring_floor", "t": e.t, "x": e.data["point"][0], "z": 0, "r0": 10, "speed": 260, "life": 0.45, "rgb": (180, 250, 255)})
        elif e.type == "footstep" and e.data.get("speed", 0) > 300:
            fx.append({"kind": "dust", "t": e.t, "x": e.data.get("x", 0), "y": 0})
    return fx


def red_flash(events, t: float) -> float:
    r = 0.0
    for e in events:
        if e.type == "switch_activated" and t >= e.t:
            r += 0.5 * math.exp(-(t - e.t) * 5) + 0.3 * math.exp(-max(0.0, t - e.t - 0.15) * 3.5) * (t > e.t + 0.15)
    return r


def render_scene(project: ProjectSpec, scene_id: str, out_path: str, samples: int = 1, qa: bool = True, preview_scale: float = 1.0,
                 progress: Optional[ProgressFn] = None, qa_path: Optional[str] = None) -> RenderResult:
    say = progress or (lambda *a: None)
    t_start = time.time()
    rt = SceneRuntime(project, scene_id)
    say("simulate", 0.0, "physics + motion simulation")
    res = rt.simulate()
    say("simulate", 1.0, f"{len(res.events)} events")
    rigs = rt.rigs
    W, H = int(project.width * preview_scale), int(project.height * preview_scale)

    def bbox(cid: str, t: float):
        j = rigs[cid].world_joints(res.animators[cid].pose_at(t))
        xs = [p[0] for p in j.values()]
        ys = [p[1] for p in j.values()]
        return min(xs) - 12, min(ys) - 6, max(xs) + 12, max(ys) + 14

    def vel(cid: str, t: float):
        a, b = res.animators[cid].pose_at(t - 0.05).root, res.animators[cid].pose_at(t + 0.05).root
        return ((b[0] - a[0]) / 0.1, (b[1] - a[1]) / 0.1)

    scene = rt.scene
    cam = CameraDirector(scene.shots, W / H, bbox, vel)
    styles = {cid: project.character(cid).style for cid in rigs}
    renderer = SkiaRenderer(W, H, rt.env, styles, rigs)
    switches = {s.id: s for s in rt.env.switches}
    for e in res.events:  # attach world x to footsteps for dust placement
        if e.type == "footstep":
            e.data.setdefault("x", rt.evaluate(e.t).poses[e.character].root[0] if e.character in res.animators else 0.0)
    fx = _effects_from_events(res.events, switches)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    wav = os.path.splitext(out_path)[0] + ".wav"
    sd = SoundDirector(project.seed, {c.on_event: c.sound for sh in scene.shots for c in sh.sound_cues})
    n = int(round(res.duration * project.fps))
    cues = sd.render(res.events, n / project.fps, wav)  # audio length == frame-quantised video length (no dropped frames)
    say("audio", 1.0, f"{len(cues)} cues")
    writer = VideoWriter(out_path, W, H, project.fps, audio=wav)
    try:
        for i in range(n):
            t = i / project.fps
            if samples <= 1:
                frame = renderer.render(rt.evaluate(t), cam.at(t), red_flash(res.events, t), fx)
            else:
                acc = None
                sh = cam.shot_at(t)
                for k in range(samples):
                    ts = t + (k / (samples - 1) - 0.5) * 0.4 / project.fps
                    ts = min(max(ts, sh.start), sh.end - 1e-4)
                    f = renderer.render(rt.evaluate(ts), cam.at(ts), red_flash(res.events, ts), fx).astype(np.float32)
                    acc = f if acc is None else acc + f
                frame = (acc / samples).astype(np.uint8)
            writer.write(frame)
            if i % 24 == 0 or i == n - 1:
                say("render", (i + 1) / n, f"frame {i + 1}/{n}")
    finally:
        writer.close()
    report = None
    if qa:
        say("qa", 0.0, "running inspector")
        report = Inspector(rt, cam, project.fps, size=(W, H)).run(video=out_path, cues=cues)
        if qa_path:
            with open(qa_path, "w") as fh:
                json.dump(report.to_dict(), fh, indent=1, default=str)
        say("qa", 1.0, "PASSED" if report.passed else "FAILED")
    evs = [{"t": round(e.t, 4), "type": e.type, "character": e.character} for e in res.events]
    return RenderResult(out_path, report, n, time.time() - t_start, evs)
