"""Build examples/specimen.json: "The Specimen" (Milestone 5 test film).

A lab at night. A specimen (a composite creature: a "0" body on "!" legs, a "0" eye and a "-" tail) roams the floor.
It walks into a glass vial, which topples and shatters. ODA, at her bench, notices; she picks up a "-", which becomes
an "x" in her hand, and throws it. The blow tears the specimen apart into its symbols, and its body, after a beat,
reforms as a "?". ODA walks over and points at it.

Everything is simulated: the vial breaks under its own impact (breakable), the "x" is a morph that keeps its motion,
the specimen is held together by joints that a hard enough blow tears, and the diagram layer shows only measured
numbers. The cuts are placed from the simulated events.

    PYTHONPATH=src python examples/build_specimen.py examples/specimen.json
"""
import json
import sys

CREATURE = {
    "id": "spec", "body": "0", "size": [70.0, 48.0], "position": [760.0, 96.0], "mass": 5.0, "color": "#7cff9a", "z": 30.0,
    "depth": 30.0, "breaks": 1800.0, "stride": 55.0,
    "parts": [{"glyph": "!", "size": [14.0, 54.0], "at": [-20.0, -14.0], "role": "leg", "phase": 0.0},
              {"glyph": "!", "size": [14.0, 54.0], "at": [20.0, -14.0], "role": "leg", "phase": 3.14159},
              {"glyph": "0", "size": [13.0, 13.0], "at": [-24.0, 8.0], "role": "eye", "mass": 0.2, "color": "#ffffff"},
              {"glyph": "-", "size": [34.0, 8.0], "at": [38.0, 4.0], "role": "tail", "mass": 0.4, "pivot": [-17.0, 0.0]}],
    "path": [[1.2, 760.0], [7.4, -120.0]],
    "morphs": [{"to": "?", "on": "creature_break@spec", "delay": 0.9, "duration": 0.8}],  # the punchline
}


def project(shots=None, duration=17.0):
    D = duration
    return {
        "schema_version": "0.1", "id": "specimen", "title": "The Specimen", "fps": 24, "width": 1280, "height": 720, "seed": 41,
        "characters": [{"id": "oda", "name": "ODA", "strength": 50000,
                        "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
                        "style": {"body_color": "#ffb86b", "far_color": "#b87a3a", "visor_color": "#7cf6ff", "glow_color": "#ffd29a",
                                  "scarf_color": "#7cf6ff", "has_scarf": True, "limb_width": 7.5}}],
        "environments": [{
            "id": "lab", "room": {"width": 1800, "height": 760, "depth_back": 520, "grid_spacing": 80, "grid_alpha": 0.25,
                                  "entry_door": False},
            "theme": {"accent": "#7cf6ff", "alert": "#ff5a5a", "back": "#171a24", "floor": "#0c0e14", "side": "#12151d",
                      "ceiling": "#08090d", "background": "#040507", "dust": "#cfefff"},
            "dust": 50,
            "decor": [
                {"kind": "window", "x": -420, "y": 300, "w": 520, "h": 300, "seed": 3},
                {"kind": "panel", "x": 330, "y": 150, "w": 260, "h": 190, "color": "#7cf6ff", "seed": 1},
                {"kind": "screen", "x": 330, "y": 380, "w": 210, "h": 120, "color": "#7cff9a", "text": "SPECIMEN 01", "seed": 2},
                {"kind": "screen", "x": 700, "y": 300, "w": 150, "h": 100, "color": "#ffb86b", "text": "GAIT", "seed": 5},
                {"kind": "pipe", "x": -900, "y": 650, "x2": 900, "y2": 650},
                {"kind": "pipe", "x": 560, "y": 650, "x2": 560, "y2": 0},
                {"kind": "shelf", "x": -780, "y": 420, "w": 180, "seed": 7},
                {"kind": "shelf", "x": 60, "y": 470, "w": 160, "seed": 9},
                {"kind": "lamp", "x": -600, "w": 230},
                {"kind": "lamp", "x": 150, "w": 230},
                {"kind": "bench", "x": -760, "y": 0, "w": 220, "h": 80, "z": 160}],
            "props": [
                {"id": "vial", "kind": "canister", "position": [150.0, 36.0], "size": [26.0, 70.0], "mass": 2.5, "z": 30.0, "depth": 22.0,
                 "friction": 0.5, "breakable": {"impulse": 380.0, "scatter": 90.0}},
                {"id": "bar", "kind": "glyph", "glyph": "-", "position": [-520.0, 7.0], "size": [44.0, 44.0], "mass": 3.5, "weight": 9.0,
                 "color": "#ffd84a", "z": 20.0, "depth": 16.0,
                 "morphs": [{"to": "x", "on": "pick_up@oda", "duration": 0.6}]}],
            "creatures": [CREATURE]}],
        "scenes": [{
            "id": "lab", "title": "The Specimen", "environment": "lab", "duration": D,
            "goals": ["break@vial", "notice@oda", "pick_up@oda", "morph@bar", "throw@oda", "creature_break@spec", "morph@spec.body",
                      "point@oda"],
            "placements": [{"character": "oda", "x": -700.0, "facing": 1, "z": 20}],
            "actions": [
                {"character": "oda", "type": "look_at", "target": "point:-760,90", "duration": 1.5},
                {"character": "oda", "type": "wait_for", "until": "event:break@vial"},
                {"character": "oda", "type": "notice", "target": "prop:vial", "duration": 0.8},
                {"character": "oda", "type": "pick_up", "target": "prop:bar"},
                {"character": "oda", "type": "look_at", "target": "prop:spec.body", "duration": 0.5},
                {"character": "oda", "type": "throw", "target": "point:-120,100"},
                {"character": "oda", "type": "wait_for", "until": "event:morph@spec.body"},
                {"character": "oda", "type": "walk_to", "target_x": -250.0},
                {"character": "oda", "type": "point", "target": "prop:spec.body"},
                {"character": "oda", "type": "idle", "duration": 3.0}],
            "shots": shots or [{"id": "wide", "start": 0.0, "end": D, "kind": "wide",
                                "camera": {"mode": "static", "center": [0, 330], "view_height": 800}}]}]}


DIAGRAMS = [
    {"id": "tag", "kind": "label", "target": "creature:spec", "t0": 1.4, "t1": 5.4, "text": "SPECIMEN 01   {speed}", "color": "#7cff9a"},
    {"id": "vial_hit", "kind": "impulse", "target": "prop:vial", "t0": 0.0, "t1": 30.0, "duration": 1.6},
    {"id": "throw_path", "kind": "trajectory", "target": "prop:bar", "on": "throw@oda", "duration": 1.2, "color": "#ffd84a"},
    {"id": "throw_v", "kind": "velocity", "target": "prop:bar", "on": "throw@oda", "duration": 0.3, "scale": 0.08, "color": "#ffd84a"},
    {"id": "tear", "kind": "impulse", "target": "creature:spec", "t0": 0.0, "t1": 30.0, "duration": 1.8, "color": "#ff7a7a"},
]


def event_times(proj):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), "lab").simulate(physics_only=True)
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
    return ev


def shots_from(ev, D):
    f = lambda k, i=0: ev[k][i]
    c = [0.0,
         round(f("break@vial") - 1.6, 2),             # 1 the lab -> the specimen walks into the vial
         round(f("notice@oda") - 0.35, 2),            # 2 the vial topples and shatters -> ODA turns
         round(f("throw_start@oda") - 0.1, 2),        # 3 ODA notices, picks up the "-", it becomes an "x"
         round(f("creature_break@spec") + 1.3, 2),    # 4 the throw, the hit, the specimen comes apart (one shot: cause and effect)
         D]                                            # 5 its body reforms as a "?"; ODA walks over and points
    S = [
        dict(id="s01_lab", kind="establishing", description="the lab at night: ODA at her bench, the specimen walking the floor",
             camera=dict(mode="dolly", center=[-40, 330], center_end=[-60, 300], view_height=860, view_height_end=790, bound_to_room=True)),
        dict(id="s02_vial", kind="medium", description="the specimen walks into the glass vial; it topples and shatters",
             camera=dict(mode="follow", target=None, view_height=360, include=["prop:vial"])),
        dict(id="s03_oda", kind="medium", description="ODA turns, takes in the shards, and picks up the minus; it becomes a times",
             camera=dict(mode="follow", target="oda", view_height=380, offset=[60, 20], lead=0.15, stiffness=4.0)),
        dict(id="s04_throw", kind="wide", description="the throw: the x flies across the lab and tears the specimen apart",
             camera=dict(mode="static", target="oda", center=[-320, 260], view_height=560, include=["prop:spec.body"], bound_to_room=True)),
        dict(id="s05_question", kind="medium", description="the pieces settle; the body reforms as a question mark; ODA walks over and points",
             camera=dict(mode="static", target="oda", center=[-200, 200], view_height=440, include=["prop:spec.body"], bound_to_room=True),
             fade_out=1.0),
    ]
    S[1]["camera"] = dict(mode="static", center=[200, 150], view_height=380, bound_to_room=True, include=["prop:vial", "prop:spec.body"])
    for i, sh in enumerate(S):
        sh["start"], sh["end"] = c[i], c[i + 1]
    return S


if __name__ == "__main__":
    out = sys.argv[1]
    proj = project()
    proj = project(shots=shots_from(event_times(proj), proj["scenes"][0]["duration"]))
    proj["scenes"][0]["diagrams"] = DIAGRAMS
    json.dump(proj, open(out, "w"), indent=1)
    for sh in proj["scenes"][0]["shots"]:
        print(f"{sh['id']:14s} {sh['start']:6.2f} - {sh['end']:6.2f}  {sh['description']}")
