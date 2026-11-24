"""Build a native, parameterised additive transposition demonstration."""
from __future__ import annotations
import argparse
from pathlib import Path
from apex.scene.schema import MathTransferSpec, ProjectSpec
from apex.scene.transposition_stage import compile_native_transfer


def project(n: int = 2, c: int = 5, op: str = "add"):
    actor = "iko"
    raw = {"op": "eq", "args": [{"op": op, "args": [
        {"op": "var", "value": "x"}, {"op": "int", "value": n}]},
        {"op": "int", "value": c}]}
    spec = MathTransferSpec(equation=raw, actor=actor)
    stage, props = compile_native_transfer(spec)
    term = props[1]
    dest_x, dest_y = stage.destination
    bottom = dest_y - term.size[1] / 2
    duration = 14.0
    action = lambda typ, **kw: {"character": actor, "type": typ, **kw}
    center_x = spec.center[0]
    return {
        "id": "semantic_transposition", "title": "Move the whole term",
        "fps": 24, "width": 1280, "height": 720, "seed": 77,
        "characters": [{"id": actor, "name": "IKO", "strength": 51000,
                        "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
                        "style": {"body_color": "#ffd04e", "far_color": "#a87925",
                                  "visor_color": "#87fafa", "glow_color": "#fdda69",
                                  "scarf_color": "#ff6493", "has_scarf": True, "limb_width": 8.0}}],
        "environments": [{"id": "math_room", "room": {"width": 2400, "height": 950,
                           "depth_back": 480, "entry_door": False, "grid_spacing": 150, "style": "open"},
                          "dust": 12, "props": [p.model_dump(mode="json") for p in props]}],
        "scenes": [{"id": "solve", "environment": "math_room", "duration": duration,
                    "math_transfer": spec.model_dump(mode="json"),
                    "placements": [{"character": actor, "x": term.position[0] - 245, "facing": 1}],
                    "actions": [
                        action("run_to", target_x=term.position[0] - 100, speed=320),
                        action("notice", target="prop:" + term.id, duration=0.7),
                        action("pick_up", target="prop:" + term.id),
                        action("walk_to", target_x=dest_x - 85, speed=240),
                        action("place", target=f"point:{dest_x},{bottom}", seat=True),
                        action("idle", duration=1.9),
                        action("point", target="prop:" + term.id, duration=0.8),
                        action("idle", duration=1.1),
                        action("act", clip="cheer", emotion="joyful", duration=1.2)],
                    "goals": [f"pick_up@{actor}[prop={term.id}]",
                              f"math_crossed@{actor}[prop={term.id}]",
                              f"math_transferred@{actor}[prop={term.id}]",
                              f"math_evaluate@{actor}[prop={props[4].id}]",
                              f"morph@{props[4].id}"],
                    "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
                    "shots": [{"id": "whole_equation", "kind": "establishing", "start": 0, "end": duration,
                               "camera": {"mode": "static", "center": [center_x, 145],
                                          "view_height": max(480, (dest_x - term.position[0] + 420) / 1.7)}}]}]}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("output")
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--c", type=int, default=5)
    p.add_argument("--op", choices=["add", "sub"], default="add")
    args = p.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ProjectSpec.model_validate(project(args.n, args.c, args.op)).model_dump_json(indent=2))
