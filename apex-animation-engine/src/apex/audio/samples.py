"""Recorded sound-effect samples (curated, freely licensed; see sfx/CREDITS.md) layered with the synthesiser.

`sfx/manifest.json` maps an engine sound name (footstep, impact, clank, door, ...) to layers of sample files. For each
cue, one file per layer is picked deterministically from (seed, cue index) and played with a small random pitch and
gain variation, so repeated events never sound identical. Files are decoded once with ffmpeg (already required for
video encoding). When ffmpeg or the files are missing, the bank reports itself unavailable and the sound director
falls back to its synthesised sounds.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional

import numpy as np

SFX_DIR = os.path.join(os.path.dirname(__file__), "sfx")
_DECODED: Dict[str, np.ndarray] = {}


def decode(path: str, sr: int) -> np.ndarray:
    """Decode any audio file to mono float32 at `sr`, peak-normalised to 0.9."""
    key = f"{path}@{sr}"
    if key not in _DECODED:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.float32).astype(np.float64)
        pk = float(np.max(np.abs(x))) if len(x) else 0.0
        _DECODED[key] = x * (0.9 / pk) if pk > 0 else x
    return _DECODED[key]


def _repitch(x: np.ndarray, ratio: float) -> np.ndarray:
    """Resample by `ratio` (>1 = higher and shorter), like varispeed tape."""
    if abs(ratio - 1.0) < 1e-6 or len(x) < 2:
        return x
    n = max(2, int(len(x) / ratio))
    return np.interp(np.arange(n) * ratio, np.arange(len(x)), x)


class SampleBank:
    def __init__(self, sr: int, seed: int = 7, root: str = SFX_DIR):
        self.sr, self.seed, self.root = sr, seed, root
        path = os.path.join(root, "manifest.json")
        self.manifest = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"sounds": {}}
        self.ok = shutil.which("ffmpeg") is not None and bool(self.manifest["sounds"])
        # The source repository may ship the manifest without the licensed WAV
        # packs (for example when rendering on a clean GitHub Actions runner).
        # Never attempt ffmpeg on a missing file: fall back to deterministic
        # synthesized audio rather than failing the entire film render.
        if self.ok:
            missing = [f for f in self.files() if not os.path.isfile(os.path.join(self.root, f))]
            if missing:
                self.ok = False

    def _spec(self, name: str) -> Optional[dict]:
        spec = self.manifest["sounds"].get(name)
        if spec and "alias" in spec:
            spec = self.manifest["sounds"].get(spec["alias"])
        return spec

    def has(self, name: str) -> bool:
        return self.ok and self._spec(name) is not None

    def synth_mix(self, name: str) -> float:
        spec = self._spec(name)
        return float(spec.get("synth_mix", 0.0)) if spec else 1.0

    def files(self) -> List[str]:
        out = set()
        for spec in self.manifest["sounds"].values():
            for layer in spec.get("layers", []):
                out.update(layer["files"])
        if "room_tone" in self.manifest:
            out.add(self.manifest["room_tone"]["file"])
        return sorted(out)

    def render(self, name: str, index: int, intensity: float = 1.0) -> np.ndarray:
        """One performance of `name` for cue number `index` (deterministic). Harder hits play slightly lower."""
        spec = self._spec(name)
        rng = np.random.default_rng((self.seed * 1_000_003 + index * 7919 + sum(map(ord, name))) & 0xFFFFFFFF)
        spread = float(spec.get("pitch", 0.0))
        out = np.zeros(1)
        for layer in spec["layers"]:
            f = layer["files"][int(rng.integers(len(layer["files"])))]
            x = decode(os.path.join(self.root, f), self.sr)
            ratio = layer.get("pitch_base", 1.0) * (1.0 + spread * float(rng.uniform(-1, 1))) * (1.0 - 0.08 * (intensity - 1.0))
            x = _repitch(x, max(0.5, ratio)) * layer.get("gain", 1.0) * 10 ** (float(rng.uniform(-1.5, 1.5)) / 20)
            if len(x) > len(out):
                out = np.pad(out, (0, len(x) - len(out)))
            out[:len(x)] += x
        return out

    def room_tone(self, n: int, offset_s: float = 0.0) -> Optional[np.ndarray]:
        """A looped room-tone bed of n samples (None if not configured). Loops crossfade over 0.25 s."""
        rt = self.manifest.get("room_tone")
        if not self.ok or not rt:
            return None
        x = decode(os.path.join(self.root, rt["file"]), self.sr)
        xf = min(int(0.25 * self.sr), len(x) // 4)
        if xf > 0:  # crossfaded loop body
            body = x[:-xf].copy()
            body[:xf] = body[:xf] * np.linspace(0, 1, xf) + x[-xf:] * np.linspace(1, 0, xf)
        else:
            body = x
        reps = int(np.ceil((n + len(body)) / len(body))) + 1
        loop = np.tile(body, reps)
        k = int(offset_s * self.sr) % len(body)
        return loop[k:k + n] * float(rt.get("gain", 0.1))
