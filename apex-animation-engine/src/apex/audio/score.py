"""A procedural film score (cinematic upgrade): music that follows the story's moods.

A scene's `score` lists mood cues placed at a time or on an engine event (goal syntax); each mood plays until the
next, with a crossfade. Moods have their own tempo, chord progression and instrumentation:

    calm      soft pad, slow arpeggio                                (80 bpm, minor)
    tension   low drone, pulsing bass, heartbeat kick, high tremolo  (92 bpm, minor with a flat second)
    action    drums, driving bass, fast arpeggio, pad                (132 bpm, minor)
    sad       piano, soft pad                                        (64 bpm, minor)
    hope      pad, rising arpeggio                                   (84 bpm, minor turning to its major relative)
    triumph   pad, bright arpeggio, light drums                      (112 bpm, major)
    silence   nothing (a held breath)

Everything is synthesised (no samples), deterministic from the seed, and stereo. Times are film time.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

SR = 48000

# chord shapes as semitones above the key's root
MINOR = {"i": (0, 3, 7), "III": (3, 7, 10), "iv": (5, 8, 12), "V": (7, 11, 14), "VI": (8, 12, 15), "VII": (10, 14, 17),
         "bII": (1, 5, 8)}
MAJOR = {"I": (0, 4, 7), "IV": (5, 9, 12), "V": (7, 11, 14), "vi": (9, 12, 16), "ii": (2, 5, 9)}
MOODS = {
    "calm": dict(bpm=80, prog=["i", "VI", "III", "VII"], q=MINOR, layers=("pad", "arp8")),
    "tension": dict(bpm=92, prog=["i", "i", "bII", "i"], q=MINOR, layers=("drone", "pulse", "heart", "trem")),
    "action": dict(bpm=132, prog=["i", "VI", "VII", "i"], q=MINOR, layers=("pad", "bass8", "arp16", "drums")),
    "sad": dict(bpm=64, prog=["i", "iv", "VI", "V"], q=MINOR, layers=("pad_soft", "piano")),
    "hope": dict(bpm=84, prog=["VI", "VII", "III", "III"], q=MINOR, layers=("pad", "arp8", "bass_long")),
    "triumph": dict(bpm=112, prog=["I", "V", "vi", "IV"], q=MAJOR, layers=("pad", "arp16", "bass8", "drums_light")),
    "silence": dict(bpm=60, prog=["i"], q=MINOR, layers=()),
}
KEYS = {"C": 48, "C#": 49, "D": 50, "D#": 51, "E": 52, "F": 53, "F#": 54, "G": 55, "G#": 56, "A": 45, "A#": 46, "B": 47}


def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def _tone(f: float, n: int, harm: int = 1, detune: float = 0.0, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k in range(1, harm + 1):
        out += np.sin(2 * np.pi * f * k * (1 + detune) * t + phase * k) / k
    return out


def _adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    env = np.full(n, s)
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    env[:na] = np.linspace(0, 1, na, endpoint=False) if na else env[:na]
    e2 = min(n, na + nd)
    if e2 > na:
        env[na:e2] = np.linspace(1, s, e2 - na, endpoint=False)
    if nr and n > nr:
        env[-nr:] *= np.linspace(1, 0, nr)
    return env


class Score:
    def __init__(self, seed: int = 7, key: str = "D"):
        self.rng = np.random.default_rng(seed)
        self.root = KEYS.get(key, 50)

    def render(self, cues: List[Tuple[float, str]], duration: float, gain: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
        """`cues`: (film time, mood), sorted. Returns the left and right channels."""
        n = int(round(duration * SR))
        L, R = np.zeros(n), np.zeros(n)
        xf = 0.9  # crossfade (s)
        for i, (t0, mood) in enumerate(cues):
            t1 = cues[i + 1][0] if i + 1 < len(cues) else duration
            if t1 <= t0 or mood == "silence":
                continue
            a = max(0.0, t0 - (xf / 2 if i else 0.0))
            b = min(duration, t1 + xf / 2)
            l, r = self._section(mood, b - a, i)
            env = np.ones(len(l))
            k = int(xf * SR)
            if i:
                env[:k] = np.linspace(0, 1, min(k, len(env)))[:len(env[:k])]
            if i + 1 < len(cues) or b < duration:
                env[-k:] *= np.linspace(1, 0, min(k, len(env)))[-len(env[-k:]):]
            s0 = int(a * SR)
            m = min(len(l), n - s0)
            L[s0:s0 + m] += (l * env)[:m]
            R[s0:s0 + m] += (r * env)[:m]
        peak = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-9)
        return L / peak * gain, R / peak * gain

    # ------------------------------------------------------------ one mood for a while
    def _section(self, mood: str, dur: float, idx: int) -> Tuple[np.ndarray, np.ndarray]:
        M = MOODS[mood]
        n = int(dur * SR)
        L, R = np.zeros(n), np.zeros(n)
        beat = 60.0 / M["bpm"]
        bar = 4 * beat
        nbars = int(math.ceil(dur / bar)) + 1
        root = self.root
        rng = np.random.default_rng(1000 + idx)

        def add(sig, t, pan=0.0, g=1.0):
            s0 = int(t * SR)
            if s0 >= n or s0 < 0:
                return
            m = min(len(sig), n - s0)
            L[s0:s0 + m] += sig[:m] * g * math.sqrt(0.5 * (1 - pan))
            R[s0:s0 + m] += sig[:m] * g * math.sqrt(0.5 * (1 + pan))

        for b in range(nbars):
            tb = b * bar
            if tb >= dur:
                break
            ch = M["q"][M["prog"][b % len(M["prog"])]]
            notes = [root + 12 + c for c in ch]
            lay = M["layers"]
            if "pad" in lay or "pad_soft" in lay:
                soft = "pad_soft" in lay
                m = int((bar + 1.2) * SR)
                for k, nt in enumerate(notes):
                    env = _adsr(m, 0.5 if soft else 0.25, 0.4, 0.8, 1.0)
                    sl = _tone(hz(nt), m, 5 if not soft else 3, detune=+0.003) * env
                    sr_ = _tone(hz(nt), m, 5 if not soft else 3, detune=-0.003, phase=1.3) * env
                    add(sl, tb, -0.6, 0.11)
                    add(sr_, tb, 0.6, 0.11)
            if "drone" in lay:
                m = int((bar + 0.6) * SR)
                env = _adsr(m, 0.3, 0.2, 0.9, 0.5)
                add(_tone(hz(root - 12), m, 6) * env, tb, 0, 0.16)
                add(_tone(hz(root - 12 + 7), m, 4, detune=0.002) * env, tb, 0.2, 0.06)
            if "trem" in lay:  # high strings, tremolo, a dissonant second
                m = int(bar * SR)
                tt = np.arange(m) / SR
                trem = 0.5 + 0.5 * np.sin(2 * np.pi * 9.0 * tt)
                for nt, p in ((root + 36 + ch[0], -0.4), (root + 36 + ch[0] + 1, 0.4)):
                    add(_tone(hz(nt), m, 2) * trem * _adsr(m, 0.6, 0.1, 0.9, 0.4), tb, p, 0.025)
            if "pulse" in lay or "bass8" in lay:
                step = beat / 2
                for k in range(8):
                    m = int(step * 0.9 * SR)
                    env = np.exp(-np.arange(m) / SR * (9.0 if "pulse" in lay else 6.0))
                    nt = root - 12 + ch[0] + (12 if ("bass8" in lay and k % 2) else 0)
                    sig = np.tanh(2.2 * _tone(hz(nt), m, 3)) * env
                    add(sig, tb + k * step, 0.0, 0.17 if "bass8" in lay else 0.13)
            if "bass_long" in lay:
                m = int(bar * SR)
                add(_tone(hz(root - 12 + ch[0]), m, 3) * _adsr(m, 0.1, 0.5, 0.6, 0.6), tb, 0, 0.15)
            if "heart" in lay:  # lub-dub
                for k in range(0, 4, 2):
                    for d, g in ((0.0, 1.0), (0.22, 0.7)):
                        m = int(0.25 * SR)
                        tt = np.arange(m) / SR
                        sig = np.sin(2 * np.pi * np.cumsum(60 * (40 / 60) ** (tt / 0.25)) / SR) * np.exp(-tt * 18)
                        add(sig, tb + k * beat + d, 0, 0.34 * g)
            if "arp8" in lay or "arp16" in lay:
                step = beat / (2 if "arp8" in lay else 4)
                seq = notes + [notes[0] + 12] + notes[::-1][1:]
                for k in range(int(round(bar / step))):
                    nt = seq[k % len(seq)] + 12
                    m = int(0.45 * SR)
                    env = np.exp(-np.arange(m) / SR * (6.5 if "arp8" in lay else 10.0))
                    add(_tone(hz(nt), m, 3) * env, tb + k * step, -0.5 if k % 2 else 0.5, 0.07)
            if "piano" in lay:
                order = [0, 1, 2, 1, 0, 2, 1, 2]
                for k in range(8):
                    nt = notes[order[k]] + (12 if k in (2, 5) else 0)
                    m = int(1.8 * SR)
                    tt = np.arange(m) / SR
                    sig = sum(np.sin(2 * np.pi * hz(nt) * h * (1 + 0.0004 * h * h) * tt) * np.exp(-tt * (2.2 + 1.3 * h)) / h for h in range(1, 6))
                    add(sig, tb + k * beat / 2, -0.25 + 0.5 * (k % 2), 0.12)
            if "drums" in lay or "drums_light" in lay:
                light = "drums_light" in lay
                for k in range(4):  # kick on every beat, snare on 2 and 4, hats on eighths
                    add(self._kick(), tb + k * beat, 0, 0.5 if not light else 0.35)
                    if k % 2 == 1:
                        add(self._snare(rng), tb + k * beat, 0.1, 0.22 if not light else 0.14)
                    for h in range(2 if light else 4):
                        add(self._hat(rng), tb + k * beat + h * beat / (2 if light else 4), 0.4, 0.05)
        return L, R

    @staticmethod
    def _kick() -> np.ndarray:
        m = int(0.3 * SR)
        tt = np.arange(m) / SR
        return np.sin(2 * np.pi * np.cumsum(110 * (42 / 110) ** (tt / 0.12)) / SR) * np.exp(-tt * 14)

    @staticmethod
    def _snare(rng) -> np.ndarray:
        m = int(0.22 * SR)
        tt = np.arange(m) / SR
        noise = rng.standard_normal(m)
        noise = noise - np.convolve(noise, np.ones(6) / 6, mode="same")  # crude high-pass
        return (0.7 * noise + 0.5 * np.sin(2 * np.pi * 190 * tt)) * np.exp(-tt * 22)

    @staticmethod
    def _hat(rng) -> np.ndarray:
        m = int(0.05 * SR)
        x = rng.standard_normal(m)
        x = x - np.convolve(x, np.ones(3) / 3, mode="same")
        return x * np.exp(-np.arange(m) / SR * 80)


def resolve_cues(spec, events, duration: float) -> List[Tuple[float, str]]:
    """Mood cues in film time from a ScoreSpec (times, or events in the film's own clock)."""
    from ..scene.goals import matches
    out = []
    for c in spec.cues:
        if c.at is not None:
            out.append((c.at + c.delay, c.mood))
        else:
            hit = next((e for e in events if matches(c.on, e)), None)
            if hit is not None:
                out.append((hit.t + c.delay, c.mood))
    out = sorted((max(0.0, min(duration, t)), m) for t, m in out)
    if not out or out[0][0] > 0.0:
        out.insert(0, (0.0, out[0][1] if out else "calm"))
    return out
