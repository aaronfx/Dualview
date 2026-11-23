"""Build an original short performance benchmark: 'The Threshold'.

Intent -> recoil -> conscious choice -> weight-bearing run -> physical leap ->
landing absorb -> pick up the goal -> tiny celebration. Real APEX physics,
joint/foot QA and event-derived cuts: no hand-drawn fake keyframe collisions.

Commands:
    python examples/build_motion_performance_probe.py out/threshold.json
    apex render out/threshold.json -o out/threshold.mp4 --scale 0.75 --qa-json out/threshold.qa.json

This is a benchmark for engineering and artistic review, not proof of
reference-quality animation. Visual and human judgement remain essential.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def project(duration=18.0, shots=None):
    return {
        "schema_version": "0.1", "id": "threshold_performance",
        "title": "The Threshold — an original motion-quality exercise",
        "fps": 24, "width": 1280, "height": 720, "seed": 84,
        "characters": [
            {"id": "iko", "name": "IKO", "strength": 52000,
             "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
             "style": {
                 "body_color": "#ffd04e", "far_color": "#a87925",
                 "visor_color": "#8ffaff", "glow_color": "#ffdc78",
                 "has_scarf": True, "scarf_color": "#ff648b",
                 "limb_width": 8.2, "cadence_scale": 1.04,
                 "lean_scale": 1.10}}
        ],
        "environments": [{
            "id": "threshold_room",
            "room": {"width": 1550, "height": 920,
                     "depth_back": 460, "entry_door": False, "grid_spacing": 180},
            "gravity": [0, -1568], "dust": 38,
            "theme": {"accent": "#63d6ef", "alert": "#ff648b",
                      "back": "#151b29", "floor": "#111722",
                      "side": "#121825", "ceiling": "#0a0e18",
                      "background": "#070a12", "dust": "#79b5cb"},
            "obstacles": [
                {"id": "threshold", "kind": "platform", "center": [-10, 32],
                 "size": [100, 64], "color": "#e36585", "style": "slab"}
            ],
            "props": [{
                "id": "spark", "kind": "glyph", "glyph": "+",
                "position": [445, 25], "size": [43, 43],
                "weight": 12, "mass": 2.2, "energy": True,
                "color": "#76f2df", "friction": 0.9
            }]
        }],
        "scenes": [{
            "id": "crossing", "title": "See, doubt, commit, leap, recover",
            "environment": "threshold_room", "duration": duration,
            "placements": [{"character": "iko", "x": -575, "facing": 1}],
            "goals": ["notice@iko", "act@iko[clip=doubt_to_dash]",
                      "takeoff@iko", "impact@iko", "act@iko[clip=impact_to_grin]",
                      "pick_up@iko[prop=spark]"],
            "time_fx": {"hit_stop": False, "screen_fx": True, "smears": True,
                        "punch_in": False},
            "score": {"key": "D", "level": 0.40, "cues": [
                {"at": 0.0, "mood": "tension"},
                {"on": "takeoff@iko", "mood": "action"},
                {"on": "pick_up@iko", "mood": "triumph"}]},
            "actions": [
                {"character": "iko", "type": "notice", "target": "point:-10,80", "duration": 0.80},
                {"character": "iko", "type": "act", "clip": "doubt_to_dash",
                 "emotion": "afraid", "intensity": 1.02, "tempo": 1.0},
                {"character": "iko", "type": "run_to", "target_x": -205, "speed": 405},
                {"character": "iko", "type": "jump_to", "target_x": 185, "height": 170},
                {"character": "iko", "type": "act", "clip": "impact_to_grin",
                 "emotion": "relieved", "intensity": 1.0},
                {"character": "iko", "type": "run_to", "target_x": 385, "speed": 310},
                {"character": "iko", "type": "pick_up", "target": "prop:spark"},
                {"character": "iko", "type": "act", "clip": "cheer", "emotion": "joyful",
                 "intensity": 0.74, "tempo": 0.95},
                {"character": "iko", "type": "idle", "duration": 1.4}
            ],
            "shots": shots or [
                {"id": "preview", "kind": "wide", "start": 0, "end": duration,
                 "camera": {"mode": "static", "center": [-10, 210], "view_height": 690}}
            ]
        }]
    }


def _event_times(sim):
    events = {}
    for e in sim.events:
        events.setdefault((e.type, e.character), []).append(e.t)
    return events


def shots_for(events, duration):
    def at(name):
        matches = events.get((name, "iko"), [])
        if not matches:
            raise ValueError(f"motion benchmark: physics did not produce {name}@iko")
        return matches[0]

    takeoff, landing, pickup = at("takeoff"), at("impact"), at("pick_up")
    if not (1.0 < takeoff < landing < pickup < duration - 0.4):
        raise ValueError(f"unexpected event order takeoff={takeoff:.2f}, impact={landing:.2f}, pick_up={pickup:.2f}")
    # The establishing insert proves the visible obstacle and goal *before*
    # the acting close-up; the action and landing remain event-timed.
    edges = [0.0, 0.76, round(takeoff - 0.28, 3),
             round(landing + 0.20, 3), round(pickup - 0.24, 3), duration]
    if min(b - a for a, b in zip(edges, edges[1:])) < 0.55:
        raise ValueError(f"storyboard edits made a shot unreadably short: {edges}")
    descriptions = [
        ("01_establish", "establishing", "one original world: IKO, a solid threshold, and a glowing reward",
         {"mode": "static", "center": [-25, 235], "view_height": 720,
          "keep_in_frame": False}),
        ("02_choice", "medium", "IKO sees the threshold, recoils, and chooses to cross",
         {"mode": "static", "center": [-390, 195], "view_height": 440,
          "include": ["obstacle:threshold"]}),
        ("03_leap", "wide", "the committed jump must clear the actual slab",
         {"mode": "follow", "target": "iko", "view_height": 500, "lead": 0.28,
          "offset": [55, 45], "stiffness": 3.8,
          "include": ["obstacle:threshold"]}),
        ("04_weight", "medium", "the body absorbs its landing and takes a breath",
         {"mode": "follow", "target": "iko", "view_height": 370,
          "lead": 0.14, "offset": [35, 40], "stiffness": 3.8}),
        ("05_reward", "medium", "the reward is physical: IKO picks up a live glyph",
         {"mode": "follow", "target": "iko", "view_height": 330,
          "lead": 0.1, "offset": [0, 35], "stiffness": 4.1,
          "include": ["prop:spark"]})
    ]
    out = []
    for i, (sid, kind, desc, camera) in enumerate(descriptions):
        out.append({"id": sid, "kind": kind, "description": desc,
                    "start": edges[i], "end": edges[i+1], "camera": camera,
                    "sound_cues": [
                        {"on_event": "takeoff", "sound": "jump", "gain": 0.9},
                        {"on_event": "impact", "sound": "land", "gain": 1.25},
                        {"on_event": "pick_up", "sound": "chime", "gain": 0.9}
                    ] if i > 0 else []})
    out[-1]["fade_out"] = 0.6
    return out


def build():
    base = ProjectSpec.model_validate(project())
    sim = SceneRuntime(base, "crossing").simulate(physics_only=True)
    events = _event_times(sim)
    clip_acts = [e for e in sim.events if e.type == "act" and e.character == "iko"]
    for clip in ("doubt_to_dash", "impact_to_grin", "cheer"):
        if not any(e.data.get("clip") == clip for e in clip_acts):
            raise ValueError(f"motion benchmark missed act clip {clip}")
    ptime = events.get(("pick_up", "iko"), [])
    if not ptime:
        raise ValueError("physics did not let IKO reach and pick up the energy glyph")
    duration = math.ceil((ptime[0] + 2.20) * base.fps) / base.fps
    if duration > 17.0:
        raise ValueError(f"motion test is excessively long: {duration:.2f}s")
    d = project(duration=duration, shots=shots_for(events, duration))
    return ProjectSpec.model_validate(d), events


if __name__ == "__main__":
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else "out/threshold_performance.json")
    dst.parent.mkdir(parents=True, exist_ok=True)
    p, events = build()
    from apex.ai.director import StoryDirector
    StoryDirector._dry_run(p)
    dst.write_text(p.model_dump_json(indent=2, exclude_defaults=True), encoding="utf-8")
    print(f"wrote {dst} for {p.scenes[0].duration:.2f}s")
    for sh in p.scenes[0].shots:
        print(f"  {sh.id:16s} {sh.start:5.2f}-{sh.end:5.2f}: {sh.description}")
    print("causal events:", {k[0]: [round(t, 3) for t in ts]
                             for k, ts in events.items()
                             if k[1] == "iko" and k[0] in ("notice", "takeoff", "impact", "pick_up")})
