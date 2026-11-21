"""FFmpeg encoding (raw RGBA frames streamed over a pipe) and ffprobe verification."""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

import numpy as np


class EncodeError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise EncodeError("ffmpeg not found on PATH (install it: see docs/SETUP.md)")
    return exe


class VideoWriter:
    def __init__(self, path: str, width: int, height: int, fps: int, audio: Optional[str] = None, crf: int = 17, preset: str = "medium"):
        self.path, self.w, self.h = path, width, height
        cmd = [ffmpeg_bin(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-"]
        if audio:
            cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart"]
        if audio:
            cmd += ["-shortest"]
        cmd += [path]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.frames = 0

    def write(self, rgba: np.ndarray) -> None:
        if rgba.shape != (self.h, self.w, 4):
            raise EncodeError(f"frame has shape {rgba.shape}, expected {(self.h, self.w, 4)}")
        try:
            self.proc.stdin.write(np.ascontiguousarray(rgba, dtype=np.uint8).tobytes())
        except BrokenPipeError as e:
            raise EncodeError(self.proc.stderr.read().decode(errors="replace")) from e
        self.frames += 1

    def close(self) -> None:
        self.proc.stdin.close()
        rc = self.proc.wait()
        err = self.proc.stderr.read().decode(errors="replace")
        if rc != 0:
            raise EncodeError(f"ffmpeg failed ({rc}): {err}")


def probe(path: str) -> dict:
    exe = shutil.which("ffprobe")
    if not exe:
        raise EncodeError("ffprobe not found on PATH")
    out = subprocess.run([exe, "-v", "error", "-show_entries",
                          "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,duration,sample_rate,channels",
                          "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)
