"""Professional-quality upgrade: motion library, contact constraints, composition rules, renderer adapter, audio, review."""
import json
import math
import wave

import numpy as np
import pytest

from apex.motion.library import (EMOTIONS, NEUTRAL, Contact, KeyPose, MotionClip, Performance, clip_from_dict, get_clip,
                                 landing_clip, list_clips)

from .conftest import ROOT, load


# ---------------------------------------------------------------- motion library
def test_library_clips_load_and_use_known_channels():
    names = list_clips()
    for n in ("lose_balance", "fall_flail", "brace", "land_hard", "land_medium", "recover_relief", "recover_relief_shake"):
        assert n in names
        c = get_clip(n)
        assert c.length() > 0 and c.keys
        for k in c.keys:
            assert set(k.values) <= set(NEUTRAL)


def test_unknown_channel_is_rejected():
    with pytest.raises(ValueError):
        clip_from_dict({"name": "bad", "duration": 1, "keys": [{"t": 0, "pose": {"wiggle": 1}}]})


def test_monotone_cubic_does_not_overshoot_between_keys():
    c = MotionClip("m", 1.0, [KeyPose(0, "a", {"lean": 0.0}), KeyPose(0.5, "b", {"lean": 1.0}), KeyPose(1.0, "c", {"lean": 1.05})])
    vals = [c.channel("lean", t) for t in np.linspace(0, 1, 201)]
    assert min(vals) >= -1e-9 and max(vals) <= 1.05 + 1e-9
    assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))  # monotone data -> monotone curve


def test_interpolation_modes_hit_the_keys():
    for mode in ("smooth", "ease", "snap", "slow_in", "back", "linear"):
        c = MotionClip("m", 1.0, [KeyPose(0, "a", {"crouch": 0.0}, mode), KeyPose(1.0, "b", {"crouch": 0.4})])
        assert abs(c.channel("crouch", 0.0)) < 1e-9 and abs(c.channel("crouch", 1.0) - 0.4) < 1e-9
    hold = MotionClip("h", 1.0, [KeyPose(0, "a", {"crouch": 0.1}, "hold"), KeyPose(1.0, "b", {"crouch": 0.4})])
    assert hold.channel("crouch", 0.99) == pytest.approx(0.1)
    snap = MotionClip("s", 1.0, [KeyPose(0, "a", {"crouch": 0.0}, "snap"), KeyPose(1.0, "b", {"crouch": 1.0})])
    assert snap.channel("crouch", 0.25) > 0.6  # fast start


def test_performance_tempo_intensity_mirror_emotion():
    c = get_clip("land_hard")
    base = c.sample(0.42)
    assert c.length(Performance(tempo=2.0)) == pytest.approx(c.length() / 2)
    assert c.sample(0.21, Performance(tempo=2.0))["crouch"] == pytest.approx(base["crouch"])
    big = c.sample(0.42, Performance(intensity=1.2))
    assert big["crouch"] - NEUTRAL["crouch"] == pytest.approx(1.2 * (base["crouch"] - NEUTRAL["crouch"]))
    m = c.sample(0.42, Performance(mirror=True))
    assert m["arm_n"] == pytest.approx(base["arm_f"]) and m["arm_f"] == pytest.approx(base["arm_n"])
    afraid = c.sample(0.42, Performance(emotion="afraid"))
    assert afraid["eye"] > base.get("eye", 1.0)
    assert set(EMOTIONS) >= {"neutral", "afraid", "determined", "relieved", "tired", "excited", "curious"}


def test_landing_performance_scales_with_impact_speed():
    n1, p1 = landing_clip(600)
    n2, p2 = landing_clip(1500)
    assert n1 == "land_medium" and n2 == "land_hard"
    assert get_clip(n2).length(p2) > get_clip(n1).length(p1)


def test_hard_landing_declares_hand_plant_and_hands_on_knees():
    c = get_clip("land_hard")
    eff = {(k.effector, k.on) for k in c.contacts}
    assert any(e == "hand_n" and on == "surface" for e, on in eff)
    assert any(on.startswith("joint:") for _, on in eff)
    names = [n for _, n in c.key_times()]
    assert names.index("impact") < names.index("absorb") < names.index("push_off") < names.index("rise")


# ---------------------------------------------------------------- contacts / joint collision
def test_knees_never_pass_through_the_landing_surface():
    from apex.motion.animator import KNEE_CLEARANCE
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(load("gravity_switch_1d.json"), "escape")
    r = rt.simulate()
    an = r.animators["axel"]
    rig = rt.rigs["axel"]
    worst = 1e9
    for seg in an.segments:
        if seg.kind != "landing":
            continue
        F = r.frames[seg.frame]
        for t in np.arange(seg.t0, seg.t1, 1 / 48):
            j = rig.world_joints(an.pose_at(float(t)))
            worst = min(worst, F.to_frame(j["knee_n"])[1], F.to_frame(j["knee_f"])[1])
    assert worst < 1e9
    assert worst >= KNEE_CLEARANCE - 1.0


# ---------------------------------------------------------------- composition rules
def test_composition_checks_run_and_pass_on_1d():
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    from apex.scene.runtime import SceneRuntime
    p = load("gravity_switch_1d.json")
    rt = SceneRuntime(p, "escape")
    rt.simulate()
    rep = Inspector(rt, build_camera(rt, 16 / 9), p.fps).run(check_determinism=False)
    by = {c.name: c for c in rep.checks}
    for n in ("composition_subject_size", "composition_required_objects"):
        assert by[n].status == "PASS", by[n]
    assert by["no_roll_during_fast_action"].status == "PASS"


def test_include_keeps_the_rail_in_frame_at_the_grab():
    from apex.render.pipeline import _resolve_target, build_camera
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(load("gravity_switch_1d.json"), "escape")
    rt.simulate()
    cam = build_camera(rt, 16 / 9)
    g = next(e for e in rt.result.events if e.type == "grab")
    c = cam.at(g.t)
    x, y = _resolve_target(rt.env, "bar:rail")
    half_h, half_w = c.view_h / 2, c.view_h * 16 / 9 / 2
    assert abs(x - c.cx) < half_w and abs(y - c.cy) < half_h


# ---------------------------------------------------------------- renderer adapter
def test_renderer_backend_registry():
    from apex.render.base import BACKENDS, Renderer, make_renderer
    from apex.scene.runtime import SceneRuntime
    p = load("gravity_switch_1b.json")
    rt = SceneRuntime(p, "switch_and_fall")
    rt.simulate()
    r = make_renderer("skia", 160, 90, rt.env, {c.id: c.style for c in p.characters}, rt.rigs)
    assert "skia" in BACKENDS and isinstance(r, Renderer)
    with pytest.raises(KeyError):
        make_renderer("nope", 1, 1)


def test_motion_trails_follow_fast_limbs():
    from apex.render.pipeline import motion_trails
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(load("gravity_switch_1d.json"), "escape")
    rt.simulate()
    t = next(e for e in rt.result.events if e.type == "impact").t - 0.05
    tr = motion_trails(rt.result, t)["axel"]
    assert len(tr) == 2 and all(0 < a < 1 for _, a in tr)


# ---------------------------------------------------------------- audio
def test_mix_is_stereo_and_impacts_are_panned():
    import tempfile
    from apex.audio.sound_director import SoundDirector
    from apex.motion.controller import Event
    ev = [Event(0.5, "impact", "a", {"normal_speed": 1400.0, "point": [-600.0, 0.0], "surface": "floor"}),
          Event(1.5, "impact", "a", {"normal_speed": 1400.0, "point": [600.0, 0.0], "surface": "floor"})]
    with tempfile.TemporaryDirectory() as d:
        path = f"{d}/a.wav"
        SoundDirector(7, music=False).render(ev, 2.5, path)
        with wave.open(path) as w:
            assert w.getnchannels() == 2
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2).astype(float)
    sr = 48000
    a = x[int(0.5 * sr):int(0.8 * sr)]
    b = x[int(1.5 * sr):int(1.8 * sr)]
    assert np.abs(a[:, 0]).sum() > np.abs(a[:, 1]).sum()  # left impact louder on the left
    assert np.abs(b[:, 1]).sum() > np.abs(b[:, 0]).sum()


# ---------------------------------------------------------------- review packet
def test_review_packet_separates_metrics_from_human_scores(tmp_path):
    from apex.qa.review import CRITERIA, aggregate_scores, build_review_packet
    p = load("gravity_switch_1d.json")
    qa = {"passed": True, "counts": {"total": 1, "by_status": {"PASS": 1}},
          "checks": [{"name": "foot_sliding[axel]", "status": "PASS", "metric": 1.2, "threshold": 1.5}]}
    qj = tmp_path / "qa.json"
    qj.write_text(json.dumps(qa))
    md = build_review_packet(p, "escape", str(tmp_path), video="x.mp4", qa_json=str(qj))
    text = open(md).read()
    assert "Objective technical metrics" in text and "Human review rubric" in text and "not a score" in text
    assert text.index("Objective") < text.index("Human review rubric")
    for key, _, _ in CRITERIA:
        assert f"`{key}`" in text
    sheet = json.loads((tmp_path / "review_scores.json").read_text())
    assert all(v is None for v in sheet["scores"].values())  # nothing pre-scored, by an AI or otherwise
    s1 = json.loads(json.dumps(sheet)); s1["scores"]["camera_clarity"] = 6
    s2 = json.loads(json.dumps(sheet)); s2["scores"]["camera_clarity"] = 8
    agg = aggregate_scores([s1, s2])
    assert agg["camera_clarity"]["mean"] == 7 and agg["camera_clarity"]["spread"] == 2 and agg["sound_quality"]["n"] == 0
    assert len(CRITERIA) == 7


# ---------------------------------------------------------------- Task 6: generalization scene
@pytest.fixture(scope="module")
def flip_rt():
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(load("foundry_flip.json"), "flip")
    rt.simulate()
    return rt


def test_generalization_story_runs_on_existing_actions(flip_rt):
    ev = [e.type for e in flip_rt.result.events]
    order = ["notice", "point", "slide_start", "slide_end", "takeoff", "press_contact", "gravity_shift", "lost_support",
             "door_open", "look_back", "exit_reached", "door_close"]
    idx = [ev.index(k) for k in order]
    assert idx == sorted(idx)
    hard = [e for e in flip_rt.result.events if e.type == "impact" and e.data["surface"] == "ceiling"]
    assert hard and hard[0].data["normal_speed"] > 1100  # plays the land_hard library clip
    rep = flip_rt.result.gravity.report()
    assert round(rep[1]["rel_prev_deg"]) == -180


def test_generalization_scene_passes_qa(flip_rt):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    p = flip_rt.project
    rep = Inspector(flip_rt, build_camera(flip_rt, 16 / 9), p.fps).run(check_determinism=False)
    assert rep.passed, rep.summary()


def test_stance_widths_scale_with_leg_length(flip_rt):
    """Landing plants were authored in absolute units for AXEL's legs; on a shorter rig they must scale."""
    an = flip_rt.result.animators["pip"]
    seg = next(s for s in an.segments if s.kind == "landing" and s.frame == "ceiling")
    a, b = seg.data["plants"]
    assert abs(a - b) <= 2 * 24.0 * (35 + 33) / 86.0 + 1e-6


def test_theme_defaults_reproduce_the_lab_and_override_per_environment():
    from apex.render.skia_renderer import hex_rgb
    from apex.scene.schema import ThemeSpec
    t = ThemeSpec()
    assert hex_rgb(t.accent) == (70, 236, 255) and hex_rgb(t.alert) == (255, 50, 62)
    env = load("foundry_flip.json").environments[0]
    assert env.theme.accent != t.accent
