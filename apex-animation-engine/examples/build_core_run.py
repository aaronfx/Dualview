"""Build examples/core_run.json: "CORE RUN", a 2-3 minute action film (after Milestone 6).

VEX, a red rival, ambushes IKO and PELL on the rooftops of a rainy neon city and hunts them across five worlds. They
run, leap, flip, roll, vault, climb and fight back, smashing whatever is in the way, and win it together.
No dialogue; every scene is action. Each scene is simulated, rendered and checked on its own and joined by
`apex film`; cuts, slow motion and the score are placed from the simulated events.

    PYTHONPATH=src python examples/build_core_run.py examples/core_run.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_last_retry import CHARACTERS as DUO, THEME, act, cam, cue, cut, plat, shot  # noqa: E402

TOP = 600.0
Y = TOP + 110
VEX = {"id": "vex", "name": "VEX", "strength": 56000, "proportions": {"spine": 31, "chest": 30, "head": 22, "thigh": 47, "shin": 45},
       "style": {"body_color": "#ff4a5a", "far_color": "#9a2232", "visor_color": "#ffffff", "glow_color": "#ff8a8a",
                 "has_scarf": False, "limb_width": 8.0, "cadence_scale": 1.0}}
CHARACTERS = DUO + [VEX]


def world(id_, kind, obstacles, props=(), width=4000, weather="none", amount=1.0, exits=(), **bd):
    b = {"kind": kind, "seed": abs(hash(id_)) % 97, "weather": weather, "weather_amount": amount}
    b.update(bd)
    return {"id": id_, "room": {"width": width, "height": 1600, "depth_back": 300, "entry_door": False, "style": "open"},
            "theme": THEME, "dust": 0, "obstacles": list(obstacles), "props": list(props), "backdrop": b, "exits": list(exits)}


def glyph(id_, g, x, y, size=46.0, mass=4.0, color="#7dffb2", **kw):
    return dict(id=id_, kind="glyph", glyph=g, position=[x, y], size=[size, size], mass=mass, weight=12.0, color=color, z=0.0,
                depth=16.0, friction=0.9, **kw)


def glass(id_, x, y, w=40.0, h=90.0):
    return dict(id=id_, kind="canister", position=[x, y + h / 2], size=[w, h], mass=3.0, z=20.0, depth=22.0, friction=0.5,
                breakable={"impulse": 260.0, "scatter": 120.0}, color="#9ff4ff")


def gate(s=TOP + 130):
    return {"id": "gate", "surface": "wall_right", "s": s, "width": 260, "sealed": False, "open_radius": 300}


A = lambda cid, typ, **kw: dict(character=cid, type=typ, **kw)  # noqa: E731


# ------------------------------------------------------------------ 1. the ambush (city rooftops, night, rain)
def city():
    obs = [plat("R1", -2000, -700, style="roof"), plat("R2", -480, 640, top=TOP - 50, style="roof"),
           plat("R3", 860, 2000, style="roof"),
           dict(id="vent", kind="beam", center=[120.0, TOP - 50 + 30], size=[70.0, 60.0])]
    props = [glyph("bar", "-", -980, TOP + 8, size=70.0, mass=4.5, color="#59e3ff"),
             glyph("x", "x", 360, TOP - 50 + 25, size=50.0, mass=5.0, color="#ffd84a"),
             glass("case", 430, TOP - 50), glass("case2", 474, TOP - 50, w=34, h=70)]
    return world("city", "city", obs, props, weather="rain", amount=1.3, exits=[gate()])


def scene_city():
    I, P, V = "iko", "pell", "vex"
    acts = [
        # the two race across the roof, laughing
        A(I, "run_to", target_x=-1350, lane=-20), A(I, "wait_for", until="event:throw_start@vex"),
        A(I, "dodge", dodge="duck"),
        A(I, "run_to", target_x=-1060), A(I, "guard", duration=0.3),
        A(I, "strike", target="char:vex", move="jab"), A(I, "strike", target="char:vex", move="cross"),
        A(I, "wait_for", until="next:strike_start@vex"), A(I, "dodge", dodge="back"),
        A(I, "run_to", target_x=-760), A(I, "jump_to", target_x=-400, height=130, flip="front", onto="obstacle:R2"),
        A(I, "run_to", target_x=40), A(I, "vault", target="obstacle:vent"),
        A(I, "run_to", target_x=560), act(I, "recover_relief_shake", 0.9, "determined"),
        A(I, "wait_for", until="next:takeoff@vex"), A(I, "run_to", target_x=600),
        A(I, "jump_to", target_x=1080, height=150, onto="obstacle:R3"),
        A(I, "roll", distance=240),
        A(I, "run_to", target_x=1700), A(I, "reach_exit", target="exit:gate", speed=300),
        A(P, "run_to", target_x=-1480, lane=20), A(P, "wait_for", until="event:throw_start@vex"),
        act(P, "shock", 1.2, "scared"), A(P, "wait_for", until="event:turn@vex"),
        A(P, "run_to", target_x=-800), A(P, "wait_for", until="event:impact@iko"),
        A(P, "run_to", target_x=-760), A(P, "jump_to", target_x=-330, height=110, onto="obstacle:R2"),
        act(P, "lose_balance", 0.8, "scared"), A(P, "wait_for", until="event:knockdown@iko"),
        act(P, "shock", 0.8, "scared"),
        A(P, "run_to", target_x=-60), A(P, "jump_to", target_x=260, height=140, onto="obstacle:R2"),
        A(P, "run_to", target_x=580), A(P, "jump_to", target_x=1020, height=140, onto="obstacle:R3"),
        A(P, "run_to", target_x=1650), A(P, "reach_exit", target="exit:gate", speed=280),
        # VEX: waiting with a bar; the throw, the brawl, then away across the roofs
        A(V, "pick_up", target="prop:bar"), A(V, "look_at", target="char:iko", duration=1.2),
        A(V, "throw", target="char:iko", power=1.1),
        A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.9),
        A(V, "strike", target="char:iko", move="roundhouse", power=1.1),
        A(V, "turn", face=1), A(V, "run_to", target_x=-760),
        A(V, "jump_to", target_x=-150, height=150, flip="front", onto="obstacle:R2"),
        A(V, "run_to", target_x=40), A(V, "vault", target="obstacle:vent"),
        A(V, "pick_up", target="prop:x"), A(V, "throw", target="char:iko", power=0.9),
        A(V, "turn", face=1), A(V, "run_to", target_x=600, lane=-45), A(V, "jump_to", target_x=1150, height=160, flip="back", onto="obstacle:R3"),
        A(V, "run_to", target_x=1760), A(V, "reach_exit", target="exit:gate", speed=320)]
    return {"id": "city", "title": "Ambush", "environment": "city", "duration": 40.0, "transition_in": "fade",
            "placements": [{"character": I, "x": -1850, "on": "obstacle:R1", "z": -10}, {"character": P, "x": -1960, "on": "obstacle:R1", "z": 10},
                           {"character": V, "x": -900, "on": "obstacle:R1", "facing": -1}],
            "hud": {"messages": [{"text": "CORE RUN", "at": 0.6, "duration": 2.6, "style": "title"}]},
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 2. the tower (storm, steel scaffolding)
def tower():
    up = TOP + 190
    obs = [plat("G1", -2000, -480, style="girder"), plat("G2", -460, 360, top=up, style="girder"),
           plat("G3", 600, 2000, top=up, style="girder")]
    props = [dict(id="crate", kind="crate", position=[1180.0, up + 35], size=[70.0, 70.0], mass=6.0, z=10.0, depth=40.0,
                  breakable={"impulse": 900.0, "grid": 2}, color="#8a6a3a"),
             dict(id="crate2", kind="crate", position=[1250.0, up + 30], size=[60.0, 60.0], mass=5.0, z=10.0, depth=40.0,
                  breakable={"impulse": 900.0, "grid": 2}, color="#7a5a32")]
    return world("tower", "tower", obs, props, weather="rain", amount=1.6, lightning=True, exits=[gate(s=up + 130)])


def scene_tower():
    I, P, V = "iko", "pell", "vex"
    acts = [
        A(I, "run_to", target_x=-560), A(I, "climb", target="obstacle:G2"),
        A(I, "run_to", target_x=300), A(I, "jump_to", target_x=820, height=140, flip="front", onto="obstacle:G3"),
        A(I, "guard", duration=0.25), A(I, "strike", target="char:vex", move="jab"), A(I, "strike", target="char:vex", move="cross"),
        A(I, "wait_for", until="next:strike_start@vex"), A(I, "dodge", dodge="back"),
        A(I, "strike", target="char:vex", move="roundhouse", power=1.1),  # VEX goes flying into the crates
        act(I, "cheer", 1.4, "joyful"), A(I, "turn", face=-1), act(I, "laugh", 2.4, "joyful"),  # too soon
        A(I, "wait_for", until="event:knockdown@iko"), A(I, "get_up", target="char:pell"),
        A(I, "run_to", target_x=1700), A(I, "reach_exit", target="exit:gate", speed=300),
        A(P, "run_to", target_x=-570), A(P, "climb", target="obstacle:G2"), act(P, "lose_balance", 0.8, "scared"),
        A(P, "run_to", target_x=300), A(P, "jump_to", target_x=760, height=120, onto="obstacle:G3"),
        A(P, "wait_for", until="event:knockdown@iko"), act(P, "shock", 0.7, "scared"),
        A(P, "offer_hand", target="char:iko"),
        A(P, "run_to", target_x=1650), A(P, "reach_exit", target="exit:gate", speed=280),
        A(V, "run_to", target_x=-570), A(V, "climb", target="obstacle:G2"),
        A(V, "run_to", target_x=300), A(V, "jump_to", target_x=1000, height=150, flip="back", onto="obstacle:G3"),
        A(V, "turn", face=-1), A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.7),
        A(V, "strike", target="char:iko", move="hook", power=0.9),
        A(V, "guard", until="next:strike_start@iko"),
        A(V, "wait_for", until="event:knockdown@vex"), A(V, "get_up"),  # up out of the wreckage, behind IKO's back
        A(V, "strike", target="char:iko", move="sweep", power=1.4, reaction="knockdown"),
        act(V, "laugh", 1.0, "joyful"), A(V, "turn", face=1),
        A(V, "run_to", target_x=1700), A(V, "reach_exit", target="exit:gate", speed=320)]
    return {"id": "tower", "title": "The tower", "environment": "tower", "duration": 40.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1500, "on": "obstacle:G1", "z": -10}, {"character": P, "x": -1650, "on": "obstacle:G1", "z": 10},
                           {"character": V, "x": -1050, "on": "obstacle:G1"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


def project(scenes=None):
    return {"schema_version": "0.1", "id": "core_run", "title": "CORE RUN", "fps": 24, "width": 1920, "height": 1080, "seed": 77,
            "characters": CHARACTERS, "environments": [city(), tower()], "scenes": scenes or [scene_city(), scene_tower()]}


if __name__ == "__main__":
    json.dump(project(), open(sys.argv[1], "w"), indent=1)
