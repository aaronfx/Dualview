"""Build examples/symbol_run.json: "Symbol Run", the Milestone 2 test film (original, hand-authored).

KAI crosses a world built from symbols and fights RHO with them. Every outcome is decided by the simulation:
- vaults a low minus sign lying across the floor, climbs onto the top bar of a giant pi (hangs from its end,
  pulls up, mantles), runs along it and front-flips off the far end into a landing roll;
- picks up a plus sign and throws it at RHO, who blocks it (the plus glances off and clatters away);
- RHO answers with a flying kick, and KAI steps back out of it;
- KAI picks up a second minus sign and swings it like a staff: RHO goes down (ragdoll), gets up, and they bump fists.

    PYTHONPATH=src python examples/build_symbol_run.py examples/symbol_run.json
"""
import math
import sys

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec
from apex.scene.solver import resolve_cuts

K, R = "kai", "rho"


def project(duration: float = 34.0) -> dict:
    acts = [
        {"character": K, "type": "run_to", "target_x": -900, "speed": 330},
        {"character": K, "type": "vault", "target": "obstacle:minus_floor", "speed": 330},
        {"character": K, "type": "climb", "target": "obstacle:pi"},
        {"character": K, "type": "run_to", "target_x": -236, "speed": 300},
        {"character": K, "type": "jump_to", "target_x": -70, "height": 70, "flip": "front"},
        {"character": K, "type": "roll"},
        {"character": K, "type": "pick_up", "target": "prop:plus"},
        {"character": K, "type": "throw", "target": "char:rho", "power": 0.9},                       # blocked
        {"character": K, "type": "wait_for", "until": "next:strike_start@rho"},
        {"character": K, "type": "dodge", "dodge": "back"},                                          # out of the flying kick
        {"character": K, "type": "pick_up", "target": "prop:staff"},
        {"character": K, "type": "strike", "target": "char:rho", "move": "swing_weapon", "speed": 300},            # knockdown
        {"character": K, "type": "guard", "until": "next:stood_up@rho"},
        {"character": K, "type": "throw", "target": "point:-120,20", "power": 0.6},                  # tosses the staff aside
        {"character": K, "type": "idle", "duration": 0.4},
        {"character": K, "type": "gesture", "target": "char:rho", "gesture": "fist_bump", "distance": 86},
        {"character": K, "type": "idle", "duration": 3.0},
        {"character": R, "type": "wait_for", "until": "next:pick_up@kai"},
        {"character": R, "type": "guard", "until": "next:block_hit@rho"},                            # blocks the plus
        {"character": R, "type": "idle", "duration": 0.3},
        {"character": R, "type": "strike", "target": "char:kai", "move": "flying_kick", "speed": 330},
        {"character": R, "type": "idle", "until": None, "duration": 0.3},
        {"character": R, "type": "wait_for", "until": "next:knockdown@rho"},
        {"character": R, "type": "get_up"},
        {"character": R, "type": "wait_for", "until": "next:gesture_start@kai"},
        {"character": R, "type": "gesture", "target": "char:kai", "gesture": "fist_bump", "distance": 86},
        {"character": R, "type": "idle", "duration": 3.0},
    ]
    acts = [{k: v for k, v in a.items() if v is not None} for a in acts]
    follow = lambda tgt, vh, inc=(), **kw: dict(mode="follow", target=tgt, view_height=vh, offset=[0, 40], lead=0.15, stiffness=4.0,
                                                include=list(inc), **kw)
    shots = [
        dict(id="s1_run", kind="wide", start=0, end=2, description="KAI runs in through the symbols and vaults the minus",
             camera=follow(K, 520)),
        dict(id="s2_climb", kind="medium", start=2, end=4, cut_on="event:climb_start@kai", cut_offset=-0.3,
             description="up onto the bar of the pi: hang, pull up, mantle", camera=follow(K, 440, ["obstacle:pi"])),
        dict(id="s3_flip", kind="wide", start=4, end=6, cut_on="event:climbed@kai", cut_offset=0.2,
             description="along the bar, a front flip off the end, a landing roll", camera=follow(K, 560)),
        dict(id="s4_throw", kind="wide", start=6, end=8, cut_on="event:pick_up@kai", cut_offset=-0.5,
             description="KAI throws the plus; RHO blocks it", camera=follow(K, 520, [f"char:{R}"], shake=1.0)),
        dict(id="s5_kick", kind="medium", start=8, end=10, cut_on="event:strike_start@rho", cut_offset=-0.35,
             description="RHO's flying kick; KAI steps out of it", camera=follow(K, 420, [f"char:{R}"], shake=1.2)),
        dict(id="s6_staff", kind="medium", start=10, end=12, cut_on="event:pick_up@kai", cut_offset=-0.7,
             description="the minus as a staff: RHO goes down", camera=follow(K, 420, [f"char:{R}"], shake=1.4)),
        dict(id="s7_respect", kind="medium", start=12, end=duration, cut_on="event:stood_up@rho", cut_offset=-0.8,
             description="the staff tossed aside; a fist bump", camera=follow(K, 380, [f"char:{R}"]), fade_out=0.9),
    ]
    return {
        "schema_version": "0.1", "id": "symbol_run", "title": "Symbol Run", "fps": 24, "width": 1920, "height": 1080, "seed": 21,
        "characters": [
            {"id": K, "name": "KAI", "strength": 50000,
             "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
             "style": {"body_color": "#ff8a3d", "far_color": "#b3561c", "visor_color": "#fff3d6", "glow_color": "#ffb070",
                       "has_scarf": True, "scarf_color": "#ffd27a", "limb_width": 8.0, "lean_scale": 1.1}},
            {"id": R, "name": "RHO", "strength": 47000,
             "proportions": {"spine": 31, "chest": 29, "head": 23, "thigh": 46, "shin": 43},
             "style": {"body_color": "#e8f0ff", "far_color": "#8a97b0", "visor_color": "#5ee0ff", "glow_color": "#bfe8ff",
                       "has_scarf": False, "limb_width": 7.5, "cadence_scale": 1.05}}],
        "environments": [{
            "id": "symbols", "room": {"width": 2600, "height": 900, "depth_back": 600, "grid_spacing": 130, "entry_door": False},
            "theme": {"accent": "#7f8cff", "alert": "#ff5a8a", "back": "#0d0f1c", "floor": "#090a13", "side": "#0b0c17",
                      "ceiling": "#040408", "background": "#020205", "dust": "#a9b4ff"},
            "gravity": [0, -1568], "dust": 90,
            "obstacles": [
                {"id": "minus_floor", "kind": "glyph", "glyph": "-", "center": [-760, 22], "size": [120, 30], "weight": 30, "color": "#59e3ff"},
                {"id": "pi", "kind": "glyph", "glyph": "π", "center": [-380, 120], "size": [320, 240], "weight": 30, "color": "#ffb347"},
                {"id": "seven", "kind": "glyph", "glyph": "7", "center": [880, 150], "size": [240, 300], "weight": 34, "color": "#c77dff"},
                # floating set dressing, high above the action
                {"id": "root", "kind": "glyph", "glyph": "√", "center": [-980, 600], "size": [240, 170], "weight": 22, "color": "#7f8cff"},
                {"id": "divide", "kind": "glyph", "glyph": "÷", "center": [260, 640], "size": [170, 150], "weight": 22, "color": "#ff7ab8"},
                {"id": "equals", "kind": "glyph", "glyph": "=", "center": [-90, 720], "size": [150, 90], "weight": 18, "color": "#59e3ff"},
            ],
            "props": [
                {"id": "plus", "kind": "glyph", "glyph": "+", "position": [190, 30], "size": [58, 58], "weight": 15, "mass": 6, "angle": 0.785,
                 "color": "#7dffb2", "friction": 0.7},
                {"id": "staff", "kind": "glyph", "glyph": "-", "position": [-150, 8], "size": [118, 16], "weight": 14, "mass": 5,
                 "color": "#59e3ff", "friction": 0.8},
            ]}],
        "scenes": [{"id": "run", "title": "Symbol Run", "environment": "symbols", "duration": duration,
                    "goals": ["vault@kai", "climbed@kai", "flip@kai", "roll_start@kai", "pick_up@kai", "throw@kai", "block_hit@rho",
                              "strike_start@rho", "evaded@kai", "hit@kai[move=swing_weapon]", "knockdown@rho", "stood_up@rho",
                              "fist_bump@kai"],
                    "placements": [{"character": K, "x": -1200, "facing": 1, "z": -10}, {"character": R, "x": 640, "facing": -1, "z": 12}],
                    "actions": acts, "shots": shots}]}


if __name__ == "__main__":
    d = project()
    proj = ProjectSpec.model_validate(d)
    r = SceneRuntime(proj, "run").simulate(physics_only=True)
    bumps = [e.t for e in r.events if e.type == "fist_bump"]
    end = (max(bumps) if bumps else r.duration - 2.6) + 2.6
    d = project(duration=math.ceil(end * 24) / 24)
    proj = resolve_cuts(ProjectSpec.model_validate(d), "run")
    from apex.ai.director import StoryDirector
    StoryDirector._dry_run(proj)  # every goal in order, nobody stuck, sounds exist
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(proj.model_dump_json(indent=1, exclude_defaults=True))
    for s in proj.scenes[0].shots:
        print(f"{s.id:12s} {s.start:6.2f} - {s.end:6.2f}  {s.description}")
