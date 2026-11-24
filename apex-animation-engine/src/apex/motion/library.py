"""Motion library: reusable, editable key-pose clips with performance parameters.

A clip is authored as a list of KEY POSES (JSON in `motion/clips/`): each key pose names a moment in the action
and sets any subset of the character-agnostic channels below. Channels not set in a key pose are interpolated
from their neighbours. Each key chooses how the curve LEAVES it (`interp`):

  smooth   monotone cubic through the keys (no overshoot between keys)    - default, organic motion
  ease     cubic ease in/out                                              - deliberate moves
  snap     very fast start, long settle (1-(1-u)^4)                       - action after anticipation
  slow_in  slow start, fast finish (u^3)                                  - falling into a pose
  back     overshoots the next key then settles (follow-through)
  linear / hold

Phases (`anticipation`, `action`, `contact`, `follow_through`, `settle`, ...) tag time ranges so a performer can
exaggerate or tone down specific parts. Contacts declare where an effector must touch the world during a window
(e.g. a hand planted on the surface in a hard landing, hands on the knees while catching breath); the animator
enforces them with IK.

Channels are relative to the rig, so a clip plays on any character proportions:
  crouch   pelvis drop as a fraction of standing pelvis height     shift   pelvis shift along the surface (same unit)
  lean / chest / head   torso & head angles (rad, + = forward / down)   twist / hip_twist   shoulder / pelvis twist
  arm_n, arm_f   arm swing from hanging (rad, + = forward)   elbow_n, elbow_f   elbow flexion (rad)
  thigh_n, shin_n, thigh_f, shin_f   free-leg offsets (airborne clips; rad)
  eye   eye opening (1 = neutral)   squash   vertical squash (1 = none)   gaze   gaze weight toward the action target
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

NEUTRAL: Dict[str, float] = {
    "crouch": 0.0, "shift": 0.0, "lean": 0.03, "chest": 0.0, "head": 0.0, "twist": 0.0, "hip_twist": 0.0,
    "arm_n": 0.12, "elbow_n": 0.3, "arm_f": -0.1, "elbow_f": 0.35,
    "thigh_n": 0.0, "shin_n": 0.0, "thigh_f": 0.0, "shin_f": 0.0,
    "eye": 1.0, "squash": 1.0, "gaze": 0.0,
    "fist": 0.0,  # hands: 0 open/relaxed, 1 clenched fists
    "look_back": 0.0,  # > 0.5: the head turns to look behind (over the shoulder)
}
SPATIAL = {"crouch", "shift", "lean", "chest", "head", "twist", "hip_twist", "arm_n", "arm_f", "elbow_n", "elbow_f",
           "thigh_n", "shin_n", "thigh_f", "shin_f"}

# Emotional modifiers (additive channel offsets, faded in) and timing/amplitude scaling. Character-agnostic.
EMOTIONS: Dict[str, Dict[str, float]] = {
    "neutral": {},
    "afraid": {"crouch": 0.05, "lean": -0.04, "head": 0.12, "eye": 0.4, "arm_n": 0.35, "elbow_n": 0.7, "_tempo": 1.1},
    "determined": {"lean": 0.08, "chest": -0.08, "head": -0.06, "eye": 0.05, "_tempo": 1.12, "_intensity": 1.08},
    "relieved": {"crouch": 0.02, "head": 0.08, "eye": -0.1, "_tempo": 0.88},
    "tired": {"crouch": 0.04, "lean": 0.12, "head": 0.2, "arm_n": -0.1, "arm_f": 0.05, "eye": -0.25, "_tempo": 0.78, "_intensity": 0.9},
    "excited": {"chest": -0.1, "head": -0.08, "eye": 0.3, "_tempo": 1.2, "_intensity": 1.15},
    "curious": {"lean": 0.06, "head": -0.05, "eye": 0.15, "_tempo": 0.95},
    "sad": {"crouch": 0.03, "lean": 0.1, "head": 0.3, "arm_n": -0.08, "arm_f": 0.04, "eye": -0.35, "_tempo": 0.72, "_intensity": 0.92},
    "joyful": {"chest": -0.12, "head": -0.14, "eye": 0.35, "_tempo": 1.25, "_intensity": 1.2},
    "embarrassed": {"crouch": 0.02, "head": 0.22, "eye": -0.15, "_tempo": 0.9},
    "scared": {"crouch": 0.07, "lean": -0.06, "head": 0.1, "eye": 0.6, "arm_n": 0.4, "elbow_n": 0.8, "_tempo": 1.2},
}


@dataclass
class Performance:
    """How a clip is performed: the AI Director / animator customises these per request."""
    tempo: float = 1.0  # > 1 = faster
    intensity: float = 1.0  # scales every spatial channel's deviation from neutral
    mirror: bool = False  # swap near/far limbs (e.g. lead with the other arm)
    emotion: str = "neutral"
    anticipation: float = 1.0  # extra scale during phases tagged 'anticipation'
    follow_through: float = 1.0  # extra scale during phases tagged 'follow_through'

    def effective(self) -> Tuple[float, float, Dict[str, float]]:
        emo = dict(EMOTIONS.get(self.emotion, {}))
        tempo = self.tempo * emo.pop("_tempo", 1.0)
        inten = self.intensity * emo.pop("_intensity", 1.0)
        return tempo, inten, emo


@dataclass
class KeyPose:
    t: float
    name: str
    values: Dict[str, float]
    interp: str = "smooth"


@dataclass
class Contact:
    effector: str  # hand_n | hand_f | foot_n | foot_f
    on: str  # "surface" or "joint:<name>"
    t0: float
    t1: float
    s: float = 0.0  # along-surface offset (fraction of stand height, + = facing direction) for "surface"
    h: float = 0.02  # height above the surface (fraction of stand height)
    toward: Optional[str] = None  # for joint targets: slide this fraction toward another joint
    frac: float = 0.0
    blend: float = 0.06  # fade in/out (s)


@dataclass
class MotionClip:
    name: str
    duration: float
    keys: List[KeyPose]
    phases: List[Tuple[str, float, float]] = field(default_factory=list)
    contacts: List[Contact] = field(default_factory=list)
    loop: bool = False
    description: str = ""
    _curves: Dict[str, List[Tuple[float, float, str]]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.keys.sort(key=lambda k: k.t)
        chans = set()
        for k in self.keys:
            chans |= set(k.values)
        for c in chans:
            self._curves[c] = [(k.t, k.values[c], k.interp) for k in self.keys if c in k.values]

    # -------------------------------------------------------------- evaluation
    @staticmethod
    def _seg(u: float, mode: str) -> float:
        if mode == "linear":
            return u
        if mode == "hold":
            return 0.0
        if mode == "ease":
            return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
        if mode == "snap":
            return 1 - (1 - u) ** 4
        if mode == "slow_in":
            return u ** 3
        if mode == "back":
            c1 = 1.70158
            return 1 + (c1 + 1) * (u - 1) ** 3 + c1 * (u - 1) ** 2
        raise ValueError(mode)

    def channel(self, c: str, t: float) -> float:
        pts = self._curves.get(c)
        if not pts:
            return NEUTRAL.get(c, 0.0)
        if self.loop and self.duration > 0:
            t = t % self.duration
        if t <= pts[0][0]:
            return pts[0][1]
        if t >= pts[-1][0]:
            return pts[-1][1]
        i = max(j for j in range(len(pts)) if pts[j][0] <= t)
        (t0, v0, mode), (t1, v1, _) = pts[i], pts[i + 1]
        u = (t - t0) / (t1 - t0)
        if mode != "smooth":
            return v0 + (v1 - v0) * self._seg(u, mode)
        # monotone cubic Hermite (Fritsch-Carlson): smooth through keys without overshooting between them
        def slope(a, b):
            return (pts[b][1] - pts[a][1]) / (pts[b][0] - pts[a][0])
        d = slope(i, i + 1)
        m0 = 0.0 if i == 0 else (0.0 if slope(i - 1, i) * d <= 0 else 2 / (1 / slope(i - 1, i) + 1 / d) if d != 0 else 0.0)
        m1 = 0.0 if i + 2 >= len(pts) else (0.0 if slope(i + 1, i + 2) * d <= 0 else 2 / (1 / slope(i + 1, i + 2) + 1 / d) if d != 0 else 0.0)
        h = t1 - t0
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        return h00 * v0 + h10 * h * m0 + h01 * v1 + h11 * h * m1

    def phase_at(self, t: float) -> Optional[str]:
        for name, a, b in self.phases:
            if a <= t < b:
                return name
        return None

    def sample(self, t: float, perf: Optional[Performance] = None, emotion_fade: float = 0.15) -> Dict[str, float]:
        """Channel values at clip-local time t (seconds of performance time) for a performance."""
        perf = perf or Performance()
        tempo, inten, emo = perf.effective()
        tc = t * tempo
        ph = self.phase_at(tc if not self.loop else tc % self.duration)
        scale = inten * (perf.anticipation if ph == "anticipation" else 1.0) * (perf.follow_through if ph == "follow_through" else 1.0)
        out = {}
        for c in set(self._curves) | set(emo):
            v = self.channel(c, tc)
            if c in SPATIAL:
                v = NEUTRAL.get(c, 0.0) + (v - NEUTRAL.get(c, 0.0)) * scale
            out[c] = v
        w = min(1.0, t / emotion_fade) if emotion_fade > 0 else 1.0
        for c, dv in emo.items():
            out[c] = out.get(c, NEUTRAL.get(c, 0.0)) + dv * w
        if perf.mirror:
            for a, b in (("arm_n", "arm_f"), ("elbow_n", "elbow_f"), ("thigh_n", "thigh_f"), ("shin_n", "shin_f")):
                if a in out or b in out:
                    out[a], out[b] = out.get(b, NEUTRAL[b]), out.get(a, NEUTRAL[a])
        return out

    def key_times(self, perf: Optional[Performance] = None) -> List[Tuple[float, str]]:
        """Named key-pose times in performance time (for pose timelines)."""
        tempo = (perf or Performance()).effective()[0]
        return [(k.t / tempo, k.name) for k in self.keys]

    def length(self, perf: Optional[Performance] = None) -> float:
        return self.duration / (perf or Performance()).effective()[0]


def landing_clip(approach: float) -> Tuple[str, Performance]:
    """Landing performance chosen from the impact speed (shared by the controller's timing and the animator)."""
    if approach > 1100.0:
        return "land_hard", Performance(intensity=min(1.12, max(0.85, approach / 1350.0)))
    return "land_medium", Performance(intensity=min(1.1, max(0.55, approach / 900.0)), tempo=1.15 if approach < 700 else 1.0)


# ------------------------------------------------------------------ loading
_DIR = os.path.join(os.path.dirname(__file__), "clips")
_CACHE: Dict[str, MotionClip] = {}


def clip_from_dict(d: dict) -> MotionClip:
    keys = [KeyPose(float(k["t"]), k.get("name", f"k{i}"), {c: float(v) for c, v in k.get("pose", {}).items()}, k.get("interp", "smooth"))
            for i, k in enumerate(d["keys"])]
    for k in keys:
        unknown = set(k.values) - set(NEUTRAL)
        if unknown:
            raise ValueError(f"clip {d['name']}: unknown channel(s) {sorted(unknown)}")
    contacts = [Contact(**c) for c in d.get("contacts", [])]
    phases = [(p[0], float(p[1]), float(p[2])) for p in d.get("phases", [])]
    return MotionClip(d["name"], float(d["duration"]), keys, phases, contacts, bool(d.get("loop", False)), d.get("description", ""))


def get_clip(name: str) -> MotionClip:
    if name not in _CACHE:
        path = os.path.join(_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise KeyError(f"motion clip '{name}' not found in {_DIR}")
        with open(path, encoding="utf-8") as fh:
            _CACHE[name] = clip_from_dict(json.load(fh))
    return _CACHE[name]


def list_clips() -> List[str]:
    return sorted(os.path.splitext(f)[0] for f in os.listdir(_DIR) if f.endswith(".json"))
