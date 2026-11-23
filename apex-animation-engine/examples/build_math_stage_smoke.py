"""Small real-engine smoke test for the Math World physical glyph compiler.

NOT a reference-level film: it checks that a true equation's tokens are
rendered as geometry in the same environment as an animated stick figure.
"""
from __future__ import annotations

import json
import sys
from apex.scene.math_stage import compile_math_stage
from apex.scene.schema import ProjectSpec


def I(v): return {"op": "int", "value": v}
def V(v): return {"op": "var", "value": v}
def E(op, a, b): return {"op": op, "args": [a, b]}


def project():
    equation = compile_math_stage(E("eq", E("add", V("x"), I(2)), I(5)),
                                  name="equation", center=(0, 430),
                                  glyph_size=(75, 104), gap=109)
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "math_stage_smoke", "title": "The Physical Equation",
        "fps": 24, "width": 1280, "height": 720, "seed": 33,
        "characters": [{"id": "iko", "name": "IKO", "style": {
            "body_color": "#ffcc40", "visor_color": "#6beaff",
            "glow_color": "#ffc850", "scarf_color": "#43d8e2"}}],
        "environments": [{"id": "math_room",
            "room": {"width": 1800, "height": 900, "entry_door": False, "style": "open"},
            "dust": 35, "gravity": [0, -1568],
            "obstacles": [x.model_dump(exclude_none=True) for x in equation.objects()],
            "props": [{"id": "loose_plus", "kind": "glyph", "glyph": "+",
                       "position": [-225, 41], "size": [70, 70],
                       "color": "#ffcc66", "mass": 2.2, "friction": 0.8}]}],
        "scenes": [{"id": "meet_equation", "environment": "math_room", "duration": 8.0,
            "placements": [{"character": "iko", "x": -700, "facing": 1}],
            "actions": [
                {"character": "iko", "type": "run_to", "target_x": -360, "speed": 310},
                {"character": "iko", "type": "notice", "target": "point:0,430"},
                {"character": "iko", "type": "pick_up", "target": "prop:loose_plus"},
                {"character": "iko", "type": "throw", "target": "point:400,330", "power": 0.8},
                {"character": "iko", "type": "act", "clip": "shock", "emotion": "curious"},
            ],
            "shots": [{"id": "math_wide", "kind": "wide", "start": 0, "end": 8,
                       "camera": {"mode": "static", "center": [0, 300], "view_height": 820,
                                  "keep_in_frame": False}}]
            }]
    })


if __name__ == "__main__":
    p = project()
    out = sys.argv[1] if len(sys.argv) > 1 else "out/math_stage_smoke.json"
    with open(out, "w", encoding="utf-8") as f:
        f.write(p.model_dump_json(indent=2))
    print(f"wrote {out}: {len(p.environments[0].obstacles)} real equation glyph obstacles")
