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


def core(x, y, **kw):
    """The energy core that keeps the world lit (an energy glyph; set dressing until someone takes it)."""
    return glyph("core", "0", x, y, size=34.0, mass=2.0, color="#7dfcff", energy=True, **kw)


def holder(id_, x, top, h=56.0):
    return dict(id=id_, kind="beam", center=[x, top + h / 2], size=[56.0, h], style="pedestal")


# ------------------------------------------------------------------ 1. the theft and the rooftop pursuit (night, rain)
CASE_X = -1300.0


def city(power=()):
    obs = [plat("R1", -2000, -700, style="roof"), plat("R2", -480, 640, top=TOP - 50, style="roof"),
           plat("R3", 860, 2000, style="roof"),
           holder("plinth", CASE_X, TOP),
           dict(id="vent", kind="beam", center=[120.0, TOP - 50 + 30], size=[70.0, 60.0])]
    top = TOP + 56
    props = [core(CASE_X, top + 18, solid=False),
             dict(id="case", kind="canister", position=[CASE_X, top + 32], size=[52.0, 64.0], mass=2.0, z=0.0, depth=40.0,
                  friction=0.5, breakable={"impulse": 260.0, "scatter": 160.0}, color="#bff8ff", material="glass"),
             dict(id="crate", kind="crate", position=[-860.0, TOP + 25], size=[50.0, 50.0], mass=3.0, z=0.0, depth=40.0,
                  breakable={"impulse": 3200.0, "grid": 2}, color="#8a6a3a")]
    return world("city", "city", obs, props, weather="rain", amount=1.3, exits=[gate()], power=list(power))


def scene_city():
    I, P, V = "iko", "pell", "vex"
    acts = [
        # VEX: the theft, a look back at them with the core, away over the roofs; a crate kicked into their path
        A(V, "walk_to", target_x=CASE_X + 70), A(V, "strike", target="prop:case", move="cross", power=1.2),
        A(V, "pick_up", target="prop:core"), A(V, "turn", face=-1), A(V, "look_at", target="char:iko", duration=0.7),
        act(V, "laugh", 0.8, "joyful"), A(V, "turn", face=1), A(V, "run_to", target_x=-775, speed=330, lane=46),
        A(V, "walk_to", target_x=-790, lane=0), A(V, "turn", face=-1),
        A(V, "strike", target="prop:crate", move="front_kick", power=1.3),
        A(V, "turn", face=1), A(V, "run_to", target_x=-760, speed=360),
        A(V, "jump_to", target_x=-260, height=140, flip="front", onto="obstacle:R2"),
        A(V, "run_to", target_x=40), A(V, "vault", target="obstacle:vent"), A(V, "run_to", target_x=580),
        A(V, "jump_to", target_x=1000, height=150, onto="obstacle:R3"), A(V, "run_to", target_x=1180),
        A(V, "turn", face=-1), A(V, "wait_for", until="next:strike_start@iko"), A(V, "dodge", dodge="back"),
        A(V, "strike", target="char:iko", move="front_kick", power=1.0, reaction="stagger", distance=56),
        act(V, "laugh", 0.8, "joyful"), A(V, "turn", face=1),
        A(V, "run_to", target_x=1700, speed=360), A(V, "reach_exit", target="exit:gate", speed=340),
        # IKO: sees it, goes straight after him; the vent, the gap, the flip over the tank, the flying kick that fails
        A(I, "wait_for", until="event:break@case"), act(I, "shock", 0.7, "scared"),
        A(I, "wait_for", until="event:act@vex[clip=laugh]"), act(I, "rise", 0.5, "determined", tempo=1.6),
        A(I, "run_to", target_x=CASE_X - 140, speed=380, lane=-20), A(I, "vault", target="obstacle:plinth"),
        A(I, "run_to", target_x=-1060, speed=380),
        A(I, "wait_for", until="event:strike_prop@vex[move=front_kick]"), A(I, "dodge", dodge="duck"),
        A(I, "run_to", target_x=-760, speed=400), A(I, "jump_to", target_x=-380, height=130, onto="obstacle:R2"),
        A(I, "run_to", target_x=30), A(I, "vault", target="obstacle:vent"),
        A(I, "run_to", target_x=600), A(I, "jump_to", target_x=1000, height=150, flip="front", onto="obstacle:R3"),
        A(I, "strike", target="char:vex", move="flying_kick", power=1.3, distance=175),  # too far: reckless
        A(I, "wait_for", until="event:hurt@iko"), act(I, "lose_balance", 0.9, "scared"),
        A(I, "wait_for", until="event:hand_offered@pell"), act(I, "wave_on", 0.9, "determined"), A(I, "turn", face=1),
        A(I, "run_to", target_x=1700, speed=380), A(I, "reach_exit", target="exit:gate", speed=320),
        # PELL: startled, behind, the safe way round; reaches IKO at the edge and is waved on
        A(P, "wait_for", until="event:break@case"), act(P, "shock", 1.1, "scared"),
        A(P, "wait_for", until="event:act@iko[clip=rise]"),  # behind IKO
        A(P, "run_to", target_x=CASE_X - 150, speed=280, lane=24), A(P, "wait_for", until="event:vault@iko"),
        A(P, "vault", target="obstacle:plinth"),
        A(P, "run_to", target_x=-1120, speed=330),
        A(P, "wait_for", until="event:strike_prop@vex[move=front_kick]"), A(P, "roll", distance=150),
        A(P, "run_to", target_x=-760, speed=340), A(P, "jump_to", target_x=-360, height=110, onto="obstacle:R2"),
        A(P, "run_to", target_x=-40, lane=30), A(P, "jump_to", target_x=260, height=140, onto="obstacle:R2"),
        A(P, "run_to", target_x=580), A(P, "wait_for", until="event:act@iko[clip=lose_balance]"),
        A(P, "jump_to", target_x=920, height=130, onto="obstacle:R3"),
        A(P, "offer_hand", target="char:iko"), A(P, "wait_for", until="event:act@iko[clip=wave_on]"),
        A(P, "run_to", target_x=1650, speed=330), A(P, "reach_exit", target="exit:gate", speed=280)]
    return {"id": "city", "title": "The theft", "environment": "city", "duration": 40.0, "transition_in": "fade",
            "placements": [{"character": I, "x": -1820, "on": "obstacle:R1", "z": -10, "facing": -1},
                           {"character": P, "x": -1930, "on": "obstacle:R1", "z": 10, "facing": -1},
                           {"character": V, "x": -1000, "on": "obstacle:R1", "facing": -1, "z": 0}],
            "hud": {"messages": [{"text": "CORE RUN", "at": 4.9, "duration": 2.8, "style": "title"}]},
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 2. the storm tower: the climb, the girder fight, the fall, the hand
UP = TOP + 190


def tower():
    obs = [plat("G1", -2000, -480, style="girder"), plat("G2", -460, 360, top=UP, style="girder"),
           plat("G3", 600, 2000, top=UP, style="girder")]
    return world("tower", "tower", obs, [core(-1100, UP + 400)], weather="rain", amount=1.6, lightning=True, exits=[gate(s=UP + 130)])


def scene_tower():
    I, P, V = "iko", "pell", "vex"
    acts = [
        # VEX: leaps the girders with the core, lets IKO come, gives ground, then turns his rush into a sweep
        A(V, "run_to", target_x=-640, speed=360), A(V, "jump_to", target_x=-300, height=290, flip="back", onto="obstacle:G2"),
        A(V, "run_to", target_x=260, speed=360), A(V, "jump_to", target_x=760, height=150, onto="obstacle:G3"),
        A(V, "run_to", target_x=930, speed=300),
        A(V, "turn", face=-1), A(V, "guard", until="event:act@iko[clip=cheer]"),  # takes the combo on the guard, giving ground
        A(V, "wait_for", until="next:strike_start@iko"), A(V, "dodge", dodge="back"),
        A(V, "strike", target="char:iko", move="sweep", power=1.2, reaction="knockdown", distance=62),
        act(V, "peer_down", 1.2, "joyful"), act(V, "laugh", 0.9, "joyful"), A(V, "turn", face=1),
        A(V, "run_to", target_x=1700, speed=360), A(V, "reach_exit", target="exit:gate", speed=340),
        # IKO: up the girders, catches him, drives him back - and is swept off the girder
        A(I, "run_to", target_x=-560, speed=400, lane=-20), A(I, "climb", target="obstacle:G2"),
        A(I, "run_to", target_x=300, speed=400), A(I, "jump_to", target_x=720, height=150, flip="front", onto="obstacle:G3"),
        A(I, "strike", target="char:vex", move="jab"), A(I, "strike", target="char:vex", move="cross"),
        A(I, "strike", target="char:vex", move="side_kick", power=1.1), act(I, "cheer", 0.6, "joyful"),
        A(I, "strike", target="char:vex", move="roundhouse", power=1.2),
        A(I, "wait_for", until="event:knockdown@iko"), A(I, "wait_for", until="event:settled@iko"),
        A(I, "get_up", hesitate=True),  # he tries alone and cannot
        A(I, "wait_for", until="event:hand_offered@pell"), A(I, "get_up", target="char:pell"),
        A(I, "look_at", target="exit:gate", duration=0.8),
        A(I, "wait_for", until="event:point@pell"), act(I, "rise", 0.5, "determined", tempo=1.6),
        A(I, "run_to", target_x=1700, speed=380), A(I, "reach_exit", target="exit:gate", speed=320),
        # PELL: the long way round, down to the catwalk; the hand, then the way back up
        A(P, "run_to", target_x=-570, speed=340, lane=26), A(P, "climb", target="obstacle:G2"),
        A(P, "run_to", target_x=300, speed=340), A(P, "wait_for", until="event:knockdown@iko"), act(P, "shock", 0.6, "scared"),
        A(P, "jump_to", target_x=630, height=120, onto="obstacle:G3"),
        A(P, "wait_for", until="event:get_up_failed@iko"), A(P, "offer_hand", target="char:iko"),
        A(P, "point", target="exit:gate", duration=0.9),
        A(P, "run_to", target_x=1650, speed=340), A(P, "reach_exit", target="exit:gate", speed=300)]
    return {"id": "tower", "title": "The tower", "environment": "tower", "duration": 40.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1500, "on": "obstacle:G1", "z": -10}, {"character": P, "x": -1680, "on": "obstacle:G1", "z": 10},
                           {"character": V, "x": -1100, "on": "obstacle:G1", "carrying": "prop:core"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 3. the canyon (sunset): the bridge, two crossings, the drone, the portal
GAP = (-480.0, -40.0)
LOG_X = 420.0


def canyon():
    obs = [plat("A", -2000, GAP[0], style="rock"), plat("C", GAP[1], 2000, style="rock"),
           plat("bridge", GAP[0], GAP[1], thick=18.0, style="bridge", color="#9a6a44",
                collapse={"on": "event:strike_prop@vex", "pieces": 6, "color": "#9a6a44"}),
           ]
    drone = {"id": "drone", "body": "0", "size": [80.0, 54.0], "position": [1350.0, TOP + 100], "mass": 5.0, "color": "#ff4a5a",
             "z": 0.0, "breaks": 1500.0, "stride": 60.0,
             "parts": [{"glyph": "!", "size": [16.0, 60.0], "at": [-22.0, -16.0], "role": "leg", "phase": 0.0},
                       {"glyph": "!", "size": [16.0, 60.0], "at": [22.0, -16.0], "role": "leg", "phase": 3.14159},
                       {"glyph": "0", "size": [14.0, 14.0], "at": [-26.0, 8.0], "role": "eye", "mass": 0.2, "color": "#ffffff"}],
             "path": [[12.0, 1350.0], [15.0, 980.0]]}
    props = [core(-1100, TOP + 400),
             glyph("anchor", "!", -20.0, TOP + 35, size=70.0, mass=2.5, color="#c08a5a"),  # the bridge's stake
             dict(id="log", kind="crate", position=[LOG_X - 137.6, TOP + 144.3], size=[76.0, 34.0], mass=3.0, z=0.0, depth=60.0,
                  color="#5a4a3a", collide_characters=False),  # held out to one side at the start: it swings across the path
             glyph("x", "x", 760.0, TOP + 20, size=40.0, mass=5.0, color="#ffd84a")]
    w = world("canyon", "canyon", obs, props, weather="embers", amount=0.9, exits=[gate()])
    w["ropes"] = [{"id": "chain", "a": "prop:log", "a_local": [0.0, 17.0], "b": f"world:{LOG_X},{TOP + 420}", "length": 293.0,
                   "color": "#8a8a8a"}]
    w["orbs"] = [{"id": "orb", "kind": "jump", "center": [-230.0, TOP + 290], "radius": 34.0, "power": 520.0, "flip": "front", "once": True}]
    w["creatures"] = [drone]
    return w


def scene_canyon():
    I, P, V = "iko", "pell", "vex"
    acts = [
        # VEX: over the bridge, kicks out its stake; sets the hanging beam swinging across the path; through the portal
        A(V, "run_to", target_x=90, speed=360), A(V, "turn", face=-1),
        A(V, "strike", target="prop:anchor", move="front_kick", power=1.0), act(V, "laugh", 0.8, "joyful"), A(V, "turn", face=1),
        A(V, "run_to", target_x=LOG_X - 260, speed=380), A(V, "duck_slide", target_x=LOG_X + 290),
        A(V, "run_to", target_x=1100, speed=380, lane=40), A(V, "jump_to", target_x=1600, height=200, flip="back", onto="obstacle:C"),
        A(V, "run_to", target_x=1750, speed=380), A(V, "reach_exit", target="exit:gate", speed=340),
        # IKO: the bridge falls in front of him; the launch pad, over the gap and the swinging beam; the drone
        A(I, "run_to", target_x=-860, speed=400, lane=-20), A(I, "wait_for", until="event:collapse@bridge"), act(I, "shock", 0.6, "scared"),
        act(I, "rise", 0.5, "determined", tempo=1.6), A(I, "run_to", target_x=-540, speed=420),
        A(I, "jump_to", target_x=120, height=170, onto="obstacle:C"),  # the jump orb over the gap
        A(I, "run_to", target_x=LOG_X - 330, speed=400), A(I, "roll", distance=600), A(I, "run_to", target_x=820, speed=420),
        A(I, "strike", target="prop:drone.body", move="front_kick", power=0.35),  # it shrugs off the kick
        A(I, "dodge", dodge="back"), A(I, "guard", until="event:throw@pell"),
        A(I, "wait_for", until="event:creature_break@drone"), A(I, "roll", distance=200),
        A(I, "run_to", target_x=1700, speed=400), A(I, "reach_exit", target="exit:gate", speed=320),
        # PELL: the swing bar over the gap, a slide under the beam; the X that tears the drone apart
        A(P, "run_to", target_x=-980, speed=340, lane=20), A(P, "wait_for", until="event:orb_jump@iko"),
        A(P, "run_to", target_x=-570, speed=420), A(P, "jump", height=200),  # too short: he catches the far edge
        A(P, "catch_ledge", target="obstacle:C"), A(P, "hang", duration=1.4),
        A(P, "run_to", target_x=LOG_X - 260, speed=360), A(P, "duck_slide", target_x=LOG_X + 290), A(P, "run_to", target_x=700, speed=340),
        A(P, "pick_up", target="prop:x"), A(P, "run_to", target_x=900, speed=300, lane=30),
        A(P, "throw", target="prop:drone.body", power=1.9),
        act(P, "cheer", 0.9, "joyful"),
        A(P, "run_to", target_x=1650, speed=360), A(P, "reach_exit", target="exit:gate", speed=300)]
    return {"id": "canyon", "title": "The canyon", "environment": "canyon", "duration": 40.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1750, "on": "obstacle:A", "z": -10}, {"character": P, "x": -1880, "on": "obstacle:A", "z": 10},
                           {"character": V, "x": -620, "on": "obstacle:A", "carrying": "prop:core"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 40.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 4. the arena (the void): the final confrontation
HOLD_X = 760.0
STALK = [-60.0]  # where VEX stops over the fallen IKO: set from the simulation (finalize)


def arena(power=()):
    obs = [plat("floor", -1800, 1800, thick=60.0), holder("socket", HOLD_X, TOP)]
    props = [core(-900, TOP + 400),
             glyph("staff", "-", -40.0, TOP + 8, size=118.0, mass=5.0, color="#ff4a5a"),
             dict(glyph("x", "x", -260.0, TOP + 25, size=50.0, mass=5.0, color="#ffd84a"), z=30.0)]
    return world("arena", "void", obs, props, width=3600, weather="data", amount=1.0, exits=[gate()], power=list(power))


def scene_arena():
    I, P, V = "iko", "pell", "vex"
    acts = [
        # VEX: sets the core in the socket, takes up the staff and takes IKO apart - until PELL's throw takes the staff
        A(V, "run_to", target_x=HOLD_X - 150, speed=340), A(V, "place", target="obstacle:socket"),
        A(V, "pick_up", target="prop:staff"), A(V, "turn", face=-1),
        A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.45),  # IKO's jab: blocked
        A(V, "strike", target="char:iko", move="swing_weapon", power=0.9, reaction="stagger"),  # IKO steps out of it
        A(V, "wait_for", until="next:hurt@vex"),  # IKO's side kick lands
        A(V, "turn", face=-1), A(V, "guard", until="next:strike_start@iko"), A(V, "guard", duration=0.35),
        A(V, "strike", target="char:iko", move="swing_weapon", power=1.5, reaction="knockdown"),
        act(V, "laugh", 0.8, "joyful"), A(V, "walk_to", target_x=STALK[0], speed=80),  # stalks the fallen IKO
        A(V, "wait_for", until="event:disarm@vex"), act(V, "shock", 0.8, "scared"),
        A(V, "wait_for", until="event:stood_up@iko"), A(V, "look_at", target="char:iko", duration=0.9),
        A(V, "strike", target="char:iko", move="hook", power=1.0),  # bare-handed now: IKO ducks it
        A(V, "wait_for", until="next:knockdown@vex"), A(V, "wait_for", until="next:settled@vex"),
        A(V, "get_up", hesitate=True),  # beaten: he cannot rise
        A(V, "wait_for", until="event:exit_reached@pell"),
        # IKO: in fast, held off by the staff, down; up again, and the flying kick; takes back the core
        A(I, "run_to", target_x=-420, speed=420, lane=-10), A(I, "wait_for", until="event:pick_up@vex"),
        act(I, "rise", 0.5, "determined", tempo=1.6),
        A(I, "strike", target="char:vex", move="jab"),
        A(I, "wait_for", until="next:strike_start@vex"), A(I, "dodge", dodge="back"),
        A(I, "strike", target="char:vex", move="side_kick", power=0.9, reaction="stagger"),
        A(I, "wait_for", until="next:knockdown@iko", duration=0.5), A(I, "strike", target="char:vex", move="cross", power=1.0),
        A(I, "wait_for", until="event:knockdown@iko"), A(I, "wait_for", until="event:settled@iko"),
        A(I, "get_up", hesitate=True),
        A(I, "wait_for", until="event:disarm@vex"), A(I, "get_up"),
        A(I, "look_at", target="char:pell", duration=0.6), A(I, "turn", face=1),
        A(I, "wait_for", until="next:strike_start@vex"), A(I, "dodge", dodge="duck"),
        A(I, "strike", target="char:vex", move="flying_kick", power=1.1, reaction="knockdown", distance=100),
        act(I, "recover_relief_shake", 0.9, "tired"), A(I, "run_to", target_x=HOLD_X - 170, speed=360),
        A(I, "pick_up", target="prop:core"), A(I, "turn", face=-1), act(I, "cheer", 1.0, "joyful"),
        A(I, "turn", face=1), A(I, "vault", target="obstacle:socket"),
        A(I, "run_to", target_x=1650, speed=340), A(I, "reach_exit", target="exit:gate", speed=300),
        # PELL: tries to help and is kicked back; finds the X; the throw that disarms VEX; draws his last attack
        A(P, "run_to", target_x=-340, speed=330, lane=30), A(P, "wait_for", until="event:hurt@vex"),
        A(P, "run_to", target_x=-120, speed=380),  # rushing in to help - too late
        A(P, "wait_for", until="event:knockdown@iko"), act(P, "shock", 0.6, "scared"),
        A(P, "pick_up", target="prop:x"), A(P, "wait_for", until="event:get_up_failed@iko"),
        A(P, "throw", target="prop:staff", power=1.4),
        A(P, "wait_for", until="event:stood_up@iko"), A(P, "guard", until="event:knockdown@vex"),
        act(P, "cheer", 1.2, "joyful"), A(P, "wait_for", until="event:pick_up@iko[prop=core]"),
        A(P, "run_to", target_x=HOLD_X - 130, speed=330), A(P, "vault", target="obstacle:socket"),
        A(P, "run_to", target_x=1600, speed=330), A(P, "reach_exit", target="exit:gate", speed=280)]
    return {"id": "arena", "title": "The arena", "environment": "arena", "duration": 50.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -1500, "on": "obstacle:floor", "z": -10},
                           {"character": P, "x": -1640, "on": "obstacle:floor", "z": 10},
                           {"character": V, "x": -900, "on": "obstacle:floor", "carrying": "prop:core"}],
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 50.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ 5. the summit (dawn): the return of the light
REST_X = 420.0


def summit(power=()):
    obs = [plat("S", -1800, 900, style="rock"), holder("beacon", REST_X, TOP, h=64.0)]
    return world("summit", "summit", obs, [core(-1100, TOP + 400)], weather="motes", width=3600, city_lights=True, power0=0.05,
                 power=list(power))


def scene_summit():
    I, P = "iko", "pell"
    acts = [A(I, "run_to", target_x=REST_X - 160, speed=300, lane=-20), A(I, "place", target="obstacle:beacon"),
            A(I, "turn", face=1), A(I, "look_at", target=f"point:{REST_X + 2000},{TOP - 400}", duration=1.6),
            A(I, "turn", face=-1), A(I, "wait_for", until="event:act@pell[clip=cheer]"),
            A(I, "gesture", target="char:pell", gesture="fist_bump"), act(I, "laugh", 1.6, "joyful"),
            A(I, "turn", face=1), A(I, "idle", duration=6.0),
            A(P, "run_to", target_x=REST_X - 330, speed=290, lane=20), A(P, "wait_for", until="event:place@iko"),
            act(P, "shock", 0.6, "scared"), A(P, "turn", face=1), A(P, "look_at", target=f"point:{REST_X + 2000},{TOP - 400}", duration=1.2),
            act(P, "cheer", 1.2, "joyful"), A(P, "wait_for", until="event:gesture_start@iko"),
            A(P, "gesture", target="char:iko", gesture="fist_bump"), act(P, "laugh", 1.6, "joyful"),
            A(P, "turn", face=1), A(P, "idle", duration=6.0)]
    return {"id": "summit", "title": "Dawn", "environment": "summit", "duration": 30.0, "transition_in": "warp",
            "placements": [{"character": I, "x": -900, "on": "obstacle:S", "z": -10, "carrying": "prop:core"},
                           {"character": P, "x": -1040, "on": "obstacle:S", "z": 10}],
            "hud": {"messages": [{"text": "CORE RUN", "at": 20.0, "duration": 6.0, "style": "title"}]},
            "actions": acts, "shots": [{"id": "wide", "start": 0, "end": 30.0, "camera": {"mode": "follow", "target": "iko", "view_height": 900}}]}


# ------------------------------------------------------------------ cameras, slow motion, score, the lights (from the events)
def event_times(proj, sid):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), sid).simulate(physics_only=True)
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
        ev.setdefault(e.type, []).append(e.t)
        if e.data.get("prop"):
            ev.setdefault(f"{e.type}@{e.character}:{e.data['prop']}", []).append(e.t)
    return ev


ENDS = {"city": ("exit_reached@iko", 0, 0.8), "tower": ("exit_reached@pell", 0, 0.5), "canyon": ("exit_reached@pell", 0, 0.5),
        "arena": ("exit_reached@iko", 0, 0.4), "summit": ("fist_bump@iko", 0, 10.0)}


def follow(target, vh, **kw):
    return cam("follow", target=target, view_height=vh, **kw)


def still(center, vh, *inc, **kw):
    return cam("static", center=list(center), view_height=vh, include=[f"char:{c}" for c in inc], **kw)


def shots_for(sc, ev):
    D = sc["duration"]
    f = lambda k, i=0: ev[k][i]  # noqa: E731
    sid = sc["id"]
    if sid == "city":
        S = [shot("a1_core", "close", "the core glowing in its glass case above the city; VEX's fist through the glass",
                  still((CASE_X, TOP + 110), 360, "vex")),
             shot("a2_dark", "establishing", "VEX lifts the core out: the city's lights die in a wave; a warning beacon pulses",
                  still((CASE_X + 300, Y + 300), 1500, "vex", "iko", "pell")),
             shot("a3_look", "medium", "IKO and PELL turn; VEX shows them the core and laughs",
                  still((-1560, Y), 640, "iko", "pell", "vex")),
             shot("a4_crate", "medium", "the chase: over the plinth; VEX kicks a crate back at them, IKO ducks, PELL rolls",
                  still((-1050, Y + 20), 760, "iko", "pell", "vex")),
             shot("a5_roofs", "tracking", "over the gap, the vent vaulted, flat out across the roofs",
                  follow("iko", 820, lead=0.45, stiffness=3.5, offset=[140, 40])),
             shot("a6_edge", "medium", "the flying kick launched too far; VEX steps out of it and kicks IKO to the edge; PELL waved on",
                  still((1080, Y), 600, "iko", "vex", "pell")),
             shot("a7_go", "wide", "the chase goes on, through the gate to the storm tower",
                  follow("iko", 1100, lead=0.5, stiffness=2.5, offset=[120, 120]))]
        t = [0.0, f("break") + 0.9, f("pick_up@vex") + 1.3, f("act@vex", 0) + 1.3, f("takeoff@iko", 0) - 0.2,
             f("flip@iko") - 0.5, f("act@iko", -1) + 0.9, D]
        return cut(S, t)
    if sid == "tower":
        S = [shot("b1_tower", "establishing", "out of the white: low on the storm tower, VEX leaping up the girders with the core",
                  cam("dolly", center=[-1250, Y + 650], center_end=[-1100, Y + 160], view_height=1700, view_height_end=900)),
             shot("b2_climb", "tracking", "IKO climbs after him, flips across the gap",
                  follow("iko", 700, lead=0.4, stiffness=3.0, offset=[100, 60])),
             shot("b3_fight", "medium", "the girder fight: IKO drives, VEX gives ground on his guard",
                  still((760, UP + 110), 500, "iko", "vex")),
             shot("b4_sweep", "medium", "IKO cheers too soon; the roundhouse dodged; the sweep",
                  still((740, UP + 100), 440, "iko", "vex")),
             shot("b5_down", "medium", "IKO cannot get up; VEX looks down at him, laughs, and goes",
                  follow("iko", 480, stiffness=2.0, offset=[60, 40])),
             shot("b6_hand", "medium", "PELL reaches him; his hand; IKO takes it; PELL points the way",
                  follow("iko", 520, stiffness=2.0, offset=[-40, 40], include=["char:pell"])),
             shot("b7_go", "tracking", "after VEX together",
                  follow("iko", 800, lead=0.4, stiffness=2.5, offset=[120, 60], include=["char:pell"]))]
        t = [0.0, 3.0, f("flip@iko") + 0.6, f("act@iko") - 0.3, f("knockdown@iko") + 1.0, f("hand_offered@pell") - 2.0,
             f("point@pell") + 1.0, D]
        return cut(S, t)
    if sid == "canyon":
        S = [shot("c1_canyon", "establishing", "out of the white: the canyon at sunset; VEX over the rope bridge",
                  cam("dolly", center=[-800, Y + 600], center_end=[-300, Y + 150], view_height=1800, view_height_end=1000)),
             shot("c2_stake", "wide", "he kicks out the stake: the bridge falls into the canyon in front of IKO",
                  still((-260, Y), 1000, "vex", "iko")),
             shot("c3_orb", "tracking", "IKO leaps for the orb: it flips him across the gap",
                  follow("iko", 900, lead=0.5, stiffness=3.0, offset=[160, 120])),
             shot("c4_ledge", "tracking", "PELL jumps short, catches the edge, hauls himself up and slides under the swinging beam",
                  follow("pell", 720, lead=0.4, stiffness=3.0, offset=[120, 60])),
             shot("c5_drone", "medium", "the drone shrugs off IKO's kick; PELL's X tears it apart; IKO rolls through",
                  still((960, Y + 20), 700, "iko", "pell")),
             shot("c6_portal", "tracking", "into the portal after VEX",
                  follow("iko", 1000, lead=0.4, stiffness=2.5, offset=[160, 60]))]
        t = [0.0, f("collapse") - 1.2, f("takeoff@iko", 0) - 0.3, f("orb_jump@iko") + 1.4, f("strike_prop@iko") - 1.0,
             f("creature_break") + 2.0, D]
        return cut(S, t)
    if sid == "arena":
        S = [shot("d1_void", "establishing", "out of the white: a floating arena; VEX carries the core to the socket",
                  cam("dolly", center=[-300, Y + 600], center_end=[300, Y + 120], view_height=1800, view_height_end=1100)),
             shot("d2_socket", "close", "the core set in the socket: energy floods the arena",
                  still((HOLD_X, TOP + 110), 400)),
             shot("d2b_standoff", "wide", "VEX walks back to the staff; IKO and PELL face him; the core glows behind him",
                  still((160, Y + 120), 1100, "iko", "pell", "vex")),
             shot("d3_duel", "medium", "VEX takes up the staff: IKO's jab blocked, the swing slipped, the side kick lands",
                  follow("iko", 560, stiffness=2.5, offset=[90, 20], include=["char:vex"])),
             shot("d4_down", "medium", "PELL rushes in, too late: the staff knocks IKO down; he cannot get up; VEX stalks him",
                  follow("iko", 600, stiffness=2.0, offset=[60, 20], include=["char:vex"])),
             shot("d5_throw", "medium", "PELL's throw takes the staff out of VEX's hands",
                  follow("vex", 820, stiffness=2.0, offset=[-160, 40], include=["char:pell"])),
             shot("d6_kick", "medium", "IKO up; a look at PELL; he ducks VEX's hook and the flying kick lands",
                  follow("iko", 560, stiffness=3.0, offset=[80, 20], include=["char:vex"])),
             shot("d7_core", "medium", "VEX cannot rise; IKO takes the core back out of the socket",
                  still((HOLD_X - 120, Y), 520, "iko")),
             shot("d8_go", "tracking", "out together, the core in IKO's hands",
                  follow("iko", 1000, lead=0.4, stiffness=2.5, offset=[160, 60]))]
        t = [0.0, f("place@vex") - 0.8, f("place@vex") + 1.6, f("pick_up@vex") - 0.2, f("hit@vex") - 2.2, f("throw_start@pell") - 0.4,
             f("disarm@vex") + 1.2, f("get_up_failed@vex") - 0.8, f("pick_up@iko") + 1.6, D]
        return cut(S, t)
    if sid == "summit":
        S = [shot("e1_run", "tracking", "out of the white: dawn; IKO and PELL run up with the core, worn out",
                  follow("iko", 640, stiffness=2.0, offset=[200, 60], include=["char:pell"])),
             shot("e2_place", "close", "IKO sets the core in the beacon",
                  still((REST_X, TOP + 100), 400, "iko")),
             shot("e3_light", "establishing", "a pulse of light: far below, the city lights up again",
                  still((REST_X + 600, Y + 160), 1500, "iko", "pell")),
             shot("e4_bump", "medium", "IKO looks at PELL; a fist bump, earned",
                  still((140, Y + 40), 480, "iko", "pell")),
             shot("e5_vista", "establishing", "the camera pulls back over the restored world: CORE RUN",
                  cam("dolly", center=[180, Y + 60], center_end=[600, Y + 520], view_height=560, view_height_end=2000), fade_out=2.2)]
        return cut(S, [0.0, f("place@iko") - 0.7, f("place@iko") + 0.8, f("gesture_start@iko") - 1.0, f("fist_bump@iko") + 2.2, D])
    raise KeyError(sid)


SLOWMO = {"city": [{"at": "break@case", "before": 0.2, "after": 0.6, "rate": 0.35},
                   {"at": "whiff@iko", "before": 0.35, "after": 0.4, "rate": 0.4}],
          "tower": [{"at": "knockdown@iko", "before": 0.15, "after": 0.6, "rate": 0.35}],
          "canyon": [{"at": "orb_jump@iko", "before": 0.1, "after": 0.9, "rate": 0.4},
                     {"at": "creature_break@drone", "before": 0.2, "after": 0.6, "rate": 0.4}],
          "arena": [{"at": "knockdown@iko", "before": 0.15, "after": 0.5, "rate": 0.35},
                    {"at": "disarm@vex", "before": 0.25, "after": 0.6, "rate": 0.35},
                    {"at": "hit@iko[move=flying_kick]", "before": 0.35, "after": 0.7, "rate": 0.3}],
          "summit": [{"at": "place@iko", "before": 0.1, "after": 0.6, "rate": 0.5}]}
SCORE = {"city": [cue("tension", at=0.0), cue("action", on="break@case", delay=0.4)],
         "tower": [cue("action", at=0.0), cue("tension", on="act@iko[clip=cheer]"), cue("sad", on="knockdown@iko"),
                   cue("hope", on="hand_grab@iko"), cue("action", on="point@pell")],
         "canyon": [cue("action", at=0.0), cue("tension", on="collapse"), cue("action", on="orb_jump@iko", delay=-0.4),
                    cue("triumph", on="creature_break"), cue("action", on="creature_break", delay=2.5)],
         "arena": [cue("tension", at=0.0), cue("action", on="strike_start@iko", delay=-0.4), cue("sad", on="knockdown@iko"),
                   cue("hope", on="throw_start@pell"), cue("action", on="disarm@vex"), cue("triumph", on="knockdown@vex")],
         "summit": [cue("hope", at=0.0), cue("triumph", on="place@iko")]}


def power_cues(sid, ev):
    """The lights, from the events: the city goes dark as VEX lifts the core; the socket floods the arena; the beacon
    relights the world."""
    if sid == "city":
        return [{"at": round(ev["pick_up@vex"][0], 2), "level": 0.06, "fade": 1.8, "origin": [CASE_X, TOP + 90], "speed": 1400.0}]
    if sid == "arena":
        return [{"at": round(ev["place@vex"][0], 2), "level": 1.0, "fade": 0.8, "origin": [HOLD_X, TOP + 90], "speed": 3000.0},
                {"at": round(ev["pick_up@iko"][0], 2), "level": 0.2, "fade": 0.8, "origin": [HOLD_X, TOP + 90], "speed": 3000.0}]
    if sid == "summit":
        return [{"at": round(ev["place@iko"][0], 2), "level": 1.0, "fade": 1.4, "origin": [REST_X, TOP + 90], "speed": 2200.0}]
    return []


def place_stalk(proj):
    """VEX walks up to the fallen IKO and stops a staff's length short of him (where IKO lies is up to the physics)."""
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), "arena").simulate(physics_only=True)
    ix = next(e.data["point"][0] for e in r.events if e.type == "settled" and e.character == "iko")
    vx = next(e.data["point"][0] for e in r.events if e.type == "hit" and e.character == "vex" and e.data.get("move") == "swing_weapon"
              and e.data.get("reaction") == "knockdown")
    STALK[0] = round(ix + (150.0 if vx > ix else -150.0), 1)
    return project()


def finalize(proj):
    proj = place_stalk(proj)
    envs = {e["id"]: e for e in proj["environments"]}
    for sc in proj["scenes"]:
        key, k, pad = ENDS[sc["id"]]
        ev = event_times(proj, sc["id"])
        sc["duration"] = round(ev[key][k] + pad, 2)
        sc["shots"] = shots_for(sc, ev)
        sc["time_fx"] = {"hit_stop": True, "slowmo": SLOWMO[sc["id"]], "smears": True, "punch_in": True}
        sc["score"] = {"key": "E", "level": 0.6, "cues": SCORE[sc["id"]]}
        envs[sc["environment"]]["backdrop"]["power"] = power_cues(sc["id"], ev)
        if sc["id"] == "arena":
            envs["arena"]["backdrop"]["power0"] = 0.4
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
