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
        # layered for weight: sub-bass drop, a short crunch transient, and a few debris ticks
        sub = np.sin(2 * np.pi * np.cumsum(55 * (32 / 55) ** (t / d)) / SR) * _env(n, 0.002, 0.25)
        crunch = _norm(_bandpass(self.noise(d), 1800, 7000)) * _env(n, 0.0003, 0.025)
        ticks = np.zeros(n)
        for k in range(5):
            i = _n(0.06 + 0.07 * k + 0.02 * self.rng.random())
            m = min(_n(0.03), n - i)
            ticks[i:i + m] += _norm(_bandpass(self.noise(0.03), 2500, 9000))[:m] * _env(m, 0.0002, 0.006) * (0.5 - 0.08 * k)
        st = clamp01(strength)
        return st * (1.1 * thud + 0.55 * body + 0.9 * sub + 0.45 * crunch * st + 0.35 * ticks) + 0.08 * ring

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

    def slide(self, d: float = 1.0) -> np.ndarray:
        """Body sliding on a metal floor: filtered scrape that decays with the slide."""
        n = _n(d)
        t = _t(d)
        scrape = _norm(_bandpass(self.noise(d), 700, 5000)) * (1 - t / d) ** 1.5 * np.minimum(1, t / 0.03)
        rumble = _norm(_bandpass(self.noise(d), 80, 400)) * (1 - t / d) * 0.6
        return 0.45 * scrape + 0.35 * rumble

    def strain(self, d: float = 0.9) -> np.ndarray:
        """Effort: a breathy, low exhale under load (no voice), with a trembling envelope."""
        n = _n(d)
        t = _t(d)
        env = np.minimum(1, t / 0.12) * (1 - t / d) ** 0.7 * (1 + 0.25 * np.sin(2 * np.pi * 9 * t))
        return 0.35 * _norm(_bandpass(self.noise(d), 250, 1800)) * env

    def snap(self) -> np.ndarray:
        """A strap snapping: a sharp crack, then the torn ends whipping away."""
        d = 0.45
        n = _n(d)
        t = _t(d)
        crack = _norm(_bandpass(self.noise(d), 1500, 11000)) * np.exp(-t / 0.012)
        whip = 0.4 * _norm(_bandpass(self.noise(d), 400, 3000)) * np.exp(-t / 0.12) * np.minimum(1, t / 0.02)
        return 1.0 * crack + whip

    def creak(self, d: float = 0.8) -> np.ndarray:
        """Steel under load / a lever biting: low ratchet clicks over a groan."""
        n = _n(d)
        t = _t(d)
        clicks = np.zeros(n)
        for k in range(int(d / 0.07)):
            i = int(k * 0.07 * SR)
            m = min(n - i, _n(0.02))
            clicks[i:i + m] += np.exp(-np.arange(m) / (0.004 * SR))
        groan = np.sin(2 * np.pi * np.cumsum(70 + 25 * np.sin(2 * np.pi * 1.3 * t)) / SR) * (1 - t / d)
        return 0.35 * _norm(_bandpass(clicks + 0.02 * self.noise(d), 600, 4000)) + 0.25 * groan

    def tap(self) -> np.ndarray:
        """Soft contact (hands meeting, a fist bump)."""
        d = 0.18
        t = _t(d)
        return 0.6 * _norm(_bandpass(self.noise(d), 200, 1800)) * np.exp(-t / 0.02)

    def clank(self) -> np.ndarray:
        """Hands slamming onto a steel rail: short metallic ring."""
        d = 0.7
        n = _n(d)
        t = _t(d)
        ring = sum(a * np.sin(2 * np.pi * f * t) for f, a in [(523, 1.0), (1187, 0.7), (1873, 0.45), (2741, 0.3)]) * _env(n, 0.001, 0.12)
        return 0.6 * ring + 0.5 * _norm(_bandpass(self.noise(d), 2000, 9000)) * _env(n, 0.001, 0.03)

    def unlock(self) -> np.ndarray:
        """Seal bars retracting: three mechanical clicks and a rising major third."""
        out = np.zeros(_n(1.4))
        for k in range(3):
            c = self.click()
            i = _n(0.12 * k)
            out[i:i + len(c)] += 0.7 * c[:len(out) - i]
        ch = self.chime((587.3, 740.0, 880.0), 0.1, 0.5)
        i = _n(0.4)
        m = min(len(ch), len(out) - i)
        out[i:i + m] += 0.8 * ch[:m]
        return out

    def door(self) -> np.ndarray:
        """Door sliding open: pneumatic hiss + soft whoosh of outside air."""
        d = 1.2
        n = _n(d)
        t = _t(d)
        hiss = _norm(_bandpass(self.noise(d), 3000, 12000)) * _env(n, 0.02, 0.35)
        return 0.35 * hiss + 0.4 * self.whoosh(d, 200, 900)[:n]

    def resolve(self) -> np.ndarray:
        """Final arrival: bright open D-major bell chord."""
        return 0.9 * self.chime((293.7, 440.0, 587.3, 740.0, 880.0), 0.07, 0.9)

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
        if not first.get("switch_activated") and (first.get("push_lost") or first.get("pinned")):
            # a rescue: tension from the moment control is lost, release when the trapped character is free,
            # full resolution once they stand again
            t_act = (first.get("push_lost") or first.get("pinned"))[0]
            t_free = (first.get("freed") or first.get("load_off") or [duration])[-1] if first.get("freed") else duration
            t_up = (first.get("stood_up") or [duration])[0]
            seg = lambda freqs, a, b: 0.0
            n = _n(duration)
            t = np.arange(n) / SR

            def pad2(freqs, a, b):
                out = np.zeros(n)
                m = (t >= a) & (t < b + 1.0)
                if not m.any():
                    return out
                tt = t[m] - a
                env = np.minimum(1, tt / 0.6) * np.clip((b + 1.0 - t[m]) / 1.0, 0, 1)
                out[m] = sum(np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt) for f in freqs) / len(freqs) * env
                return out
            out = 0.5 * pad2((73.4, 110.0, 146.8, 174.6), 0.0, t_act)
            out += 0.65 * pad2((73.4, 103.8, 146.8, 155.6), t_act, t_free)
            out += 0.5 * pad2((73.4, 110.0, 146.8, 185.0), t_free, t_up)
            out += 0.7 * pad2((73.4, 110.0, 146.8, 185.0, 220.0, 293.7), t_up, duration)
            return out * 0.05
        acts = first.get("switch_activated") or [duration]
        t_act = acts[0]
        t_rec = next((x for x in (first.get("recovered") or []) if x > t_act), duration)
        notices = first.get("notice") or []
        t_res = next((x for x in notices if x > t_rec), duration)
        t_act2 = acts[1] if len(acts) > 1 else duration  # second switch: tension returns
        t_rec2 = next((x for x in (first.get("recovered") or []) if x > t_act2 + 1.0), duration)
        t_exit = (first.get("exit_reached") or [duration])[0]

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
        out += 0.55 * pad((73.4, 110.0, 146.8, 185.0, 220.0), t_res, min(duration, t_act2))  # D major lift: a way out
        if t_act2 < duration:
            out += 0.6 * pad((77.8, 110.0, 155.6, 164.8), t_act2, t_rec2)  # tension again: the room turns over
            out += 0.5 * pad((73.4, 110.0, 146.8, 185.0), t_rec2, t_exit)  # hope: the door is open
            out += 0.7 * pad((73.4, 110.0, 146.8, 185.0, 220.0, 293.7), t_exit, duration)  # arrival: full D major
        return out * 0.05

    def beat_track(self, music, duration: float) -> np.ndarray:
        """A beat-locked groove (Milestone 4): a kick on every beat, a closed hat on the off-beats, a bass note that
        changes each bar. Every onset is placed exactly on the film-time beat grid (QA measures them back)."""
        n = _n(duration)
        out = np.zeros(n)
        P = 60.0 / music.bpm
        kick = kick_wave()
        kick_n = len(kick)
        hat = _bandpass(self.rng.standard_normal(_n(0.05)), 6000, None) * np.exp(-np.arange(_n(0.05)) / SR * 70.0)
        roots = (55.0, 55.0, 65.4, 49.0)  # A A C G: one note per bar
        k = 0
        while True:
            tb = music.offset + k * P
            if tb >= duration:
                break
            i = int(round(tb * SR))
            m = min(kick_n, n - i)
            out[i:i + m] += 0.9 * kick[:m]
            j = int(round((tb + P / 2) * SR))
            if j < n:
                mh = min(len(hat), n - j)
                out[j:j + mh] += 0.25 * hat[:mh]
            if k % music.beats_per_bar == 0:
                bar_n = min(_n(P * music.beats_per_bar), n - i)
                tt = np.arange(bar_n) / SR
                fr = roots[(k // music.beats_per_bar) % len(roots)]
                out[i:i + bar_n] += 0.22 * (np.sin(2 * np.pi * fr * tt) + 0.35 * np.sin(4 * np.pi * fr * tt)) * np.exp(-tt * 1.2)
            k += 1
        return out * 0.32 * music.gain

    def ambience(self, duration: float) -> np.ndarray:
        n = _n(duration)
        t = np.arange(n) / SR
        a = 0.05 * np.sin(2 * np.pi * 50 * t) + 0.03 * np.sin(2 * np.pi * 100.3 * t)
        a += 0.04 * _norm(_bandpass(self.rng.standard_normal(n), 40, 260))
        return a * np.minimum(1, t / 0.3)


def kick_wave() -> np.ndarray:
    """The beat track's kick: a pitch-dropping sine (130 -> 45 Hz) with a 3 ms attack (QA matches against it)."""
    kick_n = _n(0.22)
    tk = np.arange(kick_n) / SR
    f = 45.0 + 85.0 * np.exp(-tk * 30.0)
    kick = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tk * 16.0)
    kick[: _n(0.003)] *= np.linspace(0, 1, _n(0.003))
    return kick


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


DEFAULT_BINDINGS = {
    "footstep": "footstep", "press_contact": "click", "gravity_shift": "pulse", "lost_support": "whoosh",
    "impact": "impact", "prop_impact": "clang", "takeoff": "jump", "recovered": None, "brace": None,
    "switch_activated": "startle", "notice": "notice", "point": "chime",
    "slide_start": "slide", "grab": "clank", "release": None, "door_unlocking": "unlock", "door_open": "door", "exit_reached": "resolve",
    "graze": None, "slide_end": None, "grab_missed": None, "door_unlocked": None,
    # physical interaction
    "push_start": "strain", "push_lost": "slide", "rope_taut": "clank", "rope_snap": "snap", "body_fall": "impact",
    "lift_start": "strain", "lift_fail": "clang", "pick_up": "clank", "lever_place": "clank", "lever_engage": "creak",
    "lever_release": "clang", "crawl_start": "slide", "hand_grab": "tap", "fist_bump": "tap", "shoulder_pat": "tap",
    "stood_up": "resolve", "pinned": None, "load_off": None, "freed": None, "get_up_start": None, "hand_offered": None,
    "push_end": None, "push_fail": None, "lift_ok": None, "wave": None,
    # combat
    "swing": "whoosh", "hit": "impact", "block_hit": "clang", "dodge": "whoosh", "strike_start": None, "hurt": None,
    "blocked": None, "whiff": None, "evaded": None, "knockdown": None, "settled": None,
    # acrobatics and symbols
    "flip": "whoosh", "roll_start": "slide", "roll_end": None, "vault": "tap", "vault_start": None, "ledge_grab": "clank",
    "climb_start": None, "climbed": "footstep", "step_off": None, "wall_run": None, "wall_contact": "footstep", "wall_kick": "whoosh",
    "throw_start": None, "throw": "whoosh", "prop_hit": "clang", "bump": "tap",
    "slowmo": "whoosh", "body_block": None, "prop_blocked": "clang",
    # orbs, portals, beats (Milestone 4)
    "orb_jump": "jump", "orb_boost": "whoosh", "orb_pad": "jump", "collect": "chime", "portal_enter": "pulse", "portal_exit": None,
    "beat_wait_end": None,
}


@dataclass
class Cue:
    t: float
    event_type: str
    sound: str
    gain: float


SOUND_NAMES = ("footstep", "click", "pulse", "whoosh", "impact", "clang", "jump", "notice", "startle", "chime", "slide",
               "clank", "unlock", "door", "resolve", "land", "strain", "snap", "creak", "tap")


class SoundDirector:
    def __init__(self, seed: int = 7, bindings: Optional[Dict[str, Optional[str]]] = None, music: bool = True,
                 samples: bool = True):
        self.synth = Synth(seed)
        self.music_on = music
        # recorded, freely licensed samples (audio/sfx, see CREDITS.md) layered over the synthesiser when available
        self.samples = None
        if samples:
            from .samples import SampleBank
            bank = SampleBank(SR, seed)
            self.samples = bank if bank.ok else None
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
                elif e.type in ("impact", "prop_impact", "body_fall"):
                    gain = 0.4 + 0.6 * clamp01(e.data.get("normal_speed", 600) / 1200)
                elif e.type == "hit":
                    gain = 0.7 + 0.6 * clamp01(e.data.get("power", 1.0) / 1.6)
                elif e.type == "swing":
                    gain = 0.45
                elif e.type == "dodge":
                    gain = 0.3
                elif e.type == "block_hit":
                    gain = 0.8
                elif e.type == "slowmo":
                    gain = 0.3
                elif e.type in ("flip", "wall_kick", "throw"):
                    gain = 0.5
                elif e.type == "prop_hit":
                    gain = 0.5 + 0.5 * clamp01(e.data.get("normal_speed", 800) / 1200)
                elif e.type in ("roll_start", "wall_contact", "climbed", "vault"):
                    gain = 0.55
                cues.append(Cue(e.t, e.type, snd, gain))
        return cues

    def render(self, events, duration: float, path: str, music=None) -> List[Cue]:
        """`music`: a MusicSpec; the beat-locked groove replaces the adaptive score bed."""
        n = _n(duration)
        L = np.zeros(n)
        Rch = np.zeros(n)  # sound effects are panned by where they happen in the room
        cues = self.cues_for(events)
        sy = self.synth
        bank: Dict[str, Callable[..., np.ndarray]] = {"footstep": sy.footstep, "click": sy.click, "pulse": sy.pulse, "whoosh": sy.whoosh,
                                                       "impact": sy.impact, "clang": sy.clang, "jump": sy.jump, "notice": sy.notice,
                                                       "startle": sy.startle, "chime": sy.chime, "slide": sy.slide, "clank": sy.clank,
                                                       "unlock": sy.unlock, "door": sy.door, "resolve": sy.resolve,
                                                       "strain": sy.strain, "snap": sy.snap, "creak": sy.creak, "tap": sy.tap}
        bank["land"] = bank["impact"]
        unknown = sorted({c.sound for c in cues} - set(bank))
        if unknown:
            raise ValueError(f"unknown sound(s) {unknown}; available: {sorted(bank)}")
        ev_by_t = {(round(e.t, 6), e.type): e for e in events}
        for ci, cue in enumerate(cues):
            e = ev_by_t.get((round(cue.t, 6), cue.event_type))
            if cue.sound == "footstep":
                sig = sy.footstep(1.0, (e.data.get("surface", "floor") if e else "floor"))
            elif cue.sound in ("impact", "clang", "land"):
                sig = bank[cue.sound](cue.gain)
            else:
                sig = bank[cue.sound]()
            name = "door_close" if cue.event_type == "door_close" else cue.sound
            if self.samples is not None and self.samples.has(name):
                rec = self.samples.render(name, ci, intensity=cue.gain if cue.sound in ("impact", "clang", "land") else 1.0)
                if cue.sound in ("impact", "clang", "land"):
                    rec = rec * cue.gain  # the synthesised impact already carries its strength
                mix = self.samples.synth_mix(name)
                m0 = max(len(rec), len(sig))
                sig = np.pad(rec, (0, m0 - len(rec))) + mix * np.pad(sig, (0, m0 - len(sig)))
            i = int(round(cue.t * SR))
            if i >= n:
                continue
            m = min(len(sig), n - i)
            amp = sig[:m] * (cue.gain if cue.sound not in ("impact", "clang", "land") else 1.0) * 0.6
            pt = e.data.get("point") if e is not None else None
            pan = max(-0.7, min(0.7, pt[0] / 700.0)) if isinstance(pt, (tuple, list)) else 0.0
            L[i:i + m] += amp * math.sqrt(0.5 * (1 - pan))
            Rch[i:i + m] += amp * math.sqrt(0.5 * (1 + pan))
        # short synthetic room reverb on the effects bus (metal chamber: ~0.7 s decay, 14 % wet)
        ir_n = _n(0.7)
        ir = self.synth.rng.standard_normal(ir_n) * np.exp(-np.arange(ir_n) / SR / 0.16)
        ir = _bandpass(ir, 200, 6000) / (np.sqrt(np.sum(ir ** 2)) + 1e-9)
        N = 1 << int(np.ceil(np.log2(n + ir_n)))
        IR = np.fft.rfft(ir, N)
        L = L + 0.14 * np.fft.irfft(np.fft.rfft(L, N) * IR, N)[:n]
        Rch = Rch + 0.14 * np.fft.irfft(np.fft.rfft(Rch, N) * IR, N)[:n]
        bed = sy.ambience(duration)
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
                    Rch[i:i + m] += hum[:m] * 0.25
        if music is not None:
            groove = sy.beat_track(music, duration)
            L, Rch = L + groove, Rch + groove  # on the effects bus level, so it survives the final normalisation
        elif self.music_on:
            bed = bed + sy.music(events, duration)
        L = L + bed
        Rch = Rch + bed
        if self.samples is not None:  # recorded room tone, offset between channels for width
            tl, tr = self.samples.room_tone(n, 0.0), self.samples.room_tone(n, 3.7)
            if tl is not None:
                L, Rch = L + tl, Rch + tr
        peak = max(np.max(np.abs(L)), np.max(np.abs(Rch))) or 1.0
        L = np.tanh(L / peak * 1.2) * 0.89 / math.tanh(1.2)
        Rch = np.tanh(Rch / peak * 1.2) * 0.89 / math.tanh(1.2)
        fade = np.ones(n)
        k = _n(0.15)
        fade[-k:] = np.linspace(1, 0, k)
        L *= fade
        Rch *= fade
        st = np.stack([L, Rch], 1)
        with wave.open(path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((st * 32767).astype("<i2").tobytes())
        return cues
