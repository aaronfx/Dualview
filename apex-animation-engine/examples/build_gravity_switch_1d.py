"""Builds examples/gravity_switch_1d.json (tunable parameters at the top).

Usage:  python examples/build_gravity_switch_1d.py examples/gravity_switch_1d.json

Several values are tuned against the simulation and are not free to change independently: the rail position
(`bar`) lies on AXEL's simulated fall path, and the shot `cuts` are placed around simulated event times. After
changing timing upstream, re-run the scene (`apex render ... --scale 0.5 --review-dir ...`) and check the
grab and cut placements.
"""
import json
import sys

P = dict(
    beam=(497.0, 760.0, 30.0, 130.0),
    bar=(258.0, 1202.0),
    sw2_x=345.0, sw2_h=30.0,
    sw2_delay=1.85, sw2_dur=0.5,
    stop_s=1314.0, jump_target=1320.0, jump_h=132.0,
    slide_start=575.0, slide_end=965.0,
    release_deg=30.0, swings=1, release_face=-1,
    duration=30.0,
    hang=1.0,
    cuts=[1.6, 2.55, 5.6, 7.25, 9.6, 11.45, 12.15, 13.2, 13.85, 16.45, 19.0, 19.95, 22.1, 23.75, 25.9],
)
def cue(ev, snd, g=1.0):
    return dict(on_event=ev, sound=snd, gain=g)


def SHOTS_DEFAULT(P):
    T = P.get("cuts")
    if not T:
        return None
    c = lambda **k: k
    S = lambda i, j, **k: dict(start=T[i] if i >= 0 else 0.0, end=T[j] if j < len(T) else P["duration"], **k)
    return [
        S(-1, 0, id="s01_establish", kind="establishing", description="wide push-in: the room, the floor switch, the conduit beam, the rail, the second switch and the sealed door on the ceiling; AXEL enters",
          camera=c(mode="dolly", center=[-40, 760], center_end=[-120, 690], view_height=1700, view_height_end=1450)),
        S(0, 1, id="s02_notice", kind="close", description="close: double take at the switch",
          camera=c(mode="follow", target="axel", focus="upper", view_height=420, offset=[165, 20], lead=0.05),
          sound_cues=[cue("notice", "notice")], exit_conditions=["event:notice"]),
        S(1, 2, id="s03_approach", kind="medium", description="cautious approach",
          camera=c(mode="follow", target="axel", view_height=470, offset=[90, 30], lead=0.3)),
        S(2, 3, id="s04_insert", kind="insert", description="insert: hesitation, then the hand presses the switch",
          camera=c(mode="static", center=[8, 92], view_height=210),
          sound_cues=[cue("press_contact", "click"), cue("switch_activated", "startle")], exit_conditions=["event:press_contact"]),
        S(3, 4, id="s05_shift", kind="tracking", description="G0 -> G1 (+90 deg): loses support, falls to the right wall, braces, lands",
          camera=c(mode="follow", target="axel", view_height=820, offset=[140, 120], lead=0.35, stiffness=4.0, shake=1.0),
          sound_cues=[cue("gravity_shift", "pulse"), cue("lost_support", "whoosh"), cue("impact", "impact")],
          exit_conditions=["event:gravity_shift", "event:lost_support", "event:impact"]),
        S(4, 5, id="s06_recover", kind="medium", description="the camera turns with gravity; relief (exhale, hands on knees); double take: something far above",
          camera=c(mode="follow", target="axel", view_height=640, offset=[-170, 250], lead=0.1, stiffness=3.0, roll_mode="align_gravity", shake=0.5),
          sound_cues=[cue("notice", "notice")], exit_conditions=["grounded_on:wall_right", "event:notice"]),
        S(5, 6, id="s07_door_pov", kind="insert", description="POV: the sealed exit, high on the far end wall (the old ceiling)",
          camera=c(mode="static", center=[-440, 1060], view_height=640, roll=90),
          sound_cues=[cue("point", "chime")], exit_conditions=["event:point"]),
        S(6, 7, id="s08_point", kind="medium", description="AXEL points at it, then spots the second switch",
          camera=c(mode="follow", target="axel", view_height=560, offset=[-90, 170], lead=0.1, stiffness=4.0, roll=90),
          sound_cues=[cue("notice", "notice")], exit_conditions=["event:notice"]),
        S(7, 8, id="s09_switch_pov", kind="insert", description="POV: the second switch on the end wall",
          camera=c(mode="static", center=[400, 1335], view_height=380, roll=90)),
        S(8, 9, id="s10_slide", kind="tracking", description="sprint along the wall, slide under the conduit beam",
          camera=c(mode="follow", target="axel", view_height=520, offset=[0, 60], lead=0.3, stiffness=5.0, roll=90),
          sound_cues=[cue("slide_start", "slide")], exit_conditions=["event:slide_start", "event:slide_end"]),
        S(9, 10, id="s11_slap", kind="medium", description="end wall: looks up, jumps, slaps the switch mid-air, lands",
          camera=c(mode="static", center=P.get("slap_cam", [445, 1290]), view_height=480, roll=90),
          sound_cues=[cue("press_contact", "click"), cue("switch_activated", "startle")], exit_conditions=["event:press_contact"]),
        S(10, 11, id="s12_reestablish", kind="establishing", description="re-establishing wide in the film's home orientation: AXEL high on the right wall, the rail mid-room, the far wall; the second switch acts",
          camera=c(mode="static", center=[40, 1010], view_height=1150, roll=0),
          sound_cues=[cue("gravity_shift", "pulse"), cue("lost_support", "whoosh")], exit_conditions=["event:gravity_shift", "event:lost_support"]),
        S(11, 12, id="s13_catch_swing", kind="tracking", description="no roll: he falls across the room, tumbles feet-first, catches the rail (kept in frame), dangles, pumps, lets go at the top",
          camera=c(mode="follow", target="axel", view_height=720, offset=[-110, -170], lead=0.15, stiffness=5.0, roll=0, shake=0.8, include=["bar:rail"]),
          sound_cues=[cue("grab", "clank")], exit_conditions=["event:grab", "event:release"]),
        S(12, 13, id="s14_drop_land", kind="tracking", description="drop to the far wall, three-point landing",
          camera=c(mode="follow", target="axel", view_height=640, offset=[60, 40], lead=0.2, stiffness=4.5, roll=0, shake=1.0),
          sound_cues=[cue("impact", "impact")], exit_conditions=["grounded_on:wall_left"]),
        S(13, 14, id="s15_relief_door", kind="medium", description="relief (head shake) while the camera turns a quarter with gravity (he is still); the door slides open",
          camera=c(mode="follow", target="axel", view_height=600, offset=[60, 40], lead=0.1, stiffness=3.0, roll=0, roll_mode="align_gravity", include=["exit:door1"]),
          sound_cues=[cue("door_unlocking", "unlock"), cue("door_open", "door")], exit_conditions=["event:door_open"]),
        S(14, 15, id="s16_exit", kind="wide", description="walks to the doorway, looks back at the room, steps into the light; the door closes; fade out",
          camera=c(mode="dolly", center=[-430, 1250], center_end=[-460, 1300], view_height=740, view_height_end=660, roll=-90),
          sound_cues=[cue("exit_reached", "resolve"), cue("door_close", "door")], exit_conditions=["event:look_back", "event:exit_reached"], fade_out=0.9),
    ]


def build(P, shots=None):
    A = lambda **k: dict(character="axel", **k)
    actions = [
        A(type="walk_to", target_x=-330, speed=150),
        A(type="notice", target="switch:gswitch", duration=0.85),
        A(type="walk_to", target_x=-62, style="cautious", target="switch:gswitch", speed=105),
        A(type="press", switch="gswitch", hesitate=True),
        A(type="wait_grounded"),
        A(type="notice", target="exit:door1", duration=0.8),
        A(type="point", target="exit:door1", duration=1.0),
        A(type="notice", target="switch:sw2", duration=0.8),
        A(type="run_to", target_x=P["slide_start"]),
        A(type="duck_slide", target_x=P["slide_end"]),
        A(type="run_to", target_x=P["stop_s"]),
        A(type="look_at", target="switch:sw2", duration=0.55),
        A(type="jump_to", target_x=P["jump_target"], height=P["jump_h"], switch="sw2"),
        A(type="grab_swing", target="bar:rail", release_deg=P["release_deg"], swings=P["swings"], face=P["release_face"], duration=P.get("hang", 1.3)),
        A(type="wait_grounded"),
        A(type="look_at", target="exit:door1", duration=0.25),
        A(type="reach_exit", target="exit:door1", speed=165, duration=0.6),
        A(type="idle", duration=3.0),
    ]
    env = dict(
        id="chamber", room=dict(width=1200, height=1400), gravity=[0, -1568],
        switches=[
            dict(id="gswitch", x=0, height=66, surface="floor", effect=dict(rotate_deg=90, delay=0.9, duration=0.25)),
            dict(id="sw2", x=P["sw2_x"], height=P["sw2_h"], surface="ceiling",
                 effect=dict(rotate_deg=-180, delay=P["sw2_delay"], duration=P["sw2_dur"])),
        ],
        props=[dict(id="crate_a", kind="crate", position=[230, 21], size=[42, 42], mass=10),
               dict(id="crate_b", kind="crate", position=[370, 17], size=[34, 34], mass=6)],
        exits=[dict(id="door1", surface="ceiling", s=-488, width=220, unlock_on="switch:sw2")],
        obstacles=[dict(id="conduit", kind="beam", center=[P["beam"][0], P["beam"][1]], size=[P["beam"][2], P["beam"][3]]),
                   dict(id="rail", kind="bar", center=list(P["bar"]), size=[12, 12])],
        dust=170,
    )
    shots = shots or SHOTS_DEFAULT(P) or [dict(id="wide", start=0, end=P["duration"], kind="wide",
                           camera=dict(mode="static", center=[0, 700], view_height=1500))]
    return dict(schema_version="0.1", id="gravity_switch_1d", title="Gravity Switch - Escape Room (1D, 30 s)", fps=24, width=1920,
                height=1080, seed=7, characters=[dict(id="axel", name="AXEL")], environments=[env],
                scenes=[dict(id="escape", title="Gravity Switch: Escape Room", environment="chamber", duration=P["duration"],
                             placements=[dict(character="axel", x=-520, facing=1)], actions=actions, shots=shots)])


if __name__ == "__main__":
    json.dump(build(P), open(sys.argv[1], "w"), indent=1)
