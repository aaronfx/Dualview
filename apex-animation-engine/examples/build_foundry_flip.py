"""Build examples/foundry_flip.json (quality-upgrade Task 6: generalization scene) and print the event timeline.

A different character (PIP: shorter legs, bigger head, faster cadence, no scarf), a different environment (a wide, low
foundry hall with its own theme) and a different action sequence (slide under a duct, mid-air slap of a wall lever,
a -180 deg gravity flip, a hard landing on the ceiling, exit through a hatch), built only from existing actions,
controllers and motion-library clips.

    PYTHONPATH=src python examples/build_foundry_flip.py examples/foundry_flip.json 19.5 shots
"""
import json, sys
W, H = 1800, 900
HW = W / 2

def project(shots):
    return {
        "schema_version": "0.1", "id": "foundry_flip", "title": "Foundry Flip (generalization test)", "fps": 24,
        "width": 1920, "height": 1080, "seed": 11,
        "characters": [{"id": "pip", "name": "PIP",
                        "proportions": {"spine": 26, "chest": 25, "neck": 6, "head": 30, "upper_arm": 27, "forearm": 25, "hand": 8,
                                        "thigh": 35, "shin": 33, "foot": 13},
                        "style": {"body_color": "#eaf2ff", "far_color": "#8f9bb3", "visor_color": "#ff4f9a", "glow_color": "#ff7ab8",
                                  "scarf_color": "#ff4f9a", "has_scarf": False, "limb_width": 8.5,
                                  "cadence_scale": 1.22, "stride_scale": 0.86, "lean_scale": 1.35, "arm_swing_scale": 1.45}}],
        "environments": [{
            "id": "foundry", "room": {"width": W, "height": H, "depth_back": 560, "grid_spacing": 90},
            "theme": {"accent": "#ffae3d", "alert": "#ff3b30", "back": "#1d1611", "floor": "#0e0a07", "side": "#17110d",
                      "ceiling": "#0a0705", "background": "#060403", "dust": "#ffd9a3"},
            "gravity": [0, -1568],
            "switches": [{"id": "flip", "x": 250.0, "height": 92.0, "surface": "wall_right",
                          "effect": {"rotate_deg": -180, "delay": 1.5, "duration": 0.45}}],
            "props": [{"id": "can_a", "kind": "canister", "position": [-870, 24], "size": [30, 48], "mass": 6},
                      {"id": "can_b", "kind": "canister", "position": [-838, 20], "size": [26, 40], "mass": 5}],
            "exits": [{"id": "hatch", "surface": "wall_right", "s": 810.0, "width": 180, "unlock_on": "switch:flip", "open_radius": 330}],
            "obstacles": [{"id": "duct", "kind": "beam", "center": [80.0, 112.0], "size": [150.0, 30.0]}],
            "dust": 140}],
        "scenes": [{
            "id": "flip", "title": "Foundry Flip", "environment": "foundry", "duration": float(sys.argv[2]) if len(sys.argv) > 2 else 16.0,
            "placements": [{"character": "pip", "x": -800, "facing": 1}],
            "actions": [
                {"character": "pip", "type": "walk_to", "target_x": -560, "speed": 140},
                {"character": "pip", "type": "notice", "target": "exit:hatch", "duration": 0.8},
                {"character": "pip", "type": "point", "target": "exit:hatch", "duration": 0.9},
                {"character": "pip", "type": "notice", "target": "switch:flip", "duration": 0.6},
                {"character": "pip", "type": "run_to", "target_x": -150.0},
                {"character": "pip", "type": "duck_slide", "target_x": 260.0},
                {"character": "pip", "type": "run_to", "target_x": 735.0},
                {"character": "pip", "type": "look_at", "target": "switch:flip", "duration": 0.45},
                {"character": "pip", "type": "jump_to", "target_x": 785.0, "height": 170.0, "switch": "flip"},
                {"character": "pip", "type": "wait_grounded"},
                {"character": "pip", "type": "look_at", "target": "exit:hatch", "duration": 1.8},
                {"character": "pip", "type": "wait_grounded"},
                {"character": "pip", "type": "notice", "target": "exit:hatch", "duration": 0.7},
                {"character": "pip", "type": "reach_exit", "target": "exit:hatch", "speed": 170, "duration": 0.6},
                {"character": "pip", "type": "idle", "duration": 3.0}],
            "shots": shots}]}

def wide_only(d):
    return [{"id": "w", "start": 0.0, "end": d, "kind": "wide", "camera": {"mode": "static", "center": [0, 450], "view_height": 1150}}]

if __name__ == "__main__":
    out = sys.argv[1]
    mode = sys.argv[3] if len(sys.argv) > 3 else "wide"
    import importlib.util, os
    d = float(sys.argv[2]) if len(sys.argv) > 2 else 16.0
    if mode == "wide":
        shots = wide_only(d)
    else:
        spec = importlib.util.spec_from_file_location("shots", os.path.join(os.path.dirname(os.path.abspath(__file__)), "foundry_flip_shots.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        shots = m.SHOTS
    json.dump(project(shots), open(out, "w"), indent=1)
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    p = ProjectSpec.model_validate(json.load(open(out)))
    rt = SceneRuntime(p, "flip"); r = rt.simulate()
    for e in r.events:
        if e.type in ("footstep",): continue
        print(f"{e.t:6.2f} {e.type:18s} {json.dumps({k: (round(v,1) if isinstance(v,float) else v) for k,v in e.data.items() if k in ('surface','normal_speed','speed','exit','switch')})}")
