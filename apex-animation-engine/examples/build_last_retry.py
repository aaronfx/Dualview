"""Build examples/last_retry.json: "THE LAST RETRY" (Milestone 6 film, human-directed benchmark).

A digital world: floating platforms over a bottomless void. IKO (yellow, energetic, impatient) and PELL (blue,
cautious, clumsy) run a level together. No dialogue.

1. The run: IKO dashes ahead, flips, laughs and beckons; PELL follows awkwardly. At the bridge IKO waves PELL on first.
2. The collapse: the bridge gives way under PELL; he catches the far ledge and hangs; IKO, on the near side, reaches
   for him across the gap and cannot. PELL scrambles up alone. The level's alarm: ONLY 3 RETRIES REMAIN.
3. Attempt 1: IKO jumps the gap and falls short. The world freezes and rewinds; the counter goes 3 -> 2.
4. Attempt 2: IKO jumps for the pillar in the gap; it crumbles under him. Rewind; 2 -> 1.
5. The last retry: IKO drops to his knees and trembles; he looks at the way out behind him, then at PELL; he stands.
   He runs into a portal, comes out high over the gap, takes an orb, leaps over the pillar as it collapses, and only
   just catches the far ledge. PELL grabs his hand and pulls him up.
6. Together: the exit opens only when both stand at it. IKO is embarrassed; PELL nudges him; they laugh and walk
   through. LEVEL COMPLETE - TOGETHER.

The film is assembled by `apex film`: every scene is simulated, rendered and checked on its own, and the rewinds are
made from the frames of the failed attempt. The retries restart from one checkpoint (the same environment and the
same starting state; film QA checks it). Cuts are placed from the simulated events.

    PYTHONPATH=src python examples/build_last_retry.py examples/last_retry.json
"""
import copy
import json
import sys

TOP = 600.0  # the level's walking height (the void is below it)
A = (-1600.0, -500.0)  # start platform
BRIDGE = (-500.0, 100.0)
C = (100.0, 1600.0)  # the far side, with the exit
PILLAR = (-250.0, -150.0)  # a thin column in the gap (after the bridge has gone), its top a little below the level
PILLAR_TOP = TOP - 80.0
FAIL_Y = TOP - 230.0  # falling below this is a fail
IKO_CP, PELL_CP = -540.0, 136.0  # the checkpoint: where the two stand when the opening ends (the retries restart here)

CHARACTERS = [
    {"id": "iko", "name": "IKO", "strength": 48000, "proportions": {"spine": 29, "chest": 27, "head": 23, "thigh": 45, "shin": 43},
     "style": {"body_color": "#ffd84a", "far_color": "#b8962a", "visor_color": "#7cf6ff", "glow_color": "#ffe07a",
               "scarf_color": "#ff5ab4", "has_scarf": True, "limb_width": 7.5, "cadence_scale": 1.05}},
    {"id": "pell", "name": "PELL", "strength": 52000, "proportions": {"spine": 31, "chest": 29, "head": 24, "thigh": 43, "shin": 41},
     "style": {"body_color": "#6fe3ff", "far_color": "#3d93ad", "visor_color": "#ffd166", "glow_color": "#a8f0ff",
               "has_scarf": False, "limb_width": 8.0, "cadence_scale": 0.95}},
]
THEME = {"accent": "#4fd8ff", "alert": "#ff4a5a", "back": "#0d1324", "floor": "#070a14", "side": "#0b1020", "ceiling": "#05070e",
         "background": "#020308", "dust": "#bfe8ff"}


def plat(id_, x0, x1, top=TOP, thick=40.0, **kw):
    return dict(id=id_, kind="platform", center=[(x0 + x1) / 2, top - thick / 2], size=[x1 - x0, thick], **kw)


def environment(id_, bridge: bool):
    obs = [plat("A", *A, color="#2a6f8f"), plat("C", *C, color="#2a6f8f")]
    if bridge:
        obs.append(plat("bridge", *BRIDGE, thick=18.0, color="#3a8fb0", collapse={"under": "pell", "after": 5.8, "pieces": 6}))
    else:
        obs.append(dict(id="pillar", kind="platform", center=[(PILLAR[0] + PILLAR[1]) / 2, PILLAR_TOP - 150.0],
                        size=[PILLAR[1] - PILLAR[0], 300.0],
                        color="#3a7f9f", collapse={"under": "iko", "after": 0.35, "on": "orb_jump@iko", "pieces": 5}))
    env = {"id": id_, "room": {"width": 3200, "height": 1500, "depth_back": 600, "grid_spacing": 100, "grid_alpha": 0.35,
                               "entry_door": False, "void_below": TOP - 140},
           # (the exit only opens for both of them at once; the quit door behind IKO is the way out of the game, alone)
           "theme": THEME, "dust": 40, "obstacles": obs,
           "exits": [{"id": "exit", "surface": "wall_right", "s": TOP + 100, "width": 190, "unlock_on": "together:iko,pell",
                      "open_radius": 280},
                     {"id": "quit", "surface": "wall_left", "s": TOP + 100, "width": 190, "sealed": False, "open_radius": 40}],
           "decor": [
               {"kind": "screen", "x": -1250, "y": TOP + 330, "w": 260, "h": 130, "color": "#4fd8ff", "text": "LEVEL 7", "seed": 2},
               {"kind": "panel", "x": -900, "y": TOP + 260, "w": 220, "h": 170, "color": "#4fd8ff", "seed": 4},
               {"kind": "screen", "x": 700, "y": TOP + 360, "w": 240, "h": 120, "color": "#ff5ab4", "text": "EXIT >>", "seed": 6},
               {"kind": "panel", "x": 1150, "y": TOP + 250, "w": 260, "h": 170, "color": "#7cff9a", "seed": 8}]}
    if not bridge:  # the final attempt's route: a portal pair and a jump orb (present at every retry)
        env["portals"] = [{"id": "P", "center": [-1400.0, TOP + 75], "link": "Q", "angle": 0.0, "height": 150.0, "color": "#ff5ab4"},
                          {"id": "Q", "center": [-800.0, TOP + 500], "link": "P", "angle": 0.0, "height": 150.0, "color": "#ff5ab4"}]
        env["orbs"] = [{"id": "o1", "kind": "jump", "center": [-470.0, TOP + 85], "radius": 30.0, "power": 231.0}]
    return env


def checkpoint():
    return [{"character": "iko", "x": IKO_CP, "on": "obstacle:A", "facing": 1, "z": -10},
            {"character": "pell", "x": PELL_CP, "on": "obstacle:C", "facing": -1, "z": 10}]


def pell_watching(extra=(), urge=None):
    P = "pell"
    return [{"character": P, "type": "look_at", "target": "char:iko", "duration": 1.8}] + (urge or []) + [
            {"character": P, "type": "wait_for", "until": "event:takeoff@iko"},
            act(P, "shock", 1.0, "scared"),
            {"character": P, "type": "wait_for", "until": "event:fail@iko"},
            act(P, "cower", 2.0, "scared", tremble=0.6)] + list(extra)


def scene_try1(D=20.0):
    I = "iko"
    return {"id": "try1", "title": "Attempt 1", "environment": "checkpoint", "duration": D, "transition_in": "cut",
            "placements": checkpoint(), "fail": {"below": FAIL_Y, "characters": ["iko"]}, "hud": {"retries": 3},
            "actions": [
                act(I, "peer_down", 1.6, "scared"),
                {"character": I, "type": "look_at", "target": "char:pell", "duration": 2.4},
                {"character": I, "type": "walk_to", "target_x": -900},
                {"character": I, "type": "turn", "face": 1},
                act(I, "rise", 1.2, "determined", tempo=1.6),
                {"character": I, "type": "run_to", "target_x": -515},
                {"character": I, "type": "jump_to", "target_x": 40, "height": 260},  # a big leap that falls short
                {"character": I, "type": "idle", "duration": 3.0}] + pell_watching(urge=[act("pell", "wave_on", 1.6, "scared")]),
            "shots": wide(D)}


def scene_try2(D=16.0):
    I = "iko"
    return {"id": "try2", "title": "Attempt 2", "environment": "checkpoint", "duration": D, "transition_in": "rewind", "retry_of": "try1",
            "placements": checkpoint(), "fail": {"below": FAIL_Y, "characters": ["iko"]}, "hud": {"retries": 2},
            "actions": [
                {"character": I, "type": "wait_for", "until": "event:point@pell"},
                {"character": I, "type": "look_at", "target": "point:-200,%d" % PILLAR_TOP, "duration": 1.0},
                act(I, "rise", 1.0, "determined", tempo=1.8),
                {"character": I, "type": "jump_to", "target_x": -200, "height": 90, "onto": "obstacle:pillar"},
                {"character": I, "type": "idle", "duration": 3.0}] + pell_watching(
                urge=[{"character": "pell", "type": "point", "target": "point:-200,%d" % PILLAR_TOP, "duration": 1.4}]),
            "shots": wide(D)}


def scene_last(D=60.0):
    I, P = "iko", "pell"
    return {"id": "last", "title": "The last retry", "environment": "checkpoint", "duration": D, "transition_in": "rewind",
            "retry_of": "try1", "placements": checkpoint(), "fail": {"below": FAIL_Y, "characters": ["iko"]},
            "hud": {"retries": 1, "messages": [
                {"text": "LAST RETRY", "at": 0.4, "duration": 2.2, "style": "alert"},
                {"text": "LEVEL COMPLETE \u2014 TOGETHER", "on": "event:exit_reached@pell", "delay": 0.3, "duration": 6.0, "style": "success"}]},
            "actions": [
                act(I, "despair", 3.2, "sad", tremble=0.8),
                act(I, "kneel_look", 4.2, "sad", tremble=0.4),
                act(I, "rise", 2.2, "determined"),
                {"character": I, "type": "look_at", "target": "point:-470,685", "duration": 1.1},
                {"character": I, "type": "look_at", "target": "point:-1400,675", "duration": 1.2},
                {"character": I, "type": "turn", "face": -1},
                {"character": I, "type": "run_to", "target_x": -1540},
                {"character": I, "type": "catch_ledge", "target": "obstacle:C"},
                {"character": I, "type": "hang"},
                act(I, "recover_relief", 1.8, "relieved"),
                {"character": I, "type": "walk_to", "target_x": 1440, "speed": 150, "lane": -30},
                {"character": I, "type": "turn", "face": -1},
                {"character": I, "type": "wait_for", "until": "event:exit_together"},
                {"character": I, "type": "idle", "duration": 1.2},
                act(I, "embarrassed", 2.4, "embarrassed"),
                {"character": I, "type": "wait_for", "until": "event:nudge@pell"},
                {"character": I, "type": "idle", "duration": 0.4},
                act(I, "laugh", 2.2, "joyful"),
                {"character": I, "type": "turn", "face": 1},
                {"character": I, "type": "reach_exit", "target": "exit:exit"},
                {"character": P, "type": "look_at", "target": "char:iko", "duration": 1.0},
                {"character": P, "type": "wait_for", "until": "event:act@iko[clip=rise]"},
                act(P, "wave_on", 1.6, "scared"),
                {"character": P, "type": "wait_for", "until": "event:portal_exit@iko"},
                act(P, "shock", 0.9, "scared"),
                {"character": P, "type": "pull_up", "target": "char:iko"},
                act(P, "recover_relief", 1.6, "relieved"),
                {"character": P, "type": "walk_to", "target_x": 1330, "speed": 140},
                {"character": P, "type": "wait_for", "until": "event:act@iko[clip=embarrassed]"},
                {"character": P, "type": "idle", "duration": 1.2},
                {"character": P, "type": "gesture", "target": "char:iko", "gesture": "nudge"},
                act(P, "laugh", 2.2, "joyful"),
                {"character": P, "type": "wait_for", "until": "event:exit_reached@iko"},
                {"character": P, "type": "reach_exit", "target": "exit:exit"}],
            "shots": wide(D)}


def act(cid, clip, d=None, emotion=None, **kw):
    a = {"character": cid, "type": "act", "clip": clip}
    if d is not None:
        a["duration"] = d
    if emotion:
        a["emotion"] = emotion
    a.update(kw)
    return a


def wide(D, center=(-300, TOP + 150), vh=1300):
    return [{"id": "wide", "start": 0.0, "end": D, "kind": "wide", "camera": {"mode": "static", "center": list(center), "view_height": vh}}]


def scene_opening(D=36.0):
    I, P = "iko", "pell"
    return {"id": "opening", "title": "The run", "environment": "world", "duration": D, "transition_in": "fade",
            "placements": [{"character": I, "x": -1440, "on": "obstacle:A", "z": -10}, {"character": P, "x": -1510, "on": "obstacle:A", "z": 10}],
            "hud": {"retries": 3, "messages": [{"text": "THE LAST RETRY", "at": 0.7, "duration": 3.0, "style": "title"},
                                               {"text": "ONLY 3 RETRIES REMAIN", "on": "event:ledge_catch@pell", "delay": 0.4,
                                                "duration": 3.0, "style": "alert"}]},
            "actions": [
                {"character": I, "type": "idle", "duration": 3.6},
                {"character": I, "type": "run_to", "target_x": -1150, "lane": -30},
                {"character": I, "type": "jump_to", "target_x": -950, "height": 120, "flip": "front", "onto": "obstacle:A"},
                act(I, "laugh", 1.6, "joyful"),
                act(I, "beckon", 1.6, "joyful"),  # over his shoulder: come on, slowcoach
                {"character": I, "type": "run_to", "target_x": -600},
                {"character": I, "type": "turn", "face": -1},
                {"character": I, "type": "wait_for", "until": "event:act@pell[clip=peer_down]"},
                act(I, "wave_on", 1.6, "joyful"),
                {"character": I, "type": "walk_to", "target_x": -700, "lane": -40},  # steps aside (toward us) to let PELL by
                {"character": I, "type": "point", "target": "point:-200,640", "duration": 1.2},
                {"character": I, "type": "wait_for", "until": "event:ledge_catch@pell"},
                act(I, "shock", 1.0, "scared"),
                {"character": I, "type": "run_to", "target_x": -540, "lane": 0},
                act(I, "reach_out", 2.6, "scared", tremble=0.4),
                {"character": I, "type": "wait_for", "until": "event:climbed@pell"},
                act(I, "recover_relief", 2.0, "sad"),
                {"character": I, "type": "idle", "duration": 6.0}],
            "shots": wide(D)}


def pell_opening():
    P = "pell"
    return [
        {"character": P, "type": "idle", "duration": 5.0},
        {"character": P, "type": "walk_to", "target_x": -1250, "speed": 105},
        act(P, "lose_balance", 1.1, "scared"),
        {"character": P, "type": "walk_to", "target_x": -760, "speed": 115},
        act(P, "peer_down", 1.6, "scared"),
        {"character": P, "type": "wait_for", "until": "event:point@iko"},
        {"character": P, "type": "walk_to", "target_x": 300, "style": "cautious"},
        {"character": P, "type": "catch_ledge", "target": "obstacle:C"},
        {"character": P, "type": "hang", "slip_at": 1.4, "distance": 12, "duration": 4.2},
        act(P, "recover_relief_shake", 1.8, "scared"),
        {"character": P, "type": "turn", "face": -1},
        act(P, "cower", 2.0, "scared", tremble=0.5),
        {"character": P, "type": "idle", "duration": 6.0}]


def project(scenes=None):
    sc = scene_opening()
    sc["actions"] += pell_opening()
    scenes = scenes or [sc, scene_try1(), scene_try2(), scene_last()]
    return {"schema_version": "0.1", "id": "last_retry", "title": "THE LAST RETRY", "fps": 24, "width": 1920, "height": 1080, "seed": 66,
            "characters": CHARACTERS, "environments": [environment("world", True), environment("checkpoint", False)],
            "scenes": scenes}


def event_times(proj, sid):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), sid).simulate(physics_only=True)
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
        ev.setdefault(e.type, []).append(e.t)
    return ev


# each scene ends a set time after the event that closes it (a failed attempt ends just after the fall: the
# freeze and the rewind take over from its last frame)
ENDS = {"opening": ("act@pell", -1, 1.6), "try1": ("fail@iko", 0, 0.75), "try2": ("fail@iko", 0, 0.75),
        "last": ("exit_reached@pell", 0, 3.6)}


def finalize(proj):
    for sc in proj["scenes"]:
        key, k, pad = ENDS[sc["id"]]
        ev = event_times(proj, sc["id"])
        sc["duration"] = round(ev[key][k] + pad, 2)
        sc["shots"] = shots_for(sc, ev)
        sc["time_fx"] = {"hit_stop": False, "slowmo": SLOWMO[sc["id"]], "smears": True, "punch_in": False}
    return proj


def cam(mode, **kw):
    return dict(mode=mode, **kw)


def shot(id_, kind, desc, camera, **kw):
    return dict(id=id_, kind=kind, description=desc, camera=camera, **kw)


def cut(shots, times):
    for i, sh in enumerate(shots):
        sh["start"], sh["end"] = round(times[i], 2), round(times[i + 1], 2)
    return shots


Y = TOP + 110  # eye line of the level


def shots_for(sc, ev):
    D = sc["duration"]
    f = lambda k, i=0: ev[k][i]
    sid = sc["id"]
    if sid == "opening":
        S = [shot("o1_level", "establishing", "the level: floating platforms over a void; the title",
                  cam("dolly", center=[-350, Y + 120], center_end=[-1050, Y + 20], view_height=1250, view_height_end=760)),
             shot("o2_run", "tracking", "IKO dashes off, flips, lands and laughs",
                  cam("follow", target="iko", view_height=560, offset=[60, 40], lead=0.3, stiffness=4.0)),
             shot("o3_pell", "medium", "PELL trails behind and stumbles; IKO beckons him on",
                  cam("follow", target="pell", view_height=560, offset=[120, 40], include=["char:iko"], stiffness=3.0)),
             shot("o4_bridge", "medium", "at the bridge: PELL peers into the void; IKO waves him on first",
                  cam("static", target="pell", center=[-640, Y], view_height=520, include=["char:iko", "char:pell"])),
             shot("o5_cross", "tracking", "PELL inches across the bridge",
                  cam("follow", target="pell", view_height=540, offset=[40, 20], stiffness=3.0, include=["obstacle:C"])),
             shot("o6_collapse", "wide", "the bridge gives way; PELL catches the far ledge and hangs; IKO reaches across in vain",
                  cam("static", target="pell", center=[-230, Y - 60], view_height=820, include=["char:iko", "char:pell"])),
             shot("o7_after", "medium", "PELL scrambles up alone; across the gap, IKO's relief, PELL's fear",
                  cam("static", target="iko", center=[-200, Y], view_height=760, include=["char:iko", "char:pell"]), fade_out=0.0)]
        t = [0.0, f("takeoff@iko") - 1.4, f("act@pell", 0) - 0.4, f("act@pell", 1) - 0.6, f("point@iko") + 1.6,
             f("collapse") - 1.0, f("climb_start@pell") + 0.2, D]
        return cut(S, t)
    if sid in ("try1", "try2"):
        n = sid[-1]
        S = [shot(f"t{n}_plan", "wide", "the checkpoint: IKO at the edge, PELL across the gap",
                  cam("static", target="iko", center=[-330, Y], view_height=820, include=["char:iko", "char:pell"])),
             shot(f"t{n}_jump", "tracking", "the jump, and the fall",
                  cam("follow", target="iko", view_height=720, offset=[0, 0], lead=0.2, stiffness=5.0))]
        return cut(S, [0.0, f("takeoff@iko") - 0.5, D])
    if sid == "last":
        S = [shot("l1_knees", "medium", "IKO drops to his knees and trembles",
                  cam("static", target="iko", center=[-560, Y - 20], view_height=420)),
             shot("l2_wayout", "wide", "he looks back at the way out, then across at PELL",
                  cam("static", target="iko", center=[-1060, Y + 20], view_height=760, include=["char:iko", "exit:quit"])),
             shot("l3_pell", "medium", "PELL, alone across the gap, waiting",
                  cam("static", target="pell", center=[150, Y], view_height=420)),
             shot("l4_rise", "medium", "IKO stands up; he looks at the orb, the portal: a plan",
                  cam("static", target="iko", center=[-760, Y + 60], view_height=620, include=["char:iko", "point:-470,685"])),
             shot("l5_stunt", "wide", "into the portal, out above the gap, the orb, over the falling pillar, and the far ledge, just",
                  cam("follow", target="iko", view_height=900, lead=0.35, stiffness=3.0, bound_to_room=True)),
             shot("l6_grab", "medium", "PELL grabs his hand and pulls him up",
                  cam("static", target="iko", center=[140, Y - 60], view_height=480, include=["char:iko", "char:pell"])),
             shot("l7_walk", "tracking", "together, to the exit",
                  cam("follow", target="pell", view_height=620, offset=[80, 30], stiffness=2.5, include=["char:iko"], bound_to_room=True)),
             shot("l8_exit", "medium", "the exit opens for both; IKO, embarrassed; a nudge; they laugh and walk through",
                  cam("static", target="pell", center=[1290, Y + 10], view_height=520, include=["char:iko", "char:pell", "exit:exit"]),
                  fade_out=1.6)]
        kl = f("act@iko", 1)  # kneel_look starts
        t = [0.0, kl + 0.7, kl + 2.6, kl + 3.9, f("portal_enter@iko") - 2.4, f("ledge_catch@iko") + 0.25,
             f("pulled_up@iko") + 1.2, f("exit_together") - 1.6, D]
        return cut(S, t)
    return wide(D)


SLOWMO = {"opening": [{"at": "collapse@bridge", "before": 0.1, "after": 0.7, "rate": 0.4},
                      {"at": "ledge_catch@pell", "before": 0.05, "after": 0.4, "rate": 0.45}],
          "try1": [{"at": "fail@iko", "before": 0.4, "after": 0.3, "rate": 0.4}],
          "try2": [{"at": "collapse@pillar", "before": 0.1, "after": 0.6, "rate": 0.4}],
          "last": [{"at": "orb_jump@iko", "before": 0.1, "after": 0.5, "rate": 0.45},
                   {"at": "ledge_catch@iko", "before": 0.35, "after": 0.55, "rate": 0.3},
                   {"at": "hand_grab@pell", "before": 0.1, "after": 0.5, "rate": 0.4}]}


if __name__ == "__main__":
    proj = finalize(project())
    json.dump(proj, open(sys.argv[1], "w"), indent=1)
    for sc in proj["scenes"]:
        print(f"{sc['id']:8s} {sc['duration']:6.2f}s  " + ", ".join(f"{sh['id']} {sh['start']:.2f}-{sh['end']:.2f}" for sh in sc["shots"]))
