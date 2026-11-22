"""CORE RUN - first independently built Director's Cut production draft.

Five original worlds, a stolen core with verified physical custody, an earned
team victory, and an event-driven restoration at the summit. This is authored
choreography, not an AI-autonomous film. Do not mark final before QA + review.

Usage:
  PYTHONPATH=src python examples/build_core_run_directors_cut.py examples/core_run_directors_cut.json
  apex film examples/core_run_directors_cut.json -o out/core_run/CORE_RUN_720p.mp4 --preset draft
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_core_run as base
from build_last_retry import act, cam, shot, cut, cue

A = base.A
TOP = base.TOP
Y = base.Y


def scene_props(env):
    """A plot-critical physical object with a stable ID in each world."""
    env["props"].append(base.glyph("core", "0", -770, TOP + 17, size=30, mass=1.0, color="#ffe77a"))
    return env


def city():
    env = base.city()
    # Replace the original cases with an actual rooftop theft at the beginning.
    env["props"] = [p for p in env["props"] if p["id"] not in ("case", "case2")]
    env["props"].append(base.glass("case", -1150, TOP, w=48, h=82))
    env["props"].append(base.glyph("core", "0", -1020, TOP + 18, size=34, mass=1.0, color="#ffe77a"))
    env["props"] = [dict(p, position=[-1430, TOP + 8]) if p["id"] == "bar" else p for p in env["props"]]
    env["backdrop"]["seed"] = 55
    return env


def tower():
    env = base.tower()
    env["props"].append(base.glyph("core", "0", -1000, TOP + 8, size=34, mass=1.0, color="#ffe77a"))
    env["backdrop"]["seed"] = 56
    return env


def canyon():
    env = base.canyon()
    env["props"].append(base.glyph("core", "0", -1000, TOP + 8, size=34, mass=1.0, color="#ffe77a"))
    env["backdrop"]["seed"] = 57
    return env


def arena():
    env = base.arena()
    env["props"].append(base.glyph("core", "0", 210, TOP + 18, size=34, mass=1.0, color="#ffe77a"))
    env["backdrop"]["seed"] = 58
    return env


def summit():
    env = base.summit()
    env["props"].append(base.glyph("core", "0", -880, TOP + 18, size=34, mass=1.0, color="#ffe77a"))
    env["backdrop"]["seed"] = 59
    return env


def film_scene(scene_id, duration, placements, actions, *, entry="warp", owner_in="vex",
               owner_out="vex", world_power=None, restoration=None, goals=(), title=None):
    data = {
        "id": scene_id,
        "title": title or scene_id.title(),
        "environment": scene_id,
        "duration": duration,
        "transition_in": entry,
        "placements": placements,
        "actions": actions,
        "shots": [{"id": "initial", "start": 0, "end": duration,
                   "camera": {"mode": "follow", "target": "iko", "view_height": 920}}],
        "story_props": [{"prop": "core", "owner_in": owner_in, "owner_out": owner_out}],
        "goals": list(goals),
    }
    if restoration is not None:
        data["restoration"] = restoration
    if world_power is not None:
        data["world_power"] = world_power
    return data


def scene_city():
    I, P, V = "iko", "pell", "vex"
    actions = [
        # VEX physically breaks the case with a thrown glyph, steals the core,
        # and escapes with it (the tracked ownership is not a visual-only trick).
        A(V, "pick_up", target="prop:bar"),
        A(V, "throw", target="prop:case", power=1.6),
        A(V, "run_to", target_x=-1020),
        A(V, "pick_up", target="prop:core"),
        A(V, "notice", target="char:iko", duration=0.35),
        A(V, "run_to", target_x=-960),
        A(V, "jump_to", target_x=-140, height=165, onto="obstacle:R2"),
        A(V, "run_to", target_x=25),
        A(V, "vault", target="obstacle:vent"),
        A(V, "run_to", target_x=585),
        A(V, "jump_to", target_x=1100, height=140, flip="front", onto="obstacle:R3"),
        A(V, "run_to", target_x=1710),
        A(V, "reach_exit", target="exit:gate", speed=300),
        A(I, "run_to", target_x=-1410),
        A(I, "wait_for", until="event:throw@vex"),
        act(I, "shock", 0.65, "scared"),
        A(I, "run_to", target_x=-780),
        A(I, "notice", target="prop:case", duration=0.4),
        A(I, "run_to", target_x=-750),
        A(I, "jump_to", target_x=-220, height=160, flip="front", onto="obstacle:R2"),
        A(I, "run_to", target_x=38),
        A(I, "vault", target="obstacle:vent"),
        A(I, "run_to", target_x=600),
        A(I, "jump_to", target_x=1040, height=155, onto="obstacle:R3"),
        A(I, "roll", distance=140),
        A(I, "run_to", target_x=1690),
        A(I, "reach_exit", target="exit:gate", speed=310),
        A(P, "run_to", target_x=-1500, lane=20),
        A(P, "wait_for", until="event:pick_up@vex[prop=core]"),
        act(P, "shock", 0.5, "scared"),
        A(P, "run_to", target_x=-755),
        A(P, "jump_to", target_x=-290, height=145, onto="obstacle:R2"),
        A(P, "run_to", target_x=565),
        A(P, "jump_to", target_x=1000, height=150, onto="obstacle:R3"),
        A(P, "run_to", target_x=1650),
        A(P, "reach_exit", target="exit:gate", speed=300),
    ]
    return film_scene(
        "city", 43, [
            {"character": I, "x": -1870, "on": "obstacle:R1", "z": -15},
            {"character": P, "x": -1960, "on": "obstacle:R1", "z": 15},
            {"character": V, "x": -1620, "on": "obstacle:R1", "facing": 1},
        ], actions, entry="fade", owner_in="world", owner_out="vex",
        title="The Theft",
        world_power={"initial": 1.0, "cues": [
            {"on": "pick_up@vex[prop=core]", "level": 0.28, "fade": 2.4}
        ]},
    )


def scene_tower():
    I, P, V = "iko", "pell", "vex"
    actions = [
        A(V, "run_to", target_x=-570, lane=35),
        A(V, "climb", target="obstacle:G2"),
        A(V, "run_to", target_x=300),
        A(V, "jump_to", target_x=990, height=150, flip="back", onto="obstacle:G3"),
        A(V, "turn", face=-1),
        A(V, "guard", until="next:strike_start@iko"),
        A(V, "guard", duration=0.35),
        A(V, "strike", target="char:iko", move="sweep", power=1.8, reaction="knockdown"),
        act(V, "laugh", 0.75, "joyful"),
        A(V, "turn", face=1),
        A(V, "run_to", target_x=1680),
        A(V, "reach_exit", target="exit:gate", speed=325),
        A(I, "run_to", target_x=-550),
        A(I, "climb", target="obstacle:G2"),
        A(I, "run_to", target_x=310),
        A(I, "jump_to", target_x=820, height=135, onto="obstacle:G3"),
        A(I, "strike", target="char:vex", move="jab", power=0.6),
        A(I, "strike", target="char:vex", move="cross", power=0.65),
        A(I, "wait_for", until="event:knockdown@iko"),
        A(I, "get_up", target="char:pell"),
        act(I, "rise", 0.5, "determined"),
        A(I, "run_to", target_x=1650),
        A(I, "reach_exit", target="exit:gate", speed=315),
        A(P, "run_to", target_x=-550, lane=20),
        A(P, "climb", target="obstacle:G2"),
        A(P, "run_to", target_x=300),
        A(P, "jump_to", target_x=760, height=128, onto="obstacle:G3"),
        A(P, "wait_for", until="event:knockdown@iko"),
        act(P, "shock", 0.35, "scared"),
        A(P, "offer_hand", target="char:iko"),
        A(P, "run_to", target_x=1640),
        A(P, "reach_exit", target="exit:gate", speed=300),
    ]
    return film_scene(
        "tower", 43, [
            {"character": I, "x": -1540, "on": "obstacle:G1", "z": -10},
            {"character": P, "x": -1660, "on": "obstacle:G1", "z": 10},
            {"character": V, "x": -1010, "on": "obstacle:G1"},
        ], actions, title="The Storm Tower",
        world_power={"initial": 0.3},
    )


def scene_canyon():
    I, P, V = "iko", "pell", "vex"
    actions = [
        A(V, "run_to", target_x=750, speed=380, lane=40),
        A(V, "turn", face=-1),
        act(V, "laugh", 0.6, "joyful"),
        A(V, "wait_for", until="event:creature_break@drone"),
        A(V, "turn", face=1),
        A(V, "run_to", target_x=1690, speed=370),
        A(V, "reach_exit", target="exit:gate", speed=330),
        A(I, "run_to", target_x=-860, lane=-20),
        A(I, "wait_for", until="event:collapse@bridge"),
        act(I, "shock", 0.45, "scared"),
        A(I, "run_to", target_x=300, speed=390),
        A(I, "roll", distance=150),
        A(I, "run_to", target_x=1680, speed=375, lane=-35),
        A(I, "reach_exit", target="exit:gate", speed=310),
        A(P, "run_to", target_x=-960, lane=20),
        A(P, "wait_for", until="event:roll_end@iko"),
        A(P, "run_to", target_x=325, speed=380),
        A(P, "pick_up", target="prop:x"),
        A(P, "throw", target="prop:drone.body", power=1.9),
        A(P, "wait_for", until="event:creature_break@drone"),
        act(P, "cheer", 0.7, "joyful"),
        A(P, "run_to", target_x=1640, speed=350),
        A(P, "reach_exit", target="exit:gate", speed=300),
    ]
    return film_scene(
        "canyon", 41, [
            {"character": I, "x": -1750, "on": "obstacle:A", "z": -10},
            {"character": P, "x": -1880, "on": "obstacle:A", "z": 10},
            {"character": V, "x": -1100, "on": "obstacle:A"},
        ], actions, title="The Collapsing Canyon",
        world_power={"initial": 0.32},
    )


def scene_arena():
    I, P, V = "iko", "pell", "vex"
    actions = [
        # VEX physically puts down the core before drawing a staff; this frees
        # the one-hand-carry slot. PELL's thrown glyph disarms him on contact.
        A(V, "place_prop", target=f"point:205,{TOP + 65}", duration=0.55),
        A(V, "pick_up", target="prop:staff"),
        A(V, "turn", face=-1),
        A(V, "guard", until="next:strike_start@iko"),
        A(V, "guard", duration=0.4),
        A(V, "strike", target="char:iko", move="swing_weapon", power=1.6, reaction="knockdown"),
        act(V, "laugh", 0.8, "joyful"),
        A(V, "wait_for", until="event:disarmed@vex"),
        act(V, "shock", 0.75, "scared"),
        A(V, "wait_for", until="event:knockdown@vex"),
        A(I, "run_to", target_x=-265, lane=-10),
        A(I, "guard", duration=0.2),
        A(I, "strike", target="char:vex", move="jab", power=0.5),
        A(I, "wait_for", until="event:knockdown@iko"),
        A(I, "get_up"),
        act(I, "rise", 0.5, "determined"),
        A(I, "wait_for", until="event:disarmed@vex"),
        A(I, "run_to", target_x=-260),
        A(I, "strike", target="char:vex", move="flying_kick", power=1.7, reaction="knockdown"),
        A(I, "wait_for", until="event:knockdown@vex"),
        A(I, "pick_up", target="prop:core"),
        act(I, "cheer", 0.8, "joyful"),
        A(P, "run_to", target_x=-755, lane=20),
        A(P, "wait_for", until="event:knockdown@iko"),
        act(P, "shock", 0.45, "scared"),
        A(P, "pick_up", target="prop:x"),
        A(P, "throw", target="char:vex", power=1.4, disarm=True),
        act(P, "rise", 0.55, "determined"),
        A(P, "wait_for", until="event:knockdown@vex"),
        act(P, "cheer", 0.85, "joyful"),
    ]
    return film_scene(
        "arena", 46, [
            {"character": I, "x": -1500, "on": "obstacle:floor", "z": -10},
            {"character": P, "x": -1620, "on": "obstacle:floor", "z": 10},
            {"character": V, "x": 25, "on": "obstacle:floor", "facing": -1},
        ], actions, title="The Final Battle",
        owner_in="vex", owner_out="iko",
        world_power={"initial": 0.22},
    )


def scene_summit():
    I, P = "iko", "pell"
    actions = [
        A(I, "run_to", target_x=310, speed=310, lane=-10),
        A(I, "place_prop", target=f"point:405,{TOP + 60}", duration=0.65),
        A(I, "wait_for", until="event:core_restored@core"),
        act(I, "recover_relief", 1.0, "relieved"),
        A(I, "gesture", target="char:pell", gesture="fist_bump"),
        act(I, "cheer", 1.6, "joyful"),
        A(P, "run_to", target_x=320, speed=300, lane=10),
        A(P, "wait_for", until="event:core_restored@core"),
        act(P, "shock", 0.6, "joyful"),
        A(P, "gesture", target="char:iko", gesture="fist_bump"),
        act(P, "laugh", 1.6, "joyful"),
    ]
    return film_scene(
        "summit", 25, [
            {"character": I, "x": -900, "on": "obstacle:S", "z": -10},
            {"character": P, "x": -1040, "on": "obstacle:S", "z": 10},
        ], actions, title="The Return of Light",
        owner_in="iko", owner_out="world",
        restoration={"prop": "core", "at": [405, TOP + 18], "radius": 27, "max_speed": 12},
        world_power={"initial": 0.26, "cues": [
            {"on": "core_restored@core", "level": 1.0, "fade": 2.4},
        ]},
    )


def shots_for_scene(sc):
    sid, D = sc["id"], sc["duration"]
    def F(typ, target, height, desc):
        return shot(f"{sid}_{typ}", typ, desc,
                    cam("follow", target=target, view_height=height, stiffness=3, offset=[80, 45],
                        include=[]))
    if sid == "city":
        shots = [
            shot("theft", "close", "VEX breaks the case and takes the glowing core",
                 cam("static", center=[-980, Y], view_height=610, include=["char:vex"])),
            shot("lights_out", "wide", "City lights fade; IKO and PELL see the thief flee",
                 cam("dolly", center=[-1370, Y + 320], center_end=[-900, Y + 40],
                     view_height=1450, view_height_end=850)),
            F("tracking", "iko", 850, "IKO and PELL launch across the rooftops"),
            F("wide", "vex", 900, "VEX jumps the gap with the core"),
            F("medium", "iko", 820, "The heroes vault the vent and pursue"),
            F("tracking", "pell", 1050, "All converge on the tower") ]
        times = [0, 3.0, 7.0, 15.0, 23.0, 31.0, D]
    elif sid == "tower":
        shots = [
            shot("tower_height", "establishing", "The scale of the storm tower",
                 cam("dolly", center=[-950, Y + 500], center_end=[-500, Y + 100],
                     view_height=1600, view_height_end=900)),
            F("tracking", "iko", 860, "Vertical pursuit: climbs and dangerous jumps"),
            F("medium", "vex", 690, "VEX turns and fights IKO on the narrow girder"),
            F("close", "iko", 560, "IKO falls, and his confidence fails"),
            F("medium", "pell", 690, "PELL offers a hand and IKO accepts"),
            F("tracking", "vex", 1050, "The stolen core escapes toward the canyon") ]
        times = [0, 3, 12, 21, 27, 34, D]
    elif sid == "canyon":
        shots = [
            shot("canyon_scale", "establishing", "The bridge over a deep canyon",
                 cam("dolly", center=[-780, Y + 380], center_end=[-650, Y],
                     view_height=1600, view_height_end=900)),
            F("wide", "vex", 1020, "VEX reaches the other side before the bridge breaks"),
            F("tracking", "iko", 840, "IKO launches over the ruined crossing"),
            F("medium", "pell", 740, "PELL uses a thrown glyph to defeat the drone"),
            F("tracking", "pell", 1040, "The heroes rush toward the arena") ]
        times = [0, 5, 12, 22, 31, D]
    elif sid == "arena":
        shots = [
            shot("void", "establishing", "VEX places the core and draws a weapon",
                 cam("dolly", center=[-200, Y + 340], center_end=[-130, Y],
                     view_height=1400, view_height_end=780)),
            F("medium", "vex", 620, "The red rival dominates the first exchange"),
            F("close", "iko", 520, "IKO is knocked down, apparently defeated"),
            F("medium", "pell", 720, "PELL's glyph disarms VEX"),
            F("medium", "iko", 610, "IKO rises for the decisive flying kick"),
            F("medium", "iko", 640, "The heroes visibly recover the glowing core") ]
        times = [0, 5, 15, 23, 32, 39, D]
    else:
        shots = [
            F("tracking", "iko", 950, "IKO carries the stolen core to the restoration socket"),
            F("medium", "iko", 630, "The core physically settles into the socket"),
            shot("sunrise", "wide", "The city's energy returns; friends celebrate",
                 cam("dolly", center=[380, Y + 50], center_end=[400, Y + 550],
                     view_height=620, view_height_end=1550), fade_out=2.0) ]
        times = [0, 9, 15, D]
    return cut(shots, times)


def project():
    scenes = [scene_city(), scene_tower(), scene_canyon(), scene_arena(), scene_summit()]
    for s in scenes:
        s["shots"] = shots_for_scene(s)
        s["time_fx"] = {"hit_stop": True, "smears": True, "punch_in": True}
        if s["id"] == "city":
            cues = [cue("tension", at=0.0),
                    cue("action", on="pick_up@vex[prop=core]")]
        elif s["id"] == "tower":
            cues = [cue("action", at=0.0),
                    cue("sad", on="knockdown@iko"), cue("hope", on="hand_offered@pell")]
        elif s["id"] == "canyon":
            cues = [cue("action", at=0.0), cue("tension", on="collapse@bridge"),
                    cue("triumph", on="creature_break@drone")]
        elif s["id"] == "arena":
            cues = [cue("tension", at=0.0), cue("action", on="strike_start@iko"),
                    cue("sad", on="knockdown@iko"), cue("hope", on="disarmed@vex"),
                    cue("triumph", on="knockdown@vex")]
        else:
            cues = [cue("tension", at=0.0),
                    cue("triumph", on="core_restored@core")]
        s["score"] = {"key": "E", "level": 0.58, "cues": cues}
    return {
        "schema_version": "0.1",
        "id": "core_run_directors_cut",
        "title": "CORE RUN - Director's Cut (first simulation draft)",
        "fps": 24,
        "width": 1920,
        "height": 1080,
        "seed": 77,
        "characters": base.CHARACTERS,
        "environments": [city(), tower(), canyon(), arena(), summit()],
        "scenes": scenes,
        "film_goals": [
            {"scene": "city", "event": "pick_up@vex[prop=core]"},
            {"scene": "tower", "event": "knockdown@iko"},
            {"scene": "canyon", "event": "collapse@bridge"},
            {"scene": "arena", "event": "disarmed@vex"},
            {"scene": "arena", "event": "pick_up@iko[prop=core]"},
            {"scene": "summit", "event": "core_restored@core"},
        ],
    }


if __name__ == "__main__":
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    from apex.qa.film import check_film

    path = sys.argv[1] if len(sys.argv) > 1 else "examples/core_run_directors_cut.json"
    p = ProjectSpec.model_validate(project())
    with open(path, "w") as fh:
        json.dump(p.model_dump(mode="json"), fh, indent=2)
    print("Wrote", path, flush=True)
    print("Simulating all five worlds and checking story events.", flush=True)
    sim_errors = []
    for sc in p.scenes:
        try:
            result = SceneRuntime(p, sc.id).simulate(physics_only=True)
            interesting = {"pick_up", "break", "throw", "prop_placed", "disarmed",
                           "knockdown", "creature_break", "core_restored", "exit_reached"}
            evs = [(round(e.t, 2), e.type, e.character, e.data.get("prop"))
                   for e in result.events if e.type in interesting]
            print(sc.id, "events:", evs[:45], flush=True)
        except Exception as exc:
            print(sc.id, "SIMULATION FAILURE:", type(exc).__name__, str(exc), flush=True)
            sim_errors.append(f"{sc.id}: {exc}")
    if sim_errors:
        raise RuntimeError("Unresolved scene physics: " + "; ".join(sim_errors))
    for ch in check_film(p):
        if ch.name in ("plot_prop_continuity", "narrative_event_chain"):
            print(ch.name, ch.status, ch.details, flush=True)
