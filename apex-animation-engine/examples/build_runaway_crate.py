"""Build examples/runaway_crate.json: a small two-character interaction example for the AI Director's prompt.

Deliberately NOT The Rescue (no strap, no pinning, no lever): it teaches the *structure* of a physical,
two-character scene, so a planner learns the pattern rather than the answer:
- a push that breaks loose and gets away, so the pusher falls (push -> push_lost -> body_fall);
- lying-down actions only after the fall (struggle, get_up);
- the other character reacts to an EVENT (wait_for until event:body_fall@pip), not to a guessed time;
- a helped get-up (get_up target char:tao + offer_hand target char:pip), then a gesture;
- ordered story goals that name engine events, and event-timed cuts (cut_on).
The physical numbers are tuned by APEX's setup solver, as they would be for an AI plan.

    PYTHONPATH=src python examples/build_runaway_crate.py examples/runaway_crate.json
"""
import json
import sys

from apex.scene.schema import ProjectSpec
from apex.scene.solver import resolve_cuts, solve

GOALS = ["push_start@pip", "push_lost@pip", "body_fall@pip", "notice@tao", "hand_offered@tao", "hand_grab@pip", "stood_up@pip",
         "fist_bump@tao"]


def project() -> dict:
    return {
        "schema_version": "0.1", "id": "runaway_crate", "title": "The Runaway Crate", "fps": 24, "width": 1920, "height": 1080, "seed": 5,
        "characters": [
            {"id": "pip", "name": "PIP", "strength": 50000,
             "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
             "style": {"body_color": "#ff6b8b", "far_color": "#b34a62", "has_scarf": False, "cadence_scale": 1.05, "lean_scale": 1.2}},
            {"id": "tao", "name": "TAO", "strength": 45000,
             "proportions": {"spine": 32, "chest": 30, "head": 25, "thigh": 46, "shin": 44},
             "style": {"body_color": "#8be36b", "far_color": "#5a9c45", "scarf_color": "#ffd23a", "has_scarf": True,
                       "cadence_scale": 0.9, "stride_scale": 1.1}}],
        "environments": [{
            "id": "loading_bay", "room": {"width": 1600, "height": 650, "depth_back": 480, "grid_spacing": 80},
            "theme": {"accent": "#ffb347", "alert": "#ff4040", "back": "#1d1a17", "floor": "#0f0d0b", "side": "#17140f"},
            "gravity": [0, -1568],
            "props": [{"id": "crate", "kind": "crate", "position": [-60, 46], "size": [130, 90], "mass": 70, "friction": 0.6,
                       "static_friction": 1.0}],
            "dust": 60}],
        "scenes": [{
            "id": "bay", "title": "The Runaway Crate", "environment": "loading_bay", "duration": 12.0,
            "goals": GOALS,
            "placements": [{"character": "pip", "x": -420, "facing": 1}, {"character": "tao", "x": 520, "facing": -1}],
            "actions": [
                {"character": "pip", "type": "walk_to", "target_x": -230, "speed": 150},
                {"character": "pip", "type": "look_at", "target": "prop:crate", "duration": 0.4},
                {"character": "pip", "type": "push", "target": "prop:crate", "effort": 1.3},
                {"character": "pip", "type": "struggle", "duration": 1.0},
                {"character": "pip", "type": "get_up", "target": "char:tao"},
                {"character": "pip", "type": "gesture", "target": "char:tao", "gesture": "fist_bump"},
                {"character": "pip", "type": "idle", "duration": 2.0},
                {"character": "tao", "type": "look_around", "duration": 1.5},
                {"character": "tao", "type": "wait_for", "until": "event:body_fall@pip"},
                {"character": "tao", "type": "notice", "target": "char:pip", "duration": 0.6},
                {"character": "tao", "type": "run_to", "target": "char:pip", "speed": 330},
                {"character": "tao", "type": "offer_hand", "target": "char:pip"},
                {"character": "tao", "type": "gesture", "target": "char:pip", "gesture": "fist_bump"},
                {"character": "tao", "type": "idle", "duration": 2.0}],
            "shots": [
                {"id": "s1_wide", "start": 0, "end": 2, "kind": "establishing", "description": "the bay: PIP sizes up a heavy crate",
                 "camera": {"mode": "static", "center": [0, 230], "view_height": 620}},
                {"id": "s2_push", "start": 2, "end": 5, "kind": "medium", "cut_on": "event:push_start@pip", "cut_offset": -0.3,
                 "description": "PIP strains; the crate breaks loose and gets away",
                 "camera": {"mode": "follow", "target": "pip", "view_height": 340, "include": ["prop:crate"]},
                 "sound_cues": [{"on_event": "push_start", "sound": "strain", "gain": 0.8}, {"on_event": "body_fall", "sound": "impact", "gain": 1.0}]},
                {"id": "s3_help", "start": 5, "end": 9, "kind": "medium", "cut_on": "event:notice@tao",
                 "description": "TAO sees PIP fall, runs over and offers a hand",
                 "camera": {"mode": "follow", "target": "tao", "view_height": 360, "include": ["char:pip"]},
                 "sound_cues": [{"on_event": "notice", "sound": "notice", "gain": 0.7}]},
                {"id": "s4_friends", "start": 9, "end": 12, "kind": "medium", "cut_on": "event:stood_up@pip", "cut_offset": 0.2,
                 "description": "back on his feet; a fist bump", "fade_out": 0.8,
                 "camera": {"mode": "follow", "target": "pip", "view_height": 300, "include": ["char:tao"]},
                 "sound_cues": [{"on_event": "fist_bump", "sound": "tap", "gain": 0.9}]}]}]}


if __name__ == "__main__":
    proj, rep = solve(ProjectSpec.model_validate(project()), "bay")
    print(rep.summary())
    if not rep.success:
        sys.exit(1)
    proj = resolve_cuts(proj, "bay")
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(proj.model_dump_json(indent=1, exclude_defaults=True))
    for s in proj.scenes[0].shots:
        print(f"{s.id:12s} {s.start:6.2f} - {s.end:6.2f}")
