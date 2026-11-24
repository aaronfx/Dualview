"""Autonomous linear-equation film generator (APEX Studio / EDU quality benchmark).

Given any `a*x + b = c`, this builds a complete APEX film with NO per-equation hardcoding: it asks
`equation_solver.solve_plan` for the SymPy-verified steps, lays the equation out as physical glyphs, identifies the
coefficient / constant / right-hand-side tokens from the layout, and stages each step as the character removing a term
from the left while the right side changes by the same amount *on the same event* — so equality is visibly preserved
(both sides change together) and every transformation is caused by a real, verified character action.

Deficiencies this addresses vs the earlier balance scene: faster, purposeful motion; minimal idle; study/effort/triumph
acting; no energy bloom or motion trails; a camera that always frames the whole equation; a clear final payoff.

    PYTHONPATH=src python examples/build_equation_film.py 1 2 5 out/eq_1_2_5.json      # x + 2 = 5
    PYTHONPATH=src python -m apex.cli render out/eq_1_2_5.json -o out/eq_1_2_5.mp4 --qa-json ... --review-dir ...
"""
from __future__ import annotations

import json
import sys

from apex.scene.equation_solver import Equation, solve_plan
from apex.scene.math_stage import compile_math_stage
from apex.scene.schema import ProjectSpec

ACTOR = "iko"
GY = 120.0          # equation baseline (reachable from the ground)
GLYPH = (76.0, 96.0)
GAP = 150.0
Z = -52.0           # equation stands in a back lane; the figure works in front of it (no body-pass)


def _roles(glyphs):
    """From the laid-out tokens, find the eq index, the right-hand-side digit ids (L->R), the left constant-term ids
    (operator + its digits) and the left coefficient ids (leading digits + the x multiplier)."""
    sem = [g.semantic for g in glyphs]
    eq_i = sem.index("eq")
    rhs = [g.id for g in glyphs[eq_i + 1:]]
    lhs = glyphs[:eq_i]
    const_ids, coef_ids = [], []
    op_i = next((i for i, g in enumerate(lhs) if g.semantic in ("add", "sub")), None)
    if op_i is not None:
        const_ids = [g.id for g in lhs[op_i:]]
    mul_i = next((i for i, g in enumerate(lhs) if g.semantic == "mul"), None)
    if mul_i is not None:
        coef_ids = [g.id for g in lhs[:mul_i + 1]]   # leading number(s) + the x multiplier
    return eq_i, rhs, const_ids, coef_ids


def stage_plan(a, b, c):
    """Everything the film needs, derived from the equation: the glyph props, and per step the left ids to remove, the
    right ids to remove, and the right ids to morph (id -> new glyph). Right side tracked across steps."""
    steps, sol = solve_plan(a, b, c)
    st = compile_math_stage(Equation(a, b, c).ast(), name="eq", center=(0.0, GY), glyph_size=GLYPH, gap=GAP)
    glyphs = list(st.glyphs)
    gmap = {g.id: g for g in glyphs}
    eq_i, rhs_ids, const_ids, coef_ids = _roles(glyphs)

    cur_rhs = list(rhs_ids)                 # right-hand-side digit ids, left to right (current)
    beats = []
    for s in steps:
        left = const_ids if s.op == "subtract" else coef_ids
        new_digits = str(int(s.after.c))
        keep = cur_rhs[-len(new_digits):]
        drop = cur_rhs[:-len(new_digits)]
        morph = [(gid, d) for gid, d in zip(keep, new_digits) if gmap[gid].glyph != d]
        beats.append({"left": list(left), "rhs_drop": list(drop), "rhs_morph": morph, "desc": s.desc if hasattr(s, "desc") else s.description})
        cur_rhs = keep
        const_ids = []                      # consumed after the subtract step
    return glyphs, beats, sol, gmap


def project(a, b, c, width=1920, height=1080, dur_override=None):
    glyphs, beats, sol, gmap = stage_plan(a, b, c)

    props = []
    for g in glyphs:
        props.append({"id": g.id, "kind": "glyph", "glyph": g.glyph, "position": [g.x, g.y],
                      "size": list(g.size), "color": g.color, "mass": 2.4, "friction": 0.9, "solid": False, "z": Z})

    # left->right extent of the equation, for camera framing (never crop the equation)
    xs = [g.x for g in glyphs]
    span = max(xs) - min(xs) + GLYPH[0]
    view_h = max(620.0, (span + 360.0) / (width / height))

    actions = [{"character": ACTOR, "type": "run_to", "target_x": min(xs) - 70, "speed": 360},
               {"character": ACTOR, "type": "act", "clip": "peer_down", "emotion": "curious", "duration": 0.7}]

    def throw_glyph(gid, morphs_on_this=()):
        g = gmap[gid]
        # approach from just left of the glyph, lift it and hurl it clear of the frame
        acts = [{"character": ACTOR, "type": "walk_to", "target_x": g.x - 64, "speed": 300},
                {"character": ACTOR, "type": "pick_up", "target": f"prop:{gid}"},
                {"character": ACTOR, "type": "throw", "target": f"point:{g.x - 900},700", "power": 1.6}]
        return acts

    morph_specs = {}   # gid -> ordered list of MorphSpec dicts (a glyph may change over several steps, e.g. 11->8->4)
    for bi, beat in enumerate(beats):
        removes = beat["left"] + beat["rhs_drop"]
        last = removes[-1]
        for gid in removes:
            actions += throw_glyph(gid)
        # the right side changes by the same amount, caused by the last removal of this step
        for gid, newglyph in beat["rhs_morph"]:
            morph_specs.setdefault(gid, []).append({"to": newglyph, "on": f"throw@{ACTOR}[prop={last}]", "duration": 0.4, "delay": 0.2})
        actions.append({"character": ACTOR, "type": "act", "clip": "reach_out", "emotion": "curious", "duration": 0.5})

    # payoff: present the solved x = sol
    actions += [{"character": ACTOR, "type": "walk_to", "target_x": -60, "speed": 260},
                {"character": ACTOR, "type": "act", "clip": "cheer", "emotion": "joyful", "duration": 1.2}]

    for p in props:
        if p["id"] in morph_specs:
            p["morphs"] = morph_specs[p["id"]]

    # a generous upper bound; the __main__ pass measures the real action end and trims the idle tail
    dur = dur_override or (6.0 + 3.0 * len(beats) + 2.5 * sum(len(b["left"]) + len(b["rhs_drop"]) for b in beats))
    return {
        "schema_version": "0.1", "id": f"equation_{a}_{b}_{c}".replace("-", "m"),
        "title": f"Solve {a}x + {b} = {c}", "fps": 24, "width": width, "height": height, "seed": 61,
        "characters": [{"id": ACTOR, "name": "IKO", "strength": 51000,
            "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
            "style": {"body_color": "#ffd04e", "far_color": "#a87925", "visor_color": "#87fafa",
                      "glow_color": "#fdda69", "scarf_color": "#ff6493", "has_scarf": True,
                      "limb_width": 8.0, "cadence_scale": 1.1}}],
        "environments": [{
            "id": "math_room",
            "room": {"width": max(2200, span + 900), "height": 1100, "depth_back": 480, "entry_door": False,
                     "grid_spacing": 150, "grid_alpha": 0.3, "style": "open"},
            "gravity": [0, -1568], "dust": 22,
            "theme": {"accent": "#7bd6f5", "alert": "#ef587c", "back": "#151b29", "floor": "#0f1623",
                      "side": "#0c1420", "ceiling": "#090d17", "background": "#050913", "dust": "#9dd9e8"},
            "obstacles": [], "props": props,
        }],
        "scenes": [{
            "id": "solve", "title": "Solve it", "environment": "math_room", "duration": round(dur, 1),
            "placements": [{"character": ACTOR, "x": min(xs) - 280, "facing": 1}],
            "actions": actions,
            "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
            "score": {"key": "D", "level": 0.4, "cues": [{"mood": "tension", "at": 0.0}, {"mood": "triumph", "at": round(dur - 3, 1)}]},
            "shots": [{"id": "whole", "kind": "wide", "start": 0, "end": round(dur, 1),
                       "camera": {"mode": "static", "center": [0, 150], "view_height": round(view_h, 1)}}],
        }],
    }


def _tight_duration(a, b, c) -> float:
    """Simulate once and end the film a short beat after the last real action (no long idle tail)."""
    from apex.scene.runtime import SceneRuntime
    p = ProjectSpec.model_validate(project(a, b, c))
    res = SceneRuntime(p, "solve").simulate()
    acts = [e.t for e in res.events if e.type in ("throw", "morph", "act", "pick_up")]
    last = max(acts) if acts else p.scenes[0].duration
    return round(min(p.scenes[0].duration, last + 2.4), 1)


if __name__ == "__main__":
    a, b, c = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    out = sys.argv[4] if len(sys.argv) > 4 else f"out/eq_{a}_{b}_{c}.json"
    p = ProjectSpec.model_validate(project(a, b, c, dur_override=_tight_duration(a, b, c)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(p.model_dump_json(indent=2))
    steps, sol = solve_plan(a, b, c)
    print(f"wrote {out}: {a}x+{b}={c} -> x={sol} ({p.scenes[0].duration}s); steps: " + " ; ".join(s.description for s in steps))
