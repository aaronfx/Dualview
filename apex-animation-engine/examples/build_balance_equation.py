"""The Balanced Equation — the character physically *does* math (Math-reference capability).

A true linear equation x + 2 = 5 stands in the world as physical glyph props. The character removes the +2 from the
left (grabs and throws the '+' and the '2' off the stage), and on that act the right-hand 5 physically morphs to 3,
leaving the solved x = 3. The transformation is authorised by SymPy BEFORE any object is built (`compile_proven_math_pair`
/ `verify_rewrite`): a false rewrite refuses to compile. Nothing is a playback trick — the removal is real physics and
the morph is the engine's mass-preserving glyph morph, triggered by the character's own throw event.

    PYTHONPATH=src python examples/build_balance_equation.py out/balance.json
    PYTHONPATH=src python -m apex.cli render out/balance.json -o out/balance.mp4 --scale 0.6 --qa-json out/balance_qa.json --review-dir out/balance_review
"""
from __future__ import annotations

import json
import sys

from apex.scene.math_stage import compile_proven_math_pair
from apex.scene.schema import ProjectSpec


def I(v):
    return {"op": "int", "value": v}


def V(v):
    return {"op": "var", "value": v}


def E(op, a, b):
    return {"op": op, "args": [a, b]}


def project(duration: float = 20.0):
    actor = "iko"
    # the proven rewrite: x + 2 = 5  ==>  x = 3 (SymPy refuses to build a false one)
    before = E("eq", E("add", V("x"), I(2)), I(5))
    after = E("eq", V("x"), I(3))
    stage, after_stage, proof = compile_proven_math_pair(
        before, after, name="eqn", center=(70, 48), glyph_size=(74, 92), gap=150)
    assert proof.valid, proof.explanation
    # before tokens, in order: x(00) +(01) 2(02) =(03) 5(04)
    g = {s.semantic: s for s in stage.glyphs}  # by token, unambiguous here
    plus, two, five = stage.glyphs[1], stage.glyphs[2], stage.glyphs[4]
    assert (plus.glyph, two.glyph, five.glyph) == ("+", "2", "5"), [s.glyph for s in stage.glyphs]

    # The equation stands upright and readable. Most terms are fixed set dressing (solid=False): they never tip, and a
    # term only becomes a free body when the character picks it up (so + and 2 can still be lifted and thrown). The 5
    # must stay a real dynamic body so it can morph to 3 — it is made bottom-heavy (low centre of mass) so it self-rights
    # and never tips, and nothing touches it until it changes.
    props = []
    for s in stage.glyphs:
        # z behind the actor's lane: the equation stands like a board the figure works in front of, so the figure
        # passing a symbol is a front/back pass (no body overlap), while it can still reach in to lift a term
        pr = {"id": s.id, "kind": "glyph", "glyph": s.glyph, "position": [s.x, s.y],
              "size": list(s.size), "color": s.color, "mass": 2.4, "friction": 0.9, "solid": False, "z": -52}
        if s.id == five.id:  # the solved right-hand side morphs 5 -> 3 in place (fixed glyphs morph upright now)
            pr["morphs"] = [{"to": "3", "on": f"throw@{actor}[prop={two.id}]", "duration": 0.45, "delay": 0.25}]
        props.append(pr)

    return {
        "schema_version": "0.1", "id": "balance_equation",
        "title": "The Balanced Equation — the figure solves x + 2 = 5",
        "fps": 24, "width": 1280, "height": 720, "seed": 77,
        "characters": [{"id": actor, "name": "IKO", "strength": 51000,
            "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
            "style": {"body_color": "#ffd04e", "far_color": "#a87925", "visor_color": "#87fafa",
                      "glow_color": "#fdda69", "scarf_color": "#ff6493", "has_scarf": True,
                      "limb_width": 8.0, "cadence_scale": 1.05}}],
        "environments": [{
            "id": "math_room",
            "room": {"width": 1800, "height": 950, "depth_back": 480, "entry_door": False,
                     "grid_spacing": 150, "grid_alpha": 0.33, "style": "open"},
            "gravity": [0, -1568], "dust": 30,
            "theme": {"accent": "#7bd6f5", "alert": "#ef587c", "back": "#151b29", "floor": "#0f1623",
                      "side": "#0c1420", "ceiling": "#090d17", "background": "#050913", "dust": "#9dd9e8"},
            "obstacles": [],
            "props": props,
        }],
        "scenes": [{
            "id": "solve", "title": "Balance it", "environment": "math_room", "duration": duration,
            "placements": [{"character": actor, "x": -560, "facing": 1}],
            "actions": [
                # 1. arrive and STUDY the problem (this is a puzzle, not clutter to clear)
                {"character": actor, "type": "run_to", "target_x": -120, "speed": 340},
                {"character": actor, "type": "notice", "target": f"prop:{five.id}"},
                {"character": actor, "type": "act", "clip": "peer_down", "emotion": "curious", "duration": 1.0},
                # 2. identify the term in the way: reach toward the + 2
                {"character": actor, "type": "act", "clip": "reach_out", "emotion": "curious", "duration": 0.7},
                # 3. cancel the operator: flick the '+' away
                {"character": actor, "type": "pick_up", "target": f"prop:{plus.id}"},
                {"character": actor, "type": "throw", "target": "point:-600,560", "power": 1.0},
                # 4. the KEY algebraic beat: carry the 2 ACROSS the '=' to the other side, then subtract it from the 5
                {"character": actor, "type": "pick_up", "target": f"prop:{two.id}"},
                {"character": actor, "type": "walk_to", "target_x": 265, "speed": 250},
                {"character": actor, "type": "notice", "target": f"prop:{five.id}"},
                {"character": actor, "type": "throw", "target": "point:880,620", "power": 1.85},
                # 5. react to the result (5 just became 3) and present the solution
                {"character": actor, "type": "act", "clip": "shock", "emotion": "surprised", "duration": 0.7},
                {"character": actor, "type": "walk_to", "target_x": 95, "speed": 210},
                {"character": actor, "type": "act", "clip": "reach_out", "emotion": "joyful", "duration": 0.6},
                {"character": actor, "type": "act", "clip": "cheer", "emotion": "joyful", "duration": 1.3},
            ],
            "goals": [f"throw@{actor}[prop={plus.id}]", f"throw@{actor}[prop={two.id}]", f"morph@{five.id}"],
            "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
            "score": {"key": "D", "level": 0.4, "cues": [{"mood": "tension", "at": 0.0},
                                                         {"mood": "hope", "at": 7.5}, {"mood": "triumph", "at": 11.5}]},
            "shots": [
                # study: hold wide on the whole equation and the arriving figure
                {"id": "s1_study", "kind": "establishing", "start": 0, "end": 4.2,
                 "camera": {"mode": "static", "center": [30, 210], "view_height": 760}},
                # identify + cancel the +: follow the figure on the left side
                {"id": "s2_cancel", "kind": "medium", "start": 4.2, "end": 7.2,
                 "camera": {"mode": "follow", "target": actor, "view_height": 430, "offset": [20, 70],
                            "lead": 0.12, "stiffness": 3.6}},
                # carry across the = and subtract from the 5: keep BOTH the figure and the 5 in frame
                {"id": "s3_carry", "kind": "medium", "start": 7.2, "end": 11.5,
                 "camera": {"mode": "follow", "target": actor, "view_height": 520, "offset": [70, 60],
                            "lead": 0.16, "stiffness": 3.4, "include": [f"prop:{five.id}"]}},
                # solved: frame x = 3 clearly; the discarded 2 (settles at x~437, just right of the 3 at ~362) sits
                # off the right edge of this framing
                {"id": "s4_solved", "kind": "medium", "start": 11.5, "end": duration,
                 "camera": {"mode": "static", "center": [-44, 160], "view_height": 500}},
            ],
        }],
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out/balance.json"
    p = ProjectSpec.model_validate(project())
    with open(out, "w", encoding="utf-8") as f:
        f.write(p.model_dump_json(indent=2))
    print(f"wrote {out}: proven x+2=5 -> x=3; {len(p.environments[0].props)} equation glyph props")
