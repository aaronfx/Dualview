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
        A(P, "idle", duration=0.8, lane=36), A(P, "run_to", target_x=-570), A(P, "climb", target="obstacle:G2"),
        A(P, "run_to", target_x=300), A(P, "jump_to", target_x=760, height=120, onto="obstacle:G3"),
        A(P, "wait_for", until="event:knockdown@iko"), act(P, "shock", 0.7, "scared"),
        A(P, "offer_hand", target="char:iko"),
        A(P, "run_to", target_x=1650), A(P, "reach_exit", target="exit:gate", speed=280),
        A(V, "run_to", target_x=-570, lane=32), A(V, "climb", target="obstacle:G2"),
        A(V, "run_to", target_x=300, lane=0), A(V, "jump_to", target_x=1000, height=150, flip="back", onto="obstacle:G3"),
        A(V, "turn", face=-1), A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.7),
        A(V, "strike", target="char:iko", move="hook", power=0.9),
        A(V, "guard", until="next:strike_start@iko"),
        A(V, "wait_for", until="event:knockdown@vex"), A(V, "get_up"),  # up out of the wreckage, behind IKO's back
        A(V, "strike", target="char:iko", move="hook", power=1.4, reaction="knockdown"),
        act(V, "laugh", 1.0, "joyful"), A(V, "turn", face=1),
        A(V, "run_to", target_x=1700), A(V, "reach_exit", target="exit:gate", speed=320)]
    return {"id": "tower", "title": "The tower", "environment": "tower", "duration": 40.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1500, "on": "obstacle:G1", "z": -10}, {"character": P, "x": -1650, "on": "obstacle:G1", "z": 10},
                           {"character": V, "x": -1050, "on": "obstacle:G1"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 3. the canyon (sunset): the bridge, the pad, the drone
GAP = (-480.0, -40.0)


def canyon():
    obs = [plat("A", -2000, GAP[0], style="rock"), plat("C", GAP[1], 2000, style="rock"),
           plat("bridge", GAP[0], GAP[1], thick=18.0, style="bridge", color="#9a6a44",
                collapse={"at": 4.2, "pieces": 6, "color": "#9a6a44"})]
    drone = {"id": "drone", "body": "0", "size": [80.0, 54.0], "position": [1150.0, TOP + 100], "mass": 5.0, "color": "#ff4a5a",
             "z": 0.0, "breaks": 1500.0, "stride": 60.0,
             "parts": [{"glyph": "!", "size": [16.0, 60.0], "at": [-22.0, -16.0], "role": "leg", "phase": 0.0},
                       {"glyph": "!", "size": [16.0, 60.0], "at": [22.0, -16.0], "role": "leg", "phase": 3.14159},
                       {"glyph": "0", "size": [14.0, 14.0], "at": [-26.0, 8.0], "role": "eye", "mass": 0.2, "color": "#ffffff"}],
             "path": [[7.0, 1150.0], [11.0, 520.0]]}
    props = [glyph("x", "x", 340.0, TOP + 20, size=40.0, mass=5.0, color="#ffd84a")]
    w = world("canyon", "canyon", obs, props, weather="embers", amount=0.9, exits=[gate()])
    w["orbs"] = [{"id": "pad", "kind": "pad", "center": [-600.0, TOP + 6], "radius": 34.0, "power": 560.0}]
    w["creatures"] = [drone]
    return w


def scene_canyon():
    I, P, V = "iko", "pell", "vex"
    acts = [
        A(I, "run_to", target_x=-860, lane=-20), A(I, "wait_for", until="event:collapse@bridge"), act(I, "shock", 0.7, "scared"),
        A(I, "run_to", target_x=300, speed=390, lane=0),  # over the launch pad and across the gap
        A(I, "roll", distance=120), A(I, "pick_up", target="prop:x"), A(I, "throw", target="prop:drone.body", power=1.4),
        act(I, "cheer", 1.0, "joyful"),
        A(I, "run_to", target_x=1650, speed=360, lane=-35), A(I, "reach_exit", target="exit:gate", speed=320),
        A(P, "run_to", target_x=-960, lane=20), A(P, "wait_for", until="event:roll_end@iko"),
        A(P, "run_to", target_x=110, speed=380),
        A(P, "wait_for", until="event:creature_break@drone"), act(P, "cheer", 1.2, "joyful"),
        A(P, "run_to", target_x=1600, speed=340), A(P, "reach_exit", target="exit:gate", speed=300),
        A(V, "run_to", target_x=760, speed=380, lane=40), A(V, "turn", face=-1), act(V, "laugh", 1.6, "joyful"),
        A(V, "wait_for", until="event:creature_break@drone"), act(V, "shock", 0.8, "scared"), A(V, "turn", face=1),
        A(V, "run_to", target_x=1700, speed=380), A(V, "reach_exit", target="exit:gate", speed=340)]
    return {"id": "canyon", "title": "The canyon", "environment": "canyon", "duration": 40.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1750, "on": "obstacle:A", "z": -10}, {"character": P, "x": -1880, "on": "obstacle:A", "z": 10},
                           {"character": V, "x": -1100, "on": "obstacle:A"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 4. the arena (the void): the final fight
def arena():
    obs = [plat("floor", -1800, 1800, thick=60.0), plat("block", 260, 460, top=TOP + 150, thick=150.0)]
    props = [glyph("staff", "-", 120.0, TOP + 8, size=118.0, mass=5.0, color="#ff4a5a"),
             glyph("x", "x", -760.0, TOP + 25, size=50.0, mass=5.0, color="#ffd84a")]
    return world("arena", "void", obs, props, width=3600, weather="data", amount=1.0)


def scene_arena():
    I, P, V = "iko", "pell", "vex"
    acts = [
        A(I, "run_to", target_x=-320, lane=-10), A(I, "guard", duration=0.3),
        A(I, "strike", target="char:vex", move="jab"), A(I, "strike", target="char:vex", move="cross"),
        A(I, "wait_for", until="next:strike_start@vex"), A(I, "dodge", dodge="duck"),
        A(I, "strike", target="char:vex", move="roundhouse", power=1.1),
        act(I, "recover_relief_shake", 1.4, "tired"),  # out of breath, open
        A(I, "wait_for", until="event:knockdown@iko"), A(I, "get_up"),
        A(I, "run_to", target_x=-420), A(I, "turn", face=1),  # back off for a run-up
        A(I, "wait_for", until="next:stood_up@vex"), act(I, "rise", 0.6, "determined", tempo=1.8),
        A(I, "strike", target="char:vex", move="flying_kick", power=1.6, reaction="knockdown"),
        A(I, "idle", duration=0.6), A(I, "offer_hand", target="char:vex"), A(I, "wait_for", until="event:fist_bump@vex"), act(I, "cheer", 1.6, "joyful"),
        A(I, "idle", duration=4.0),
        A(P, "run_to", target_x=-640, lane=20), act(P, "shock", 0.8, "scared"),
        A(P, "wait_for", until="event:knockdown@iko"), act(P, "rise", 1.0, "determined", tempo=1.6),
        A(P, "pick_up", target="prop:x"), A(P, "throw", target="char:vex", power=1.3),
        act(P, "cheer", 1.0, "joyful"), A(P, "wait_for", until="event:knockdown@vex"), act(P, "laugh", 2.0, "joyful"),
        A(P, "idle", duration=4.0),
        A(V, "pick_up", target="prop:staff"), A(V, "turn", face=-1),
        A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.9),
        A(V, "strike", target="char:iko", move="swing_weapon", power=1.0),
        A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.4),
        A(V, "strike", target="char:iko", move="swing_weapon", power=1.5, reaction="knockdown"),
        act(V, "laugh", 1.0, "joyful"),
        A(V, "wait_for", until="event:knockdown@vex"), A(V, "get_up"),  # PELL's throw
        A(V, "wait_for", until="next:knockdown@vex"), A(V, "get_up", target="char:iko"),  # IKO's flying kick
        A(V, "gesture", target="char:iko", gesture="fist_bump"), A(V, "idle", duration=3.0)]
    return {"id": "arena", "title": "The arena", "environment": "arena", "duration": 45.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1500, "on": "obstacle:floor", "z": -10},
                           {"character": P, "x": -1620, "on": "obstacle:floor", "z": 10},
                           {"character": V, "x": 40, "on": "obstacle:floor", "facing": -1}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 45.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 5. the summit (dawn): together
def summit():
    return world("summit", "summit", [plat("S", -1800, 700, style="rock")], weather="motes", width=3600)


def scene_summit():
    I, P, V = "iko", "pell", "vex"
    acts = [A(I, "run_to", target_x=460, lane=-30, speed=330), act(I, "cheer", 1.6, "joyful"),
            A(I, "gesture", target="char:pell", gesture="fist_bump"), act(I, "laugh", 2.0, "joyful"), A(I, "idle", duration=6.0),
            A(P, "run_to", target_x=340, speed=300), A(P, "wait_for", until="event:act@iko[clip=cheer]"), A(P, "idle", duration=0.4),
            A(P, "gesture", target="char:iko", gesture="fist_bump"), act(P, "laugh", 2.0, "joyful"), A(P, "idle", duration=6.0),
            A(V, "run_to", target_x=180, speed=280, lane=30), act(V, "embarrassed", 1.6, "embarrassed"), act(V, "laugh", 2.2, "joyful"),
            A(V, "idle", duration=6.0)]
    return {"id": "summit", "title": "Dawn", "environment": "summit", "duration": 20.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -900, "on": "obstacle:S", "z": -10}, {"character": P, "x": -1040, "on": "obstacle:S", "z": 10},
                           {"character": V, "x": -1220, "on": "obstacle:S", "z": 30}],
            "hud": {"messages": [{"text": "CORE RUN", "at": 8.5, "duration": 7.0, "style": "title"}]},
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 20.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ cameras, slow motion, score (from the events)
def event_times(proj, sid):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), sid).simulate(physics_only=True)
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
        ev.setdefault(e.type, []).append(e.t)
    return ev


ENDS = {"city": ("exit_reached@pell", 0, 0.6), "tower": ("exit_reached@pell", 0, 0.6), "canyon": ("exit_reached@pell", 0, 0.6),
        "arena": ("fist_bump@vex", 0, 3.2), "summit": ("act@vex", -1, 6.0)}


def follow(target, vh, **kw):
    return cam("follow", target=target, view_height=vh, **kw)


def shots_for(sc, ev):
    D = sc["duration"]
    f = lambda k, i=0: ev[k][i]  # noqa: E731
    sid = sc["id"]
    if sid == "city":
        S = [shot("a1_title", "establishing", "the neon city in the rain; two figures racing over the roofs; the title",
                  cam("dolly", center=[-1300, Y + 380], center_end=[-1650, Y + 40], view_height=1500, view_height_end=620)),
             shot("a2_throw", "medium", "VEX, waiting with a bar: he hurls it; IKO ducks",
                  cam("static", target="iko", center=[-1180, Y], view_height=560, include=["char:iko", "char:vex"])),
             shot("a3_brawl", "medium", "the rooftop brawl: jab, cross, VEX's roundhouse, IKO slips it",
                  cam("static", target="iko", center=[-1000, Y], view_height=460, include=["char:iko", "char:vex"])),
             shot("a4_leap", "tracking", "VEX flips across the gap; IKO flips after him",
                  follow("iko", 820, lead=0.45, stiffness=3.5, offset=[140, 40])),
             shot("a5_vault", "tracking", "over the vent; VEX turns and hurls an X point blank: IKO staggers through the glass",
                  cam("static", target="iko", center=[300, Y - 40], view_height=620, include=["char:iko", "char:vex"])),
             shot("a6_chase", "wide", "the last gap, a landing roll, out through the gate",
                  follow("iko", 1100, lead=0.5, stiffness=2.5, offset=[120, 120], include=["char:pell"]))]
        t = [0.0, f("throw_start@vex") - 1.0, f("throw@vex") + 0.6, f("takeoff@vex") - 0.6, f("vault_start@iko") - 0.3,
             f("break") + 1.4, D]
        return cut(S, t)
    if sid == "tower":
        S = [shot("b1_storm", "establishing", "out of the white: a tower of steel in a lightning storm",
                  cam("dolly", center=[-1100, Y + 500], center_end=[-1250, Y + 120], view_height=1600, view_height_end=760)),
             shot("b2_climb", "tracking", "up the girders after VEX",
                  follow("iko", 700, lead=0.4, stiffness=3.0, offset=[100, 60])),
             shot("b3_fight", "medium", "the girder fight: blocks, a hook slipped, the roundhouse",
                  cam("static", target="iko", center=[1000, Y + 200], view_height=520, include=["char:iko", "char:vex"])),
             shot("b4_crates", "medium", "VEX crashes through the crates; IKO celebrates too soon; the sweep",
                  cam("static", target="iko", center=[1080, Y + 190], view_height=560, include=["char:iko", "char:vex"])),
             shot("b5_hand", "medium", "VEX laughs and runs; PELL hauls IKO up; after him",
                  follow("pell", 560, stiffness=2.5, offset=[60, 40], include=["char:iko"]))]
        t = [0.0, 2.2, f("strike_start@iko") - 0.8, f("knockdown@vex") - 0.4, f("knockdown@iko") + 0.8, D]
        return cut(S, t)
    if sid == "canyon":
        S = [shot("c1_canyon", "establishing", "out of the white: a canyon at sunset; VEX sprints for the rope bridge",
                  cam("dolly", center=[-900, Y + 400], center_end=[-700, Y + 60], view_height=1500, view_height_end=900)),
             shot("c2_collapse", "wide", "the bridge falls behind VEX; he laughs across the gap",
                  cam("static", target="vex", center=[-240, Y], view_height=900, include=["char:iko", "char:vex"])),
             shot("c3_pad", "tracking", "IKO hits the launch pad and soars over the gap",
                  follow("iko", 900, lead=0.5, stiffness=3.0, offset=[160, 120])),
             shot("c4_throw", "medium", "a roll, the X grabbed and hurled: VEX's drone torn apart",
                  cam("static", target="iko", center=[480, Y + 20], view_height=620, include=["char:iko", "char:vex"])),
             shot("c5_away", "tracking", "PELL lands, cheers; all three race for the gate",
                  follow("pell", 800, lead=0.4, stiffness=2.5, offset=[160, 60]))]
        t = [0.0, f("collapse") - 1.0, f("orb_pad@iko") - 0.8, f("roll_start@iko") - 0.2, f("creature_break") + 1.6, D]
        return cut(S, t)
    if sid == "arena":
        S = [shot("d1_void", "establishing", "out of the white: a floating arena in the void; VEX takes up a staff",
                  cam("dolly", center=[-500, Y + 420], center_end=[-300, Y + 60], view_height=1500, view_height_end=700)),
             shot("d2_duel", "medium", "IKO against the staff: blocked, landed, ducked, dodged",
                  cam("static", target="iko", center=[-130, Y], view_height=480, include=["char:iko", "char:vex"])),
             shot("d3_down", "close", "the staff catches IKO; he goes down hard",
                  cam("static", target="iko", center=[-60, Y - 20], view_height=420, include=["char:iko"])),
             shot("d4_pell", "medium", "PELL finds his nerve: the X, hurled, and VEX goes down",
                  cam("static", target="pell", center=[-330, Y], view_height=800, include=["char:pell", "char:vex"])),
             shot("d5_kick", "tracking", "IKO up, a run-up, the flying kick",
                  follow("iko", 620, lead=0.35, stiffness=4.0, offset=[120, 30])),
             shot("d6_hand", "medium", "IKO offers VEX his hand; a fist bump",
                  cam("static", target="iko", center=[90, Y + 10], view_height=440, include=["char:iko", "char:vex"]))]
        t = [0.0, f("strike_start@iko") - 1.0, f("knockdown@iko") - 0.6, f("pick_up@pell") - 0.5, f("strike_start@iko", -1) - 1.5,
             f("hand_offered@iko") - 0.6, D]
        return cut(S, t)
    if sid == "summit":
        S = [shot("e1_run", "tracking", "out of the white: dawn above the clouds; the three run up onto the summit",
                  follow("iko", 620, stiffness=2.0, offset=[200, 60], include=["char:pell"])),
             shot("e2_bump", "medium", "IKO cheers; a fist bump with PELL; even VEX laughs",
                  cam("static", target="iko", center=[340, Y + 40], view_height=520, include=["char:iko", "char:pell", "char:vex"])),
             shot("e3_vista", "establishing", "the camera pulls away into the sunrise: CORE RUN",
                  cam("dolly", center=[320, Y + 80], center_end=[100, Y + 560], view_height=560, view_height_end=1800), fade_out=2.2)]
        return cut(S, [0.0, f("act@iko", 0) - 0.5, f("fist_bump@iko") + 1.6, D])
    raise KeyError(sid)


SLOWMO = {"city": [{"at": "flip@iko", "before": 0.1, "after": 0.5, "rate": 0.4},
                   {"at": "break@case", "before": 0.25, "after": 0.6, "rate": 0.35}],
          "tower": [{"at": "knockdown@vex", "before": 0.15, "after": 0.7, "rate": 0.35},
                    {"at": "knockdown@iko", "before": 0.15, "after": 0.5, "rate": 0.4}],
          "canyon": [{"at": "orb_pad@iko", "before": 0.05, "after": 0.9, "rate": 0.45},
                     {"at": "creature_break@drone", "before": 0.3, "after": 0.7, "rate": 0.35}],
          "arena": [{"at": "knockdown@iko", "before": 0.15, "after": 0.5, "rate": 0.35},
                    {"at": "hit@pell", "before": 0.2, "after": 0.5, "rate": 0.4},
                    {"at": "hit@iko[move=flying_kick]", "before": 0.35, "after": 0.7, "rate": 0.3}],
          "summit": []}
SCORE = {"city": [cue("tension", at=0.0), cue("action", on="throw_start@vex", delay=-0.3)],
         "tower": [cue("action", at=0.0), cue("triumph", on="knockdown@vex", delay=0.3), cue("sad", on="knockdown@iko"),
                   cue("action", on="hand_offered@pell")],
         "canyon": [cue("action", at=0.0), cue("tension", on="collapse"), cue("action", on="orb_pad@iko", delay=-0.4),
                    cue("triumph", on="creature_break"), cue("action", on="creature_break", delay=2.5)],
         "arena": [cue("tension", at=0.0), cue("action", on="strike_start@iko", delay=-0.6), cue("sad", on="knockdown@iko"),
                   cue("hope", on="pick_up@pell"), cue("action", on="hit@pell"), cue("triumph", on="hand_offered@iko")],
         "summit": [cue("triumph", at=0.0)]}


def finalize(proj):
    for sc in proj["scenes"]:
        key, k, pad = ENDS[sc["id"]]
        ev = event_times(proj, sc["id"])
        sc["duration"] = round(ev[key][k] + pad, 2)
        sc["shots"] = shots_for(sc, ev)
        sc["time_fx"] = {"hit_stop": True, "slowmo": SLOWMO[sc["id"]], "smears": True, "punch_in": True}
        sc["score"] = {"key": "E", "level": 0.6, "cues": SCORE[sc["id"]]}
    return proj


def project(scenes=None):
    return {"schema_version": "0.1", "id": "core_run", "title": "CORE RUN", "fps": 24, "width": 1920, "height": 1080, "seed": 77,
            "characters": CHARACTERS, "environments": [city(), tower(), canyon(), arena(), summit()],
            "scenes": scenes or [scene_city(), scene_tower(), scene_canyon(), scene_arena(), scene_summit()]}


if __name__ == "__main__":
    proj = finalize(project())
    json.dump(proj, open(sys.argv[1], "w"), indent=1)
    for sc in proj["scenes"]:
        print(f"{sc['id']:8s} {sc['duration']:6.2f}s  " + ", ".join(f"{sh['id']} {sh['start']:.2f}-{sh['end']:.2f}" for sh in sc["shots"]))
