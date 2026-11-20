"""Sound Director: binds engine events to synthesized sounds (all original, generated from scratch).

Synchronisation rule: a cue's time is ALWAYS the time of the engine event it is bound to. Cues are never placed
by guessed timestamps; QA verifies this mapping.
"""
from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import numpy as np

SR = 48000


def _n(d: float) -> int:
    return int(round(d * SR))


def _t(d: float) -> np.ndarray:
    return np.arange(_n(d)) / SR


def _env(n: int, a: float, d: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d)


def _norm(x: np.ndarray) -> np.ndarray:
    return x / (np.max(np.abs(x)) + 1e-9)


def _bandpass(x: np.ndarray, lo: float, hi: Optional[float], soft: float = 0.15) -> np.ndarray:
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo > 0:
        m *= 1 / (1 + np.exp(-(np.log(f + 1e-9) - np.log(lo)) / soft))
    if hi:
        m *= 1 / (1 + np.exp((np.log(f + 1e-9) - np.log(hi)) / soft))
    return np.fft.irfft(X * m, len(x))


def _sweep(f0: float, f1: float, d: float, curve: float = 1.0) -> np.ndarray:
    t = _t(d)
    u = (t / d) ** curve
    return np.sin(2 * np.pi * np.cumsum(f0 * (f1 / f0) ** u) / SR)


class Synth:
    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)

    def noise(self, d: float) -> np.ndarray:
        return self.rng.standard_normal(_n(d))

    def footstep(self, v: float = 1.0, surface: str = "floor") -> np.ndarray:
        d = 0.2
        n = _n(d)
        f0 = 130 if surface == "floor" else 170
        s = 0.9 * _sweep(f0, 55, d) * _env(n, 0.002, 0.035) + 0.5 * _norm(_bandpass(self.noise(d), 1500, 7000)) * _env(n, 0.0005, 0.012)
        ring = 1210 if surface == "floor" else 1530
        s += 0.12 * (np.sin(2 * np.pi * ring * _t(d)) + 0.6 * np.sin(2 * np.pi * ring * 1.55 * _t(d))) * _env(n, 0.001, 0.06)
        return s * v

    def click(self) -> np.ndarray:
        d = 0.25
        n = _n(d)
        return (0.8 * _norm(_bandpass(self.noise(d), 3000, 12000)) * _env(n, 0.0002, 0.004)
                + 0.35 * np.sin(2 * np.pi * 2250 * _t(d)) * _env(n, 0.0005, 0.03) + 0.7 * _sweep(260, 120, d) * _env(n, 0.001, 0.03))

    def pulse(self) -> np.ndarray:
        d = 2.0
        n = _n(d)
        t = _t(d)
        boom = _sweep(78, 32, d, 0.5) * _env(n, 0.004, 0.55)
        buzz = _bandpass((2 * ((55 * t) % 1) - 1) + 0.6 * (2 * ((110.7 * t) % 1) - 1), 90, 2500) * _env(n, 0.003, 0.35)
        return boom + 0.6 * _sweep(39, 26, d, 0.5) * _env(n, 0.01, 0.7) + 0.35 * _norm(buzz)

    def whoosh(self, d: float = 0.9, f0: float = 300, f1: float = 2500) -> np.ndarray:
        n = _n(d)
        x = self.noise(d)
        out = np.zeros(n)
        seg = 2048
        for i in range(0, n - seg, seg // 2):
            cf = f0 * (f1 / f0) ** (i / n)
            out[i:i + seg] += _bandpass(x[i:i + seg] * np.hanning(seg), cf * 0.6, cf * 2.2)
        return _norm(out) * np.sin(np.pi * np.arange(n) / n) ** 0.8

    def impact(self, strength: float = 1.0) -> np.ndarray:
        d = 1.4
        n = _n(d)
        t = _t(d)
        thud = _sweep(150, 48, d, 0.35) * _env(n, 0.001, 0.18)
        body = _norm(_bandpass(self.noise(d), 60, 1400)) * _env(n, 0.0005, 0.06)
        ring = sum(a * np.sin(2 * np.pi * 523 * r * t) for r, a in [(1, 1), (2.27, 0.6), (3.64, 0.4)]) * _env(n, 0.001, 0.35)
        return clamp01(strength) * (1.2 * thud + 0.6 * body) + 0.08 * ring

    def clang(self, strength: float = 1.0) -> np.ndarray:
        d = 0.9
        n = _n(d)
        t = _t(d)
        c = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(310, 1), (743, 0.8), (1187, 0.6), (1731, 0.5)]) * _env(n, 0.001, 0.2)
        return clamp01(strength) * (0.6 * c + 0.5 * _norm(_bandpass(self.noise(d), 1500, 9000)) * _env(n, 0.001, 0.1))

    def jump(self) -> np.ndarray:
        return 0.4 * _norm(_bandpass(self.noise(0.2), 600, 4000)) * _env(_n(0.2), 0.01, 0.06)

    def chime(self, notes=(587.3, 880.0), gap: float = 0.09, decay: float = 0.4) -> np.ndarray:
        d = gap * len(notes) + decay * 3
        out = np.zeros(_n(d))
        for k, f in enumerate(notes):
            i = _n(gap * k)
            m = len(out) - i
            t = np.arange(m) / SR
            out[i:] += (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2.76 * f * t)) * _env(m, 0.002, decay) * 0.5
        return out

    def notice(self) -> np.ndarray:
        """Curious 'what's that?' stinger: two rising notes."""
        return self.chime((659.3, 987.8), 0.11, 0.35)

    def startle(self) -> np.ndarray:
        d = 0.9
        n = _n(d)
        t = _t(d)
        stab = sum(np.sin(2 * np.pi * f * t) for f in (146.8, 207.7, 293.7)) / 3 * _env(n, 0.003, 0.25)
        return 0.8 * stab + 0.35 * self.whoosh(d, 1200, 300)[:n]

    def hum_rise(self, d: float) -> np.ndarray:
        n = _n(d)
        t = np.arange(n) / SR
        f = 70 * (220 / 70) ** (t / d)
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.4 * np.sign(np.sin(2 * np.pi * np.cumsum(2 * f) / SR))
        return _bandpass(x, 60, 3000) * np.minimum(1, t / 0.1) * (0.3 + 0.7 * t / d)

    def music(self, events, duration: float) -> np.ndarray:
        """Small adaptive score bed: calm minor pad -> tension cluster from the switch until recovery -> brighter
        resolution when the new path is noticed. Chord changes are placed at engine event times."""
        n = _n(duration)
        t = np.arange(n) / SR
        first = {}
        for e in events:
            first.setdefault(e.type, []).append(e.t)
        t_act = (first.get("switch_activated") or [duration])[0]
        t_rec = (first.get("recovered") or [duration])[0]
        notices = first.get("notice") or []
        t_res = next((x for x in notices if x > t_rec), duration)

        def pad(freqs, a, b):
            seg = np.zeros(n)
            m = (t >= a) & (t < b + 1.0)
            if not m.any():
                return seg
            tt = t[m] - a
            env = np.minimum(1, tt / 0.6) * np.clip((b + 1.0 - t[m]) / 1.0, 0, 1)
            seg[m] = sum(np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt) for f in freqs) / len(freqs) * env
            return seg
        out = 0.5 * pad((73.4, 110.0, 146.8, 174.6), 0.0, t_act)            # D minor, calm
        out += 0.6 * pad((73.4, 103.8, 146.8, 155.6), t_act, t_rec)          # tension cluster (tritone + minor 2nd)
        out += 0.55 * pad((73.4, 110.0, 146.8, 185.0, 220.0), t_res, duration)  # D major lift: a way out
        return out * 0.05

    def ambience(self, duration: float) -> np.ndarray:
        n = _n(duration)
        t = np.arange(n) / SR
        a = 0.05 * np.sin(2 * np.pi * 50 * t) + 0.03 * np.sin(2 * np.pi * 100.3 * t)
        a += 0.04 * _norm(_bandpass(self.rng.standard_normal(n), 40, 260))
        return a * np.minimum(1, t / 0.3)


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


DEFAULT_BINDINGS = {
    "footstep": "footstep", "press_contact": "click", "gravity_shift": "pulse", "lost_support": "whoosh",
    "impact": "impact", "prop_impact": "clang", "takeoff": "jump", "recovered": None, "brace": None,
    "switch_activated": "startle", "notice": "notice", "point": "chime",
}


@dataclass
class Cue:
    t: float
    event_type: str
    sound: str
    gain: float


class SoundDirector:
    def __init__(self, seed: int = 7, bindings: Optional[Dict[str, Optional[str]]] = None, music: bool = True):
        self.synth = Synth(seed)
        self.music_on = music
        self.bindings = dict(DEFAULT_BINDINGS)
        if bindings:
            self.bindings.update(bindings)

    def cues_for(self, events) -> List[Cue]:
        cues = []
        for e in events:
            snd = self.bindings.get(e.type)
            if snd:
                gain = 1.0
                if e.type == "footstep":
                    gain = 0.35 + 0.5 * clamp01(e.data.get("speed", 150) / 450)
                elif e.type in ("impact", "prop_impact"):
                    gain = 0.4 + 0.6 * clamp01(e.data.get("normal_speed", 600) / 1200)
                cues.append(Cue(e.t, e.type, snd, gain))
        return cues

    def render(self, events, duration: float, path: str) -> List[Cue]:
        n = _n(duration)
        L = np.zeros(n)
        cues = self.cues_for(events)
        sy = self.synth
        bank: Dict[str, Callable[..., np.ndarray]] = {"footstep": sy.footstep, "click": sy.click, "pulse": sy.pulse, "whoosh": sy.whoosh,
                                                       "impact": sy.impact, "clang": sy.clang, "jump": sy.jump, "notice": sy.notice,
                                                       "startle": sy.startle, "chime": sy.chime}
        bank["land"] = bank["impact"]
        unknown = sorted({c.sound for c in cues} - set(bank))
        if unknown:
            raise ValueError(f"unknown sound(s) {unknown}; available: {sorted(bank)}")
        ev_by_t = {(round(e.t, 6), e.type): e for e in events}
        for cue in cues:
            e = ev_by_t.get((round(cue.t, 6), cue.event_type))
            if cue.sound == "footstep":
                sig = sy.footstep(1.0, (e.data.get("surface", "floor") if e else "floor"))
            elif cue.sound in ("impact", "clang", "land"):
                sig = bank[cue.sound](cue.gain)
            else:
                sig = bank[cue.sound]()
            i = int(round(cue.t * SR))
            if i >= n:
                continue
            m = min(len(sig), n - i)
            L[i:i + m] += sig[:m] * (cue.gain if cue.sound not in ("impact", "clang", "land") else 1.0) * 0.6
        L += sy.ambience(duration)
        # rising hum while the mechanism charges (switch activation -> gravity shift), placed from engine events
        acts = [e for e in events if e.type == "switch_activated"]
        for a in acts:
            g = next((e for e in events if e.type == "gravity_shift" and e.t >= a.t), None)
            if g is not None and g.t - a.t > 0.1:
                hum = sy.hum_rise(g.t - a.t + 0.15)
                i = int(round(a.t * SR))
                m = min(len(hum), n - i)
                if m > 0:
                    L[i:i + m] += hum[:m] * 0.25
        if self.music_on:
            L += sy.music(events, duration)
        peak = np.max(np.abs(L)) or 1.0
        L = np.tanh(L / peak * 1.2) * 0.89 / math.tanh(1.2)
        fade = np.ones(n)
        k = _n(0.15)
        fade[-k:] = np.linspace(1, 0, k)
        L *= fade
        st = np.stack([L, L], 1)
        with wave.open(path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((st * 32767).astype("<i2").tobytes())
        return cues
