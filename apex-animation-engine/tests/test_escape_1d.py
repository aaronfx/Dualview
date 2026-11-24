"""Milestone 1D: slide, jump_to (mid-air press), grab_swing, reach_exit, the door state machine, signed gravity
rotations and the 30-second Gravity Switch story."""
import json
import math

import numpy as np
import pytest

from apex.physics.gravity import GravityField, GravityTransition
from apex.scene.schema import ActionSpec, GravityEffect, ProjectSpec

from .conftest import ROOT, load


@pytest.fixture(scope="session")
def escape_project():
    return load("gravity_switch_1d.json")


@pytest.fixture(scope="session")
def escape_runtime(escape_project):
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(escape_project, "escape")
    rt.simulate()
    return rt


@pytest.fixture(scope="session")
def escape_report(escape_runtime, escape_project):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    cam = build_camera(escape_runtime, escape_project.width / escape_project.height)
    return Inspector(escape_runtime, cam, escape_project.fps).run(check_determinism=False)


def _ev(rt, kind, after=0.0, **match):
    return next(e for e in rt.result.events if e.type == kind and e.t >= after and all(e.data.get(k) == v for k, v in match.items()))


# ---------------------------------------------------------------- schema
def test_gravity_effect_needs_exactly_one_form():
    with pytest.raises(Exception):
        GravityEffect()
    with pytest.raises(Exception):
        GravityEffect(to=(1, 0), rotate_deg=90)
    assert GravityEffect(rotate_deg=-180).rotate_deg == -180
    assert GravityEffect(to=(-1, 0), turn="ccw").turn == "ccw"


def test_new_actions_validate_their_targets():
    with pytest.raises(Exception):
        ActionSpec(type="grab_swing", character="a", target="exit:door1")
    with pytest.raises(Exception):
        ActionSpec(type="reach_exit", character="a", target="bar:rail")
    with pytest.raises(Exception):
        ActionSpec(type="jump_to", character="a", target_x=10)  # needs height
    ActionSpec(type="duck_slide", character="a", target_x=900)


def test_unlock_on_must_name_a_known_switch():
    data = json.loads((ROOT / "examples" / "gravity_switch_1d.json").read_text())
    data["environments"][0]["exits"][0]["unlock_on"] = "switch:nope"
    with pytest.raises(Exception):
        ProjectSpec.model_validate(data)


# ---------------------------------------------------------------- gravity angles
def test_signed_sweep_controls_the_rotation_direction():
    g = GravityField(initial=(1568.0, 0.0))
    g.schedule(GravityTransition(1.0, 1.0, (-1568.0, 0.0), easing="linear", sweep=-math.pi))
    mid = g.at(1.5)  # a clockwise half turn from +x passes through -y (the original "down"), not +y
    assert mid[1] < -1500 and abs(mid[0]) < 5
    g2 = GravityField(initial=(1568.0, 0.0))
    g2.schedule(GravityTransition(1.0, 1.0, (-1568.0, 0.0), easing="linear", sweep=math.pi))
    assert g2.at(1.5)[1] > 1500


def test_unwrapped_angle_and_report():
    g = GravityField()  # original down = -90 deg
    g.schedule(GravityTransition(1.0, 0.25, (1568.0, 0.0), sweep=math.pi / 2))
    g.schedule(GravityTransition(3.0, 0.5, (-1568.0, 0.0), sweep=-math.pi))
    assert abs(math.degrees(g.angle_unwrapped(2.0)) - 0.0) < 1e-9
    assert abs(math.degrees(g.angle_unwrapped(4.0)) + 180.0) < 1e-9
    ts = np.linspace(0, 4, 400)
    a = np.array([g.angle_unwrapped(float(t)) for t in ts])
    assert np.max(np.abs(np.diff(a))) < 0.2  # continuous: no 360-degree jumps
    rep = g.report()
    assert [round(r["rel_prev_deg"]) for r in rep] == [0, 90, -180]
    assert [round(r["rel_original_deg"]) for r in rep] == [0, 90, -90]


def test_story_gravity_states(escape_runtime):
    rep = escape_runtime.result.gravity.report()
    assert [r["state"] for r in rep] == ["G0", "G1", "G2"]
    assert round(rep[1]["rel_prev_deg"]) == 90 and round(rep[2]["rel_prev_deg"]) == -180
    assert round(rep[2]["rel_original_deg"]) == -90 and round(rep[2]["world_deg"]) == 180
    shift = _ev(escape_runtime, "gravity_shift", switch="sw2")
    assert round(shift.data["rel_prev_deg"]) == -180 and round(shift.data["rel_original_deg"]) == -90


# ---------------------------------------------------------------- story order and physical coherence
def test_story_beats_in_order(escape_runtime):
    rt = escape_runtime
    seq = [_ev(rt, "press_contact", switch="gswitch")]
    seq.append(_ev(rt, "impact", seq[-1].t, surface="wall_right"))
    seq.append(_ev(rt, "point", seq[-1].t))
    seq.append(_ev(rt, "slide_start", seq[-1].t))
    seq.append(_ev(rt, "slide_end", seq[-1].t))
    seq.append(_ev(rt, "press_contact", seq[-1].t, switch="sw2"))
    seq.append(_ev(rt, "lost_support", seq[-1].t, surface="wall_right"))
    seq.append(_ev(rt, "grab", seq[-1].t))
    seq.append(_ev(rt, "release", seq[-1].t))
    seq.append(_ev(rt, "impact", seq[-1].t, surface="wall_left"))
    seq.append(_ev(rt, "door_open", seq[-1].t - 0.01))
    seq.append(_ev(rt, "exit_reached", seq[-1].t))
    assert seq[-1].t < rt.result.duration - 1.0  # the film ends after the exit, with a hold


def test_second_switch_is_slapped_mid_air(escape_runtime):
    rt = escape_runtime
    e = _ev(rt, "press_contact", switch="sw2")
    an = rt.result.animators["axel"]
    assert an.segments[an.segment_at(e.t)].kind == "airborne"
    j = rt.rigs["axel"].world_joints(an.pose_at(e.t))
    assert min(math.dist(j["hand_n"], e.data["point"]), math.dist(j["hand_f"], e.data["point"])) < 5.0


def test_slide_clears_the_beam(escape_runtime):
    rt = escape_runtime
    beam = next(o for o in rt.env.obstacles if o.kind == "beam")
    an = rt.result.animators["axel"]
    seg = next(s for s in an.segments if s.kind == "slide")
    lowest_gap = 1e9
    for t in np.arange(seg.t0, seg.t1, 1 / 96):
        j = rt.rigs["axel"].world_joints(an.pose_at(float(t)))
        for p in j.values():
            if beam.center[1] - beam.size[1] / 2 <= p[1] <= beam.center[1] + beam.size[1] / 2:
                lowest_gap = min(lowest_gap, p[0] - (beam.center[0] + beam.size[0] / 2))  # G1 "up" is -x: underside = +x face
    assert 0 < lowest_gap < 60  # under the beam, close to it: a real duck, not a wide miss


def test_hands_stay_on_the_rail(escape_runtime):
    rt = escape_runtime
    an = rt.result.animators["axel"]
    seg = next(s for s in an.segments if s.kind == "swing")
    B = seg.data["anchor"]
    for t in np.arange(seg.t0, seg.t1, 1 / 120):
        j = rt.rigs["axel"].world_joints(an.pose_at(float(t)))
        assert math.dist(j["wrist_n"], B) < 1.5 and math.dist(j["wrist_f"], B) < 1.5


def test_grip_radius_is_arms_overhead(escape_runtime):
    rt = escape_runtime
    an = rt.result.animators["axel"]
    seg = next(s for s in an.segments if s.kind == "swing")
    B = seg.data["anchor"]
    r = [math.dist(an.pose_at(float(t)).root, B) for t in np.linspace(seg.t0, seg.t1 - 1e-3, 30)]
    assert 85 < min(r) and max(r) < 115  # pelvis ~ shoulder height + straight arms below the bar, rigidly constant


def test_release_at_the_top_of_the_swing(escape_runtime):
    e = _ev(escape_runtime, "release")
    assert e.data["speed"] < 60.0
    land = _ev(escape_runtime, "impact", e.t, surface="wall_left")
    assert land.data["normal_speed"] < 1700


def test_catch_absorbs_energy_and_pumping_is_booked(escape_runtime):
    g = _ev(escape_runtime, "grab")
    assert g.data["speed_after"] < g.data["speed"]
    an = escape_runtime.result.animators["axel"]
    seg = next(s for s in an.segments if s.kind == "swing")
    assert seg.data["pumps"] and seg.data["work"][-1][1] > 0


def test_only_supporting_surfaces_are_landings(escape_runtime):
    rt = escape_runtime
    for e in rt.result.events:
        if e.type == "impact":
            gd = rt.result.gravity.direction(e.t)
            n = rt.result.frames[e.data["surface"]].normal
            assert -(gd[0] * n[0] + gd[1] * n[1]) >= math.cos(math.radians(55))


def test_hard_landings_get_the_relief_beat(escape_runtime):
    from apex.motion.controller import RECOVER_T
    an = escape_runtime.result.animators["axel"]
    settles = [s for s in an.segments if s.kind == "idle" and s.data.get("settle")]
    assert len(settles) == 2  # after the wall landing and after the drop from the rail
    assert all(s.t1 - s.t0 >= RECOVER_T - 1e-3 for s in settles)


def test_startle_is_eased(escape_runtime):
    rt = escape_runtime
    e = _ev(rt, "press_contact", switch="gswitch")
    an = rt.result.animators["axel"]
    ts = np.arange(e.t, e.t + 0.6, 1 / 240)
    ys = [an.pose_at(float(t)).root[1] for t in ts]
    assert max(abs(np.diff(ys))) * 240 < 340  # about half the 1C review value (pelvis rose ~22 u in 0.08 s, ~634 u/s)


# ---------------------------------------------------------------- door state machine
def test_door_state_machine(escape_runtime):
    from apex.scene.runtime import DOOR_OPEN_S, DOOR_UNLOCK_S, door_state
    d = escape_runtime.result.doors["door1"]
    act = _ev(escape_runtime, "switch_activated", switch="sw2").t
    assert d["unlock_t"] > act and d["open_t"] >= d["unlock_t"] + DOOR_UNLOCK_S and d["exit_t"] >= d["open_t"] + 0.45
    assert door_state(d, act)[0] == "sealed"
    assert door_state(d, d["unlock_t"] + 0.1)[0] == "unlocking"
    assert door_state(d, d["open_t"] - 0.01)[0] == "unlocked"
    assert door_state(d, d["open_t"] + DOOR_OPEN_S / 2)[0] == "opening"
    assert door_state(d, d["exit_t"] + 0.1)[0] == "exited"


def test_door_waits_for_the_character():
    """reach_exit stops at the threshold until the door is open."""
    from apex.scene.runtime import SceneRuntime
    data = json.loads((ROOT / "examples" / "gravity_switch_1d.json").read_text())
    data["environments"][0]["exits"][0]["unlock_on"] = None  # never unlocks
    rt = SceneRuntime(ProjectSpec.model_validate(data), "escape")
    r = rt.simulate()
    assert not any(e.type in ("door_open", "exit_reached") for e in r.events)
    an = r.animators["axel"]
    s_end, _ = r.frames["wall_left"].to_frame(an.pose_at(r.duration - 0.01).root)
    assert s_end > -1400 + 20  # still inside the room, in front of the door plane


# ---------------------------------------------------------------- camera / QA / render
def test_camera_rolls_with_gravity_both_ways(escape_runtime, escape_project):
    from apex.render.pipeline import build_camera
    cam = build_camera(escape_runtime, 16 / 9)
    s06 = next(s for s in cam.shots if s.id == "s06_recover")
    relief = next(s for s in cam.shots if s.id == "s15_relief_door")
    assert abs(cam.at(s06.end - 1e-3).roll - 90) < 3
    assert abs(cam.at(relief.end - 1e-3).roll + 90) < 3  # turned back the other way (CW gravity sweep)
    rates = [abs(cam.at(t + 1 / 24).roll - cam.at(t).roll) * 24 for t in np.arange(relief.start, relief.end - 0.05, 1 / 24)]
    assert max(rates) <= 150


def test_no_roll_during_the_catch_swing_and_drop(escape_runtime):
    """Quality upgrade: the swing is staged world-fixed (re-establishing wide, then catch/swing/drop with no roll) so
    spatial orientation is preserved; the single quarter-turn to the new gravity happens in the still relief beat."""
    from apex.render.pipeline import build_camera
    cam = build_camera(escape_runtime, 16 / 9)
    shots = {s.id: s for s in cam.shots}
    for sid in ("s12_reestablish", "s13_catch_swing", "s14_drop_land"):
        sh = shots[sid]
        rolls = [cam.at(float(t)).roll for t in np.arange(sh.start, sh.end - 1e-3, 1 / 24)]
        assert max(rolls) - min(rolls) < 1.0, sid
    sw = shots["s13_catch_swing"]
    g = _ev(escape_runtime, "grab")
    assert sw.start < g.t < sw.end and "bar:rail" in sw.camera.include


def test_inspector_passes_1d(escape_report):
    assert escape_report.passed, escape_report.summary()
    by = {c.name: c for c in escape_report.checks}
    for name in ("grip_attachment[axel]", "swing_energy_conserved[axel]", "obstacle_clearance", "hand_on_switch_at_contact",
                 "landings_on_supporting_surfaces", "camera_roll_follows_gravity_direction", "gravity_angle_report",
                 "door_state_machine[door1]", "subject_in_frame", "gravity_direction[axel]", "surface_penetration[axel]"):
        assert by[name].status == "PASS", by[name]


def test_render_open_door_frame(escape_runtime, escape_project):
    from apex.render.pipeline import _effects_from_events, build_camera
    from apex.render.skia_renderer import SkiaRenderer
    rt = escape_runtime
    cam = build_camera(rt, 16 / 9)
    r = SkiaRenderer(320, 180, rt.env, {"axel": escape_project.character("axel").style}, rt.rigs)
    fx = _effects_from_events(rt.result.events, {s.id: s for s in rt.env.switches}, rt.env)
    t = rt.result.doors["door1"]["exit_t"] + 0.2
    img = r.render(rt.evaluate(t), cam.at(t), 0.0, fx)
    assert img.shape == (180, 320, 4) and img[..., :3].mean() > 5


def test_new_sounds(tmp_path):
    from apex.audio.sound_director import SoundDirector
    from apex.motion.controller import Event
    ev = [Event(0.1, "slide_start", "a"), Event(0.5, "grab", "a"), Event(0.9, "door_unlocking", "a", {"exit": "d"}),
          Event(1.2, "door_open", "a", {"exit": "d"}), Event(1.6, "exit_reached", "a", {"exit": "d"})]
    cues = SoundDirector(1).render(ev, 3.0, str(tmp_path / "s.wav"))
    assert {c.sound for c in cues} == {"slide", "clank", "unlock", "door", "resolve"}


# ---------------------------------------------------------------- 1D review revisions (Part A)
def test_hard_landing_is_three_point(escape_runtime):
    """Weight on impact: on a hard landing the near hand touches the surface ahead of the feet."""
    rt = escape_runtime
    an = rt.result.animators["axel"]
    for seg in (s for s in an.segments if s.kind == "landing" and s.data["approach"] > 1200):
        F = rt.result.frames[seg.frame]
        h = min(F.to_frame(rt.rigs["axel"].world_joints(an.pose_at(float(t)))["hand_n"])[1]
                for t in np.arange(seg.t0 + 0.15, seg.t0 + 0.4, 1 / 96))
        assert h < 12.0


def test_heavier_landing_recovers_more_slowly():
    from apex.core.mathx import damped_spring
    # the controller's landing spring: heavy impacts use a lower frequency and more damping
    light = damped_spring(60.0, -600 * 0.9, 88.7, 11.0, 0.55, 0.25)[0]
    heavy = damped_spring(60.0, -1500 * 0.9, 88.7, 9.0, 0.8, 0.25)[0]
    assert heavy < light


def test_relief_beats_vary(escape_runtime):
    an = escape_runtime.result.animators["axel"]
    settles = [s for s in an.segments if s.kind == "idle" and s.data.get("settle")]
    assert [s.data["variant"] for s in settles] == [0, 1]
    assert all(0.75 <= s.data["settle_k"] <= 1.25 for s in settles)


def test_reversal_reaction_before_losing_support(escape_runtime):
    """When the floor starts to tilt away he reacts (arms out, eyes wide) before the fall."""
    rt = escape_runtime
    an = rt.result.animators["axel"]
    shift = _ev(rt, "gravity_shift", switch="sw2").t
    lost = _ev(rt, "lost_support", shift).t
    before = an.pose_at(shift - 0.05)
    during = an.pose_at(min(lost - 0.01, shift + 0.18))
    assert during.eye > before.eye + 0.3


def test_threshold_look_back_holds_still(escape_runtime):
    rt = escape_runtime
    lb = _ev(rt, "look_back")
    ex = _ev(rt, "exit_reached", lb.t)
    an = rt.result.animators["axel"]
    a, b = an.pose_at(lb.t + 0.1).root, an.pose_at(lb.t + 0.5).root
    assert math.dist(a, b) < 2.0 and ex.t > lb.t + 0.5


def test_door_closes_behind_him(escape_runtime):
    from apex.scene.runtime import DOOR_CLOSE_DELAY, DOOR_CLOSE_S, door_state
    d = escape_runtime.result.doors["door1"]
    x = d["exit_t"]
    assert door_state(d, x + DOOR_CLOSE_DELAY + DOOR_CLOSE_S / 2)[0] == "closing"
    assert door_state(d, x + DOOR_CLOSE_DELAY + DOOR_CLOSE_S + 0.01)[0] == "closed"
    assert x + DOOR_CLOSE_DELAY + DOOR_CLOSE_S < escape_runtime.result.duration - 0.2  # the close is seen before the end


def test_final_shot_fades_out(escape_runtime):
    from apex.render.pipeline import build_camera, shot_fade
    cam = build_camera(escape_runtime, 16 / 9)
    end = escape_runtime.result.duration
    assert shot_fade(cam, end - 1e-3) > 0.98 and shot_fade(cam, end - 1.2) == 0.0


def test_rail_is_long_on_screen_at_the_catch(escape_runtime, escape_project):
    """1D review: the rail read as a glow at the hands. At the catch it must project to a clearly visible bar."""
    from apex.render.pipeline import build_camera
    from apex.render.skia_renderer import FOV_K
    rt = escape_runtime
    cam = build_camera(rt, 16 / 9)
    g = _ev(rt, "grab")
    c = cam.at(g.t - 1e-3)
    x, y = next(o.center for o in rt.env.obstacles if o.kind == "bar")
    focal, Fd = 1080 * FOV_K, c.view_h * FOV_K
    P = lambda z: ((x - c.cx) * focal / (Fd + z), -(y - c.cy) * focal / (Fd + z))
    a, b = P(rt.env.room.depth_back), P(0.0)
    assert math.dist(a, b) > 90  # pixels at 1080p from the back-wall bracket to the character plane
