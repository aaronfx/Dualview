"""Build examples/first_exchange.json: "First Exchange", the Milestone 1 combat test film (original, hand-authored).

Two fighters in a dark void trade a choreographed exchange. Every outcome is decided by the simulation:
- a jab blocked by the guard; a cross ducked; a counter-hook that lands (a flinch);
- a front kick dodged by stepping back; a roundhouse ducked;
- an uppercut that staggers; a sweep that takes the feet out, so the body falls as a ragdoll and lands face up or face down;
- a get-up from the floor, then a fist bump.

Characters react to each other's events (`next:` waits), and the shot cuts land on simulated events (`cut_on`).

    PYTHONPATH=src python examples/build_first_exchange.py examples/first_exchange.json
"""
import json
import math
import sys

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec
from apex.scene.solver import resolve_cuts

K, R = "kai", "rho"


def project(duration: float = 22.0) -> dict:
    acts = [
        {"character": K, "type": "walk_to", "target_x": -150, "speed": 140},
        {"character": K, "type": "guard", "duration": 0.7},
        {"character": K, "type": "strike", "target": "char:rho", "move": "jab"},                     # blocked
        {"character": K, "type": "strike", "target": "char:rho", "move": "cross"},                   # ducked
        {"character": K, "type": "wait_for", "until": "next:hurt@kai"},                               # eats the counter-hook (no guard up)
        {"character": K, "type": "strike", "target": "char:rho", "move": "front_kick"},              # dodged back
        {"character": K, "type": "wait_for", "until": "next:strike_start@rho"},
        {"character": K, "type": "dodge", "dodge": "duck"},                                           # under the roundhouse
        {"character": K, "type": "strike", "target": "char:rho", "move": "uppercut", "reaction": "stagger"},
        {"character": K, "type": "strike", "target": "char:rho", "move": "sweep"},                   # knockdown
        {"character": K, "type": "guard", "until": "next:stood_up@rho"},
        {"character": K, "type": "idle", "duration": 0.6},
        {"character": K, "type": "gesture", "target": "char:rho", "gesture": "fist_bump", "distance": 86},              # walks over, offers
        {"character": K, "type": "idle", "duration": 3.0},
        {"character": R, "type": "walk_to", "target_x": 70, "speed": 140},
        {"character": R, "type": "guard", "until": "next:blocked@kai"},                               # blocks the jab
        {"character": R, "type": "wait_for", "until": "next:strike_start@kai"},
        {"character": R, "type": "dodge", "dodge": "duck"},                                           # ducks the cross
        {"character": R, "type": "strike", "target": "char:kai", "move": "hook", "power": 0.55},     # counter
        {"character": R, "type": "wait_for", "until": "next:strike_start@kai"},
        {"character": R, "type": "dodge", "dodge": "back"},                                           # out of the front kick
        {"character": R, "type": "strike", "target": "char:kai", "move": "roundhouse", "power": 1.2},
        {"character": R, "type": "wait_for", "until": "next:knockdown@rho"},                          # uppercut, then swept
        {"character": R, "type": "get_up"},
        {"character": R, "type": "wait_for", "until": "next:gesture_start@kai"},                       # meets it
        {"character": R, "type": "gesture", "target": "char:kai", "gesture": "fist_bump", "distance": 86},
        {"character": R, "type": "idle", "duration": 3.0},
    ]
    follow = lambda tgt, vh, other, **kw: dict(mode="follow", target=tgt, view_height=vh, offset=[0, 30], lead=0.1, stiffness=4.0,
                                               include=[f"char:{other}"], **kw)
    shots = [
        dict(id="s1_void", kind="establishing", start=0, end=2, description="two fighters walk out of the dark and square up",
             camera=dict(mode="dolly", center=[-40, 250], center_end=[-40, 200], view_height=760, view_height_end=560)),
        dict(id="s2_feel_out", kind="medium", start=2, end=4, cut_on="event:strike_start@kai", cut_offset=-0.45,
             description="KAI probes: jab blocked, cross ducked", camera=follow(K, 330, R, shake=1.0)),
        dict(id="s3_counter", kind="medium", start=4, end=6, cut_on="event:strike_start@rho", cut_offset=-0.15,
             description="RHO counters with a hook that lands", camera=follow(K, 330, R, shake=1.2)),
        dict(id="s4_kicks", kind="wide", start=6, end=8, cut_on="event:dodge@rho", cut_offset=-0.2,
             description="kick dodged, roundhouse ducked", camera=follow(K, 420, R, shake=1.0)),
        dict(id="s5_finish", kind="medium", start=8, end=10, cut_on="event:strike_start@kai", cut_offset=-0.2,
             description="uppercut, sweep: RHO goes down hard", camera=follow(K, 380, R, shake=1.4)),
        dict(id="s6_respect", kind="medium", start=10, end=duration, cut_on="event:stood_up@rho", cut_offset=-0.6,
             description="back on his feet; a fist bump", camera=follow(K, 330, R), fade_out=0.9),
    ]
    return {
        "schema_version": "0.1", "id": "first_exchange", "title": "First Exchange", "fps": 24, "width": 1920, "height": 1080, "seed": 11,
        "characters": [
            {"id": K, "name": "KAI", "strength": 50000,
             "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
             "style": {"body_color": "#ff8a3d", "far_color": "#b3561c", "visor_color": "#fff3d6", "glow_color": "#ffb070",
                       "has_scarf": False, "limb_width": 8.0, "lean_scale": 1.1}},
            {"id": R, "name": "RHO", "strength": 47000,
             "proportions": {"spine": 31, "chest": 29, "head": 23, "thigh": 46, "shin": 43},
             "style": {"body_color": "#e8f0ff", "far_color": "#8a97b0", "visor_color": "#5ee0ff", "glow_color": "#bfe8ff",
                       "scarf_color": "#5ee0ff", "has_scarf": True, "limb_width": 7.5, "cadence_scale": 1.05}}],
        "environments": [{
            "id": "void", "room": {"width": 1500, "height": 700, "depth_back": 600, "grid_spacing": 120, "entry_door": False},
            "theme": {"accent": "#38425a", "alert": "#ff5a4a", "back": "#0c0e14", "floor": "#08090d", "side": "#0a0b10",
                      "ceiling": "#030304", "background": "#020203", "dust": "#9fb4d0"},
            "gravity": [0, -1568], "dust": 70}],
        "scenes": [{"id": "exchange", "title": "First Exchange", "environment": "void", "duration": duration,
                    "goals": ["blocked@kai", "evaded@rho", "hurt@kai", "evaded@rho", "evaded@kai", "hurt@rho", "knockdown@rho",
                              "settled@rho", "stood_up@rho", "fist_bump@kai"],
                    "placements": [{"character": K, "x": -400, "facing": 1}, {"character": R, "x": 320, "facing": -1}],
                    "actions": acts, "shots": shots}]}


if __name__ == "__main__":
    d = project()
    proj = ProjectSpec.model_validate(d)
    r = SceneRuntime(proj, "exchange").simulate(physics_only=True)
    end = max(e.t for e in r.events if e.type == "fist_bump") + 2.6
    d = project(duration=math.ceil(end * 24) / 24)
    proj = resolve_cuts(ProjectSpec.model_validate(d), "exchange")
    from apex.ai.director import StoryDirector
    StoryDirector._dry_run(proj)  # every goal in order, nobody stuck, sounds exist
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(proj.model_dump_json(indent=1, exclude_defaults=True))
    for s in proj.scenes[0].shots:
        print(f"{s.id:14s} {s.start:6.2f} - {s.end:6.2f}  {s.description}")
