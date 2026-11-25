"""Native C6 standing-blocker demonstration, shared with acceptance test geometry."""
import json
import sys
from pathlib import Path

def _two_char_scene(iko_x, pell_x, iko_target, pell_actions):
    def _actor(cid, color):
        return {"id": cid, "name": cid.upper(), "strength": 52000,
                "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
                "style": {"visual_profile": "apex_ink", "performance_profile": "continuous", "body_color": color,
                          "far_color": "#888888", "glow_color": color, "has_scarf": False, "limb_width": 8.0}}
    return {"schema_version": "0.1", "id": "blk", "title": "Blocked", "fps": 24, "width": 1280, "height": 720,
            "seed": 7, "characters": [_actor("iko", "#ffd04e"), _actor("pell", "#59d6ed")],
            "environments": [{"id": "e", "room": {"width": 2200, "height": 800, "depth_back": 400,
                              "entry_door": False, "grid_spacing": 160, "grid_alpha": 0.1, "style": "open"},
                              "gravity": [0, -1568], "dust": 8,
                              "obstacles": [{"id": "ground", "kind": "platform", "style": "girder",
                                             "color": "#3b4b57", "center": [0, -32], "size": [2200, 64]}], "props": []}],
            "scenes": [{"id": "s", "title": "s", "environment": "e", "duration": 6.0,
                        "placements": [{"character": "iko", "x": iko_x, "facing": 1, "z": 0},
                                       {"character": "pell", "x": pell_x, "facing": -1, "z": 0}],
                        "actions": [{"character": "iko", "type": "run_to", "target_x": iko_target, "speed": 360}]
                                   + pell_actions, "goals": [],
                        "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
                        "shots": [{"id": "w", "kind": "wide", "start": 0, "end": 6.0,
                                   "camera": {"mode": "static", "center": [0, 200], "view_height": 700}}]}]}


if __name__ == "__main__":
    raw = _two_char_scene(-950, -530, 1050, [])
    raw["characters"].append({**raw["characters"][1], "id": "ren", "name": "REN", "style": {**raw["characters"][1]["style"], "body_color": "#ef826b", "glow_color": "#ef826b"}})
    raw["environments"][0]["room"]["width"] = 3000
    raw["environments"][0]["obstacles"][0]["size"][0] = 3000
    raw["environments"][0]["room"]["road_view"] = True
    raw["id"] = "combined_crossing"
    raw["title"] = "Push, fall, assess, jump"
    scene = raw["scenes"][0]
    scene["placements"].append({"character": "ren", "x": 100, "facing": -1, "z": 0})
    scene["actions"].insert(0, {"character": "iko", "type": "gesture", "gesture": "nudge", "target": "char:pell", "reaction": "stagger", "distance": 65, "speed": 300})
    scene["actions"].insert(1, {"character": "iko", "type": "gesture", "gesture": "nudge", "target": "char:ren", "reaction": "knockdown", "distance": 65, "speed": 360, "note": "forward_crossing"})
    scene["actions"][2]["adaptive_avoidance"] = True
    scene["duration"] = 12.0
    scene["shots"][0]["end"] = 12.0
    scene["shots"][0]["camera"] = {"mode": "follow", "target": "iko", "view_height": 650, "include": [], "keep_in_frame": True, "offset": [0, 0]}
    scene["goals"] = ["nudge@iko[with=pell]", "nudge_reaction@pell[by=iko]", "nudge_clear@iko[with=pell]", "nudge@iko[with=ren]", "settled@ren", "adaptive_jump@iko", "takeoff@iko"]
    Path(sys.argv[1]).write_text(json.dumps(raw), encoding="utf-8")
