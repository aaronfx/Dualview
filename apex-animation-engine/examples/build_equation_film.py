"""Autonomous linear-equation film — taught by TRANSPOSITION, using the engine's `transpose` move.

For any `a*x + b = c`: the character gestures and the term glides ACROSS the `=`, its operation inverting
(`+`<->`-`, `x`(times)<->`/`) as it crosses — so `x + 2 = 5` becomes `x = 5 - 2`, and `5 - 2` is then computed to `3`.
Nothing is thrown away; every move is a real algebra step, and the arithmetic (`solve_plan`) is SymPy-verified. No
per-equation hardcoding.

    PYTHONPATH=src python examples/build_equation_film.py 1 2 5 out/eq_1_2_5.json
"""
from __future__ import annotations

import sys

from apex.scene.equation_solver import Equation, solve_plan
from apex.scene.math_stage import compile_math_stage
from apex.scene.schema import ProjectSpec

ACTOR = "iko"
GY = 130.0
GLYPH = (70.0, 92.0)
GAP = 128.0
Z = -52.0
# The renderer stores the multiply operator as the times glyph "x" (× is aliased to it);
# transposition inverts the operation as the term crosses the =.
FLIP = {"+": "-", "-": "+", "x": "÷", "÷": "x"}


def _roles(glyphs):
    sem = [g.semantic for g in glyphs]
    eq_i = sem.index("eq")
    rhs = [g.id for g in glyphs[eq_i + 1:]]
    lhs = glyphs[:eq_i]
    op_i = next((i for i, g in enumerate(lhs) if g.semantic in ("add", "sub")), None)
    const = [g.id for g in lhs[op_i:]] if op_i is not None else []
    mul_i = next((i for i, g in enumerate(lhs) if g.semantic == "mul"), None)
    coef = [g.id for g in lhs[:mul_i + 1]] if mul_i is not None else []
    return eq_i, rhs, const, coef


def stage_plan(a, b, c):
    steps, sol = solve_plan(a, b, c)
    st = compile_math_stage(Equation(a, b, c).ast(), name="eq", center=(0.0, GY), glyph_size=GLYPH, gap=GAP)
    glyphs = list(st.glyphs)
    gmap = {g.id: g for g in glyphs}
    _, rhs_ids, const, coef = _roles(glyphs)
    right_x = max(gmap[i].x for i in rhs_ids)
    cur_rhs = list(rhs_ids)
    beats = []
    for s in steps:
        term = const if s.op == "subtract" else coef
        op_id = next(i for i in term if gmap[i].semantic in ("add", "sub", "mul"))
        num_ids = [i for i in term if i != op_id]
        flipped = FLIP[gmap[op_id].glyph]
        cross = [(op_id, flipped, right_x + GAP)] + [(nid, None, right_x + (k + 2) * GAP) for k, nid in enumerate(num_ids)]
        result = str(int(s.after.c))
        assert len(result) == 1, "single-digit right-hand sides in this benchmark"
        lead = cur_rhs[0]
        consume = cur_rhs[1:] + [op_id] + num_ids
        beats.append({"cross": cross, "lead": lead, "result": result, "consume": consume})
        cur_rhs = [lead]
        right_x = gmap[lead].x
        if s.op == "subtract":
            const = []
        else:
            coef = []
    return glyphs, beats, sol, gmap


def project(a, b, c, width=1920, height=1080):
    glyphs, beats, sol, gmap = stage_plan(a, b, c)
    props = [{"id": g.id, "kind": "glyph", "glyph": g.glyph, "position": [g.x, g.y],
              "size": list(g.size), "color": g.color, "mass": 2.4, "friction": 0.9, "solid": False, "z": Z,
              "transposes": [], "morphs": []} for g in glyphs]
    pmap = {p["id"]: p for p in props}

    all_x = [g.x for g in glyphs] + [tx for be in beats for (_, _, tx) in be["cross"]]
    lo, hi = min(all_x), max(all_x) + GLYPH[0]
    view_h = max(560.0, (hi - lo + 420.0) / (width / height))
    cam_cx = round((lo + hi) / 2 - GLYPH[0] / 2)
    off_x = hi + 600.0   # where consumed terms glide away to

    actions = []
    t = 0.0

    def act(clip, dur, emotion="curious"):
        nonlocal t
        actions.append({"character": ACTOR, "type": "act", "clip": clip, "emotion": emotion, "duration": dur})
        t += dur

    # the figure stands by the equation and directs it (reference-style symbol manipulation)
    act("peer_down", 1.1, "curious")                       # study
    for be in beats:
        # cross: gesture, and each term of the left side glides across the = ; the operator inverts mid-flight
        g0 = t + 0.15
        for gid, flipped, tx in be["cross"]:
            pmap[gid]["transposes"].append({"to": [tx, GY], "at": round(g0, 2), "duration": 0.55, "arc": 150.0})
            if flipped is not None:
                pmap[gid]["morphs"].append({"to": flipped, "at": round(g0 + 0.27, 2), "duration": 0.3})
        act("reach_out", 1.1, "curious")                   # the push-across gesture
        act("peer_down", 0.9, "curious")                   # read it: x = c <op> b
        # compute: the leading right digit becomes the result; the crossed term glides away (consumed)
        cg = t + 0.15
        pmap[be["lead"]]["morphs"].append({"to": be["result"], "at": round(cg, 2), "duration": 0.35})
        for k, gid in enumerate(be["consume"]):
            pmap[gid]["transposes"].append({"to": [off_x + k * 120, 760.0], "at": round(cg, 2), "duration": 0.5, "arc": 220.0})
        act("shock", 0.8, "surprised")                     # the realization / compute beat
    act("reach_out", 0.7, "joyful")                        # present the answer
    act("cheer", 1.4, "joyful")                            # payoff
    dur = round(t + 0.6, 1)

    for p in props:
        if not p["transposes"]:
            del p["transposes"]
        if not p["morphs"]:
            del p["morphs"]

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
            "room": {"width": max(2800, (hi - lo) + 1800), "height": 1100, "depth_back": 480, "entry_door": False,
                     "grid_spacing": 150, "grid_alpha": 0.3, "style": "open"},
            "gravity": [0, -1568], "dust": 18,
            "theme": {"accent": "#7bd6f5", "alert": "#ef587c", "back": "#151b29", "floor": "#0f1623",
                      "side": "#0c1420", "ceiling": "#090d17", "background": "#050913", "dust": "#9dd9e8"},
            "obstacles": [], "props": props,
        }],
        "scenes": [{
            "id": "solve", "title": "Solve it", "environment": "math_room", "duration": dur,
            "placements": [{"character": ACTOR, "x": round(min(g.x for g in glyphs) - 40), "facing": 1}],
            "actions": actions,
            "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
            "score": {"key": "D", "level": 0.4, "cues": [{"mood": "tension", "at": 0.0}, {"mood": "triumph", "at": round(dur - 2.5, 1)}]},
            "shots": [{"id": "whole", "kind": "wide", "start": 0, "end": dur,
                       "camera": {"mode": "static", "center": [cam_cx, 150], "view_height": round(view_h, 1)}}],
        }],
    }


if __name__ == "__main__":
    a, b, c = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    out = sys.argv[4] if len(sys.argv) > 4 else f"out/eq_{a}_{b}_{c}.json"
    p = ProjectSpec.model_validate(project(a, b, c))
    with open(out, "w", encoding="utf-8") as f:
        f.write(p.model_dump_json(indent=2))
    steps, sol = solve_plan(a, b, c)
    print(f"wrote {out}: {a}x+{b}={c} -> x={sol} ({p.scenes[0].duration}s); " + " ; ".join(s.description for s in steps))
