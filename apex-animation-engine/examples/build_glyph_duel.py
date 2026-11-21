"""Build examples/glyph_duel.json: "Glyph Duel", the Milestone 2 acceptance film (original, hand-authored).

One continuous fight that chains every Milestone 2 capability with combat. Every outcome is decided by the simulation:
1. KAI and RHO square up. KAI's jab is blocked. RHO's roundhouse is answered with a **back flip** (airborne: the kick
   whiffs), and KAI lands straight into his guard.
2. RHO presses with a cross; KAI **rolls under it**, into the near depth lane, and passes in front of him (the bodies
   never intersect: QA `body_clearance` measures it in 3D, with no exemptions).
3. KAI **climbs** the giant pi, crosses its bar and **picks up** a times sign resting on it, then **throws** it down at RHO:
   falling from the bar it gathers speed, and the impulse knocks RHO down.
4. He **front-flips** off the bar and lands in his guard; as RHO gets up, a **flying kick** (blocked); he ducks the
   counter-hook.
5. He picks up a minus sign and **fights with it**: the first swing is dodged, the second lands. Then he **throws** it:
   RHO goes down (ragdoll), gets up, and they bump fists.

    PYTHONPATH=src python examples/build_glyph_duel.py examples/glyph_duel.json
"""
import math
import sys

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec
from apex.scene.solver import resolve_cuts

K, R = "kai", "rho"


def project(duration: float = 50.0) -> dict:
    k = lambda **a: dict(character=K, **a)
    r = lambda **a: dict(character=R, **a)
    acts = [
        # 1. square up, jab blocked, back flip over the roundhouse
        k(type="walk_to", target_x=-240, speed=150), k(type="guard", duration=0.4),
        k(type="strike", target="char:rho", move="jab", distance=116),  # from the edge of reach: the guard stops it
        k(type="wait_for", until="next:strike_start@rho"),
        k(type="jump_to", target_x=-470, height=110, flip="back"),
        k(type="guard", until="next:strike_start@rho"),
        # 2. roll under the cross, past him
        k(type="roll", distance=300, lane=-50),  # into the near lane: passes in front of RHO, not through him
        # 3. climb the pi, take the times sign from its bar, throw it down at RHO
        k(type="run_to", target_x=440, speed=320, lane=-14),
        k(type="climb", target="obstacle:pi"),
        k(type="pick_up", target="prop:times"),
        k(type="throw", target="char:rho", power=0.6),
        # 4. front flip off the bar into a flying kick; duck the counter
        k(type="jump_to", target_x=380, height=80, flip="front"),
        k(type="guard", until="next:stood_up@rho"),
        k(type="strike", target="char:rho", move="flying_kick", speed=320),
        k(type="wait_for", until="next:strike_start@rho"),
        k(type="dodge", dodge="duck"),
        # 5. the minus sign as a staff: dodged, then lands; then thrown
        k(type="pick_up", target="prop:staff"),
        k(type="strike", target="char:rho", move="swing_weapon", speed=300),
        k(type="strike", target="char:rho", move="swing_weapon", reaction="stagger"),
        k(type="throw", target="char:rho", power=1.3),
        k(type="guard", until="next:stood_up@rho"),
        k(type="idle", duration=0.4),
        k(type="gesture", target="char:rho", gesture="fist_bump", distance=86),
        k(type="idle", duration=3.0),
        # RHO
        r(type="guard", until="next:block_hit@rho"),
        r(type="idle", duration=0.25),
        r(type="strike", target="char:kai", move="roundhouse", power=1.2),
        r(type="idle", duration=0.3),
        r(type="strike", target="char:kai", move="cross", speed=320),
        r(type="wait_for", until="next:roll_end@kai"),
        r(type="turn", face=1),
        r(type="walk_to", target_x=230, speed=150),
        r(type="look_at", target="point:640,300", duration=0.4),
        r(type="wait_for", until="next:hurt@rho"),
        r(type="guard", until="next:block_hit@rho"),
        r(type="idle", duration=0.75),
        r(type="strike", target="char:kai", move="hook", power=0.8, distance=112),
        r(type="wait_for", until="next:pick_up@kai"),
        r(type="guard", duration=0.2),
        r(type="wait_for", until="next:strike_start@kai"),
        r(type="dodge", dodge="back"),
        r(type="wait_for", until="next:knockdown@rho"),
        r(type="get_up"),
        r(type="wait_for", until="next:gesture_start@kai"),
        r(type="gesture", target="char:kai", gesture="fist_bump", distance=86),
        r(type="idle", duration=3.0),
    ]
    follow = lambda tgt, vh, inc=(), **kw: dict(**{**dict(mode="follow", target=tgt, view_height=vh, offset=[0, 40], lead=0.12,
                                                         stiffness=4.0, include=list(inc)), **kw})
    both = [f"char:{R}"]
    # deliberate shot scales: wide to establish and for travel, medium two-shots for exchanges, close shots only where
    # a detail carries the story (the pick-up of the symbol, the reconciliation)
    shots = [
        dict(id="s01_arena", kind="wide", start=0, end=2, description="the arena: they square up, the pi looms",
             camera=follow(K, 620, both + ["obstacle:pi"], stiffness=2.5)),
        dict(id="s02_jab", kind="medium", start=2, end=4, cut_on="event:strike_start@kai", cut_offset=-0.45,
             description="two-shot: the jab is blocked", camera=follow(K, 360, both, shake=1.0)),
        dict(id="s03_flip", kind="wide", start=4, end=6, cut_on="event:strike_start@rho", cut_offset=-0.3,
             description="the roundhouse; KAI back-flips over it (tracked through the air) and lands in guard",
             camera=follow(K, 520, both, shake=1.0)),
        dict(id="s04_roll", kind="medium", start=6, end=8, cut_on="event:roll_start@kai", cut_offset=-0.5,
             description="low two-shot: the cross; KAI rolls under it, in front of RHO", camera=follow(K, 400, both, offset=[0, 5], shake=1.0)),
        dict(id="s05_climb", kind="wide", start=8, end=10, cut_on="event:climb_start@kai", cut_offset=-0.6,
             description="up the pi", camera=follow(K, 560, ["obstacle:pi"])),
        dict(id="s06_pick", kind="close", start=10, end=12, cut_on="event:pick_up@kai", cut_offset=-0.45,
             description="close: he takes the times sign from the bar", camera=follow(K, 230, focus="upper", stiffness=3.0)),
        dict(id="s07_throw", kind="wide", start=12, end=14, cut_on="event:throw_start@kai", cut_offset=-0.15,
             description="wide: thrown down at RHO", camera=dict(mode="static", center=[470, 250], view_height=640, shake=1.0)),
        dict(id="s08_dive", kind="wide", start=14, end=16, cut_on="event:flip@kai", cut_offset=-0.25,
             description="the front flip off the bar, tracked down", camera=follow(K, 560, both, shake=1.2)),
        dict(id="s09_kick", kind="medium", start=16, end=18, cut_on="event:strike_start@kai[move=flying_kick]", cut_offset=-0.4,
             description="two-shot: flying kick blocked, the hook ducked", camera=follow(K, 400, both, shake=1.2)),
        dict(id="s10_staff", kind="medium", start=18, end=20, cut_on="event:pick_up@kai", cut_offset=-0.8,
             description="the minus sign as a staff", camera=follow(K, 380, both, shake=1.3)),
        dict(id="s11_down", kind="medium", start=20, end=22, cut_on="event:throw_start@kai", cut_offset=-0.3,
             description="thrown: RHO goes down (the camera closes in on the blow)", camera=follow(K, 460, both, shake=1.4)),
        dict(id="s12_respect", kind="close", start=22, end=duration, cut_on="event:stood_up@rho", cut_offset=-0.8,
             description="he gets up; a fist bump, framed close", camera=follow(K, 330, both), fade_out=0.9),
    ]
    return {
        "schema_version": "0.1", "id": "glyph_duel", "title": "Glyph Duel", "fps": 24, "width": 1920, "height": 1080, "seed": 31,
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
                {"id": "pi", "kind": "glyph", "glyph": "π", "center": [650, 120], "size": [320, 240], "weight": 30, "color": "#ffb347"},
                # floating set dressing, high above the action
                {"id": "root", "kind": "glyph", "glyph": "√", "center": [-760, 620], "size": [240, 170], "weight": 22, "color": "#7f8cff"},
                {"id": "divide", "kind": "glyph", "glyph": "÷", "center": [120, 690], "size": [170, 150], "weight": 22, "color": "#ff7ab8"},
                {"id": "seven", "kind": "glyph", "glyph": "7", "center": [1050, 640], "size": [150, 200], "weight": 22, "color": "#c77dff"},
            ],
            "props": [
                {"id": "times", "kind": "glyph", "glyph": "x", "position": [740, 252], "size": [46, 46], "weight": 13, "mass": 5,
                 "color": "#7dffb2", "friction": 0.9},
                {"id": "staff", "kind": "glyph", "glyph": "-", "position": [430, 8], "size": [118, 16], "weight": 14, "mass": 5,
                 "color": "#59e3ff", "friction": 0.8},
            ]}],
        "scenes": [{"id": "duel", "title": "Glyph Duel", "environment": "symbols", "duration": duration,
                    "goals": ["blocked@kai", "flip@kai", "evaded@kai", "recovered@kai[into=guard]", "roll_start@kai", "evaded@kai",
                              "climbed@kai", "pick_up@kai[prop=times]", "throw@kai", "prop_hit@times", "knockdown@rho", "flip@kai", "stood_up@rho", "blocked@kai[move=flying_kick]",
                              "evaded@kai", "pick_up@kai[prop=staff]", "evaded@rho", "hit@kai[move=swing_weapon]", "throw@kai",
                              "knockdown@rho", "stood_up@rho", "fist_bump@kai"],
                    # Milestone 3: hit-stop on every blow; slow motion on the two flips and the final throw
                    "time_fx": {"hit_stop": True, "hit_stop_frames": 3, "hit_stop_max": 6,
                                "slowmo": [{"at": "flip@kai[dir=back]", "before": 0.1, "after": 0.55, "rate": 0.35},
                                           {"at": "flip@kai[dir=front]", "before": 0.05, "after": 0.6, "rate": 0.35},
                                           {"at": "hit@kai[prop=staff]", "before": 0.25, "after": 0.5, "rate": 0.3}]},
                    "placements": [{"character": K, "x": -470, "facing": 1, "z": -14}, {"character": R, "x": 60, "facing": -1, "z": 13}],
                    "actions": acts, "shots": shots}]}


if __name__ == "__main__":
    d = project()
    proj = ProjectSpec.model_validate(d)
    r = SceneRuntime(proj, "duel").simulate(physics_only=True)
    bumps = [e.t for e in r.events if e.type == "fist_bump"]
    end = (max(bumps) if bumps else r.duration - 2.6) + 2.6
    d = project(duration=math.ceil(end * 24) / 24)
    proj = resolve_cuts(ProjectSpec.model_validate(d), "duel")
    from apex.ai.director import StoryDirector
    StoryDirector._dry_run(proj)  # every goal in order, nobody stuck, sounds exist
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(proj.model_dump_json(indent=1, exclude_defaults=True))
    for s in proj.scenes[0].shots:
        print(f"{s.id:12s} {s.start:6.2f} - {s.end:6.2f}  {s.description}")
