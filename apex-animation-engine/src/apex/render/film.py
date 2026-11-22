"""Multi-scene films (Milestone 6): render every scene of a project and join them into one film.

Each scene is rendered and checked on its own (`render_scene`, with QA). The scenes are then joined in order, entering
each one the way its `transition_in` says:
- `cut`: straight on;
- `fade`: a fade up from black (picture and sound);
- `warp`: a jump to another world: the picture comes up out of a white flash;
- `rewind`: the game resets. The last frame of the previous scene freezes and drains of colour, then the whole
  previous scene plays backwards at high speed with a glitch (colour split, noise, scan lines) and a tape-rewind sound
  (its own sound track reversed and pitched up). It is built from the frames that were rendered, so the rewind always
  shows exactly what happened.

Nothing is repaired by hand: the film is the scenes as rendered, plus transitions made from those same frames.
"""
from __future__ import annotations

import json
import os
import resource
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .video import ffmpeg_bin, probe

FREEZE_T = 0.7  # s: the frozen last frame before a rewind
REWIND_T = 1.8  # s: how long the rewind lasts, whatever the length of the scene it rewinds
FADE_T = 0.6


@dataclass
class SceneMetrics:
    scene: str
    frames: int
    seconds: float  # wall time: simulate + render + encode + QA
    render_fps: float
    gates: dict
    checks: int
    failed: List[str]
    peak_rss_mb: float  # peak resident memory of the process so far


@dataclass
class FilmResult:
    video: str
    duration: float
    scenes: List[SceneMetrics] = field(default_factory=list)
    film_checks: List[dict] = field(default_factory=list)
    seconds: float = 0.0
    peak_rss_mb: float = 0.0

    def to_dict(self) -> dict:
        return {"video": self.video, "duration": round(self.duration, 3), "seconds": round(self.seconds, 1),
                "peak_rss_mb": round(self.peak_rss_mb, 1), "film_checks": self.film_checks,
                "scenes": [vars(s) for s in self.scenes]}


def _rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # Linux: kilobytes


def _run(cmd: List[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-2000:]}")


def _duration(path: str) -> float:
    return float(probe(path)["format"]["duration"])


def rewind_clip(prev: str, out: str, fps: int, size) -> float:
    """The reset between two attempts, built from the previous scene's rendered file. Returns its length (s)."""
    W, H = size
    d = _duration(prev)
    k = max(1.0, (d - 0.05) / REWIND_T)
    ff = ffmpeg_bin()
    freeze = out + ".freeze.mp4"
    last = max(0.0, d - 1.5 / fps)
    # the world freezes: the last frame, held, losing its colour, with a growing noise
    _run([ff, "-y", "-loglevel", "error", "-ss", f"{last:.3f}", "-i", prev, "-f", "lavfi", "-t", f"{FREEZE_T}",
          "-i", "anullsrc=r=48000:cl=stereo",
          "-filter_complex", f"[0:v]trim=end_frame=1,loop=loop={int(FREEZE_T * fps)}:size=1,setpts=N/{fps}/TB,"
                             f"hue=s='max(0,1-t/{FREEZE_T * 0.8})',noise=alls='20':allf=t,scale={W}:{H},fps={fps},format=yuv420p[v]",
          "-map", "[v]", "-map", "1:a", "-t", f"{FREEZE_T}", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
          "-c:a", "aac", "-b:a", "192k", "-ar", "48000", freeze])
    rew = out + ".rew.mp4"
    # the rewind: the scene backwards, k times faster, glitched; its sound reversed and pitched up like a tape
    vf = (f"[0:v]setpts=PTS/{k:.4f},fps={fps},reverse,rgbashift=rh=-7:bh=7,noise=alls=28:allf=t+u,"
          f"drawgrid=w=iw:h=6:t=2:c=black@0.35,eq=saturation=0.55:contrast=1.15,scale={W}:{H},format=yuv420p[v]")
    af = (f"[0:a]areverse,asetrate={int(48000 * min(k, 6.0))},aresample=48000,atempo={max(0.5, min(2.0, k / min(k, 6.0))):.4f},"
          f"atrim=0:{REWIND_T},volume=0.55,aformat=sample_rates=48000:channel_layouts=stereo[a]")
    _run([ff, "-y", "-loglevel", "error", "-i", prev, "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]",
          "-t", f"{REWIND_T}", "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", rew])
    _concat([freeze, rew], out, fps, size, fades=[False, False])
    for f in (freeze, rew):
        os.remove(f)
    return _duration(out)


def _concat(parts: List[str], out: str, fps: int, size, fades: List[bool], crf: int = 17) -> None:
    W, H = size
    cmd = [ffmpeg_bin(), "-y", "-loglevel", "error"]
    for p in parts:
        cmd += ["-i", p]
    g, ins = [], []
    for i, (p, fade) in enumerate(zip(parts, fades)):
        v = f"[{i}:v]scale={W}:{H},fps={fps},format=yuv420p,setsar=1"
        a = f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo"
        if fade == "warp":
            v += ",fade=t=in:st=0:d=0.7:color=white"
            a += ",afade=t=in:st=0:d=0.3"
        elif fade:
            v += f",fade=t=in:st=0:d={FADE_T}"
            a += f",afade=t=in:st=0:d={FADE_T}"
        g += [v + f"[v{i}]", a + f"[a{i}]"]
        ins.append(f"[v{i}][a{i}]")
    g.append("".join(ins) + f"concat=n={len(parts)}:v=1:a=1[v][a]")
    cmd += ["-filter_complex", ";".join(g), "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out]
    _run(cmd)


def render_film(project, out_path: str, samples: int = 1, preview_scale: float = 1.0, work_dir: Optional[str] = None,
                qa: bool = True, only: Optional[List[str]] = None, progress: Optional[Callable] = None,
                strict_qa: bool = False) -> FilmResult:
    """Render every scene (or the ones in `only`, reusing earlier renders of the rest from `work_dir`) and join them."""
    from ..qa.film import check_film
    if strict_qa and not qa:
        raise ValueError("strict_qa requires QA to be enabled")
    if strict_qa and only is not None:
        raise ValueError("strict_qa requires a full fresh render; omit --only to avoid stale cached scenes")
    from .pipeline import render_scene
    t0 = time.time()
    work = work_dir or os.path.splitext(out_path)[0] + "_scenes"
    os.makedirs(work, exist_ok=True)
    W, H = int(project.width * preview_scale), int(project.height * preview_scale)
    result = FilmResult(out_path, 0.0)
    segs = []
    for i, sc in enumerate(project.scenes):
        seg = os.path.join(work, f"{i:02d}_{sc.id}.mp4")
        meta = seg + ".json"
        if only is not None and sc.id not in only and os.path.exists(seg) and os.path.exists(meta):
            result.scenes.append(SceneMetrics(**json.load(open(meta))))
            segs.append(seg)
            continue
        if progress:
            progress("scene", i / len(project.scenes), f"{sc.id} ({i + 1}/{len(project.scenes)})")
        ts = time.time()
        r = render_scene(project, sc.id, seg, samples=samples, qa=qa, preview_scale=preview_scale, progress=progress,
                         qa_path=seg + ".qa.json" if qa else None)
        dt = time.time() - ts
        rep = r.qa
        m = SceneMetrics(sc.id, r.frames, round(dt, 1), round(r.frames / dt, 2), rep.gates() if rep else {},
                         len(rep.checks) if rep else 0, sorted(c.name for c in rep.checks if c.status == "FAIL") if rep else [],
                         round(_rss_mb(), 1))
        json.dump(vars(m), open(meta, "w"), indent=1)
        result.scenes.append(m)
        segs.append(seg)
        if strict_qa and any(v == "FAIL" for v in m.gates.values()):
            raise RuntimeError(f"strict film QA: scene {sc.id} failed: {m.failed}")
    result.film_checks = [vars(c) for c in check_film(project)]
    if strict_qa and any(c["status"] == "FAIL" for c in result.film_checks):
        raise RuntimeError("strict film QA: film-wide checks failed: " +
                           ", ".join(c["name"] for c in result.film_checks if c["status"] == "FAIL"))
    parts, fades = [], []
    for i, (sc, seg) in enumerate(zip(project.scenes, segs)):
        if i > 0 and sc.transition_in == "rewind":
            rw = os.path.join(work, f"{i:02d}_rewind.mp4")
            rewind_clip(segs[i - 1], rw, project.fps, (W, H))
            parts.append(rw)
            fades.append(False)
        parts.append(seg)
        fades.append("warp" if sc.transition_in == "warp" else (sc.transition_in == "fade" or (i == 0 and sc.transition_in != "cut")))
    if progress:
        progress("film", 0.0, f"joining {len(parts)} parts")
    _concat(parts, out_path, project.fps, (W, H), fades)
    result.duration = _duration(out_path)
    result.seconds = time.time() - t0
    result.peak_rss_mb = _rss_mb()
    return result
