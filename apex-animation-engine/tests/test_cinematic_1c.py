"""Milestone 1C: character acting, secondary motion, cinematic camera and review tooling."""
import json
import math
import subprocess

import numpy as np
import pytest

from apex.camera.director import SAFE, CameraDirector, gravity_roll
from apex.scene.schema import ProjectSpec
from apex.scene.targets import exit_world, resolve

from .conftest import ROOT, load


@pytest.fixture(scope="session")
def cine_project():
    return load("gravity_switch_1c.json")


@pytest.fixture(scope="session")
def cine_runtime(cine_project):
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(cine_project, "switch_sequence")
    rt.simulate()
    return rt


@pytest.fixture(scope="session")
def cine_camera(cine_runtime, cine_project):
    from apex.render.pipeline import build_camera
    return build_camera(cine_runtime, cine_project.width / cine_project.height)


@pytest.fixture(scope="session")
def cine_report(cine_runtime, cine_camera, cine_project):
    from apex.qa.inspector import Inspector
    return Inspector(cine_runtime, cine_camera, cine_project.fps).run(check_determinism=False)


def _first(events, kind, after=0.0):
    return next(e for e in events if e.type == kind and e.t >= after)


# ---------------------------------------------------------------- schema / targets
def test_targets_and_exits_resolve(cine_project):
    env = cine_project.environment(cine_project.scenes[0].environment)
    assert resolve(env, "switch:gswitch") == (env.switches[0].x, env.switches[0].height)
    assert exit_world(env, "door1") == (env.room.width / 2, 900.0)
    assert resolve(env, "point:10,20") == (10.0, 20.0)
    assert resolve(env, None) is None


def test_unknown_target_reference_is_rejected():
    data = json.loads((ROOT / "examples" / "gravity_switch_1c.json").read_text())
    acts = data["scenes"][0]["actions"]
    next(a for a in acts if a.get("target", "").startswith("exit:"))["target"] = "exit:nope"
    with pytest.raises(Exception):
        ProjectSpec.model_validate(data)


# ---------------------------------------------------------------- story beats
def test_story_beats_happen_in_order(cine_runtime):
    ev = cine_runtime.result.events
    order = [_first(ev, "notice"), _first(ev, "press_contact"), _first(ev, "gravity_shift"), _first(ev, "lost_support"),
             _first(ev, "impact"), _first(ev, "recovered")]
    ts = [e.t for e in order]
    assert ts == sorted(ts), ts
    second_notice = _first(ev, "notice", after=order[-1].t)
    point = _first(ev, "point", after=second_notice.t)
    assert point.t > second_notice.t
    assert order[4].data.get("surface", order[4].data.get("collider", "wall_right")).startswith("wall")


def test_hand_touches_switch_at_contact(cine_runtime):
    res = cine_runtime.result
    e = _first(res.events, "press_contact")
    sw = cine_runtime.env.switches[0]
    pose = res.animators["axel"].pose_at(e.t)
    j = cine_runtime.rigs["axel"].world_joints(pose)
    d = min(math.dist(j["hand_n"], (sw.x, sw.height)), math.dist(j["hand_f"], (sw.x, sw.height)))
    assert d < 22.0, d


def test_hesitant_press_contact_is_delayed(cine_runtime):
    from apex.motion.controller import PRESS_CONTACT_T, PRESS_H_CONTACT_T
    an = cine_runtime.result.animators["axel"]
    e = _first(cine_runtime.result.events, "press_contact")
    seg = an.segments[an.segment_at(e.t)]
    assert seg.kind == "press"
    assert abs((e.t - seg.t0) - PRESS_H_CONTACT_T) < 0.02
    assert PRESS_H_CONTACT_T > PRESS_CONTACT_T + 0.5  # hesitation actually lengthens the beat


def test_notice_double_take_widens_eyes(cine_runtime):
    from apex.motion.controller import NOTICE_DOUBLE_TAKE
    an = cine_runtime.result.animators["axel"]
    e = _first(cine_runtime.result.events, "notice")
    before = an.pose_at(e.t - NOTICE_DOUBLE_TAKE + 0.05)
    after = an.pose_at(e.t + 0.1)
    assert after.eye > before.eye + 0.3


def test_gaze_points_head_at_target(cine_runtime):
    """After the double take the head looks toward the switch (screen side of the target)."""
    an = cine_runtime.result.animators["axel"]
    rig = cine_runtime.rigs["axel"]
    e = _first(cine_runtime.result.events, "notice")
    pose = an.pose_at(e.t + 0.2)
    c, _up, fwd = rig.head_frame(pose)
    sw = cine_runtime.env.switches[0]
    to = (sw.x - c[0], sw.height - c[1])
    assert fwd[0] * to[0] + fwd[1] * to[1] > 0


def test_point_hand_extends_toward_exit(cine_runtime):
    res = cine_runtime.result
    e = _first(res.events, "point")
    pose = res.animators["axel"].pose_at(e.t + 0.3)
    j = cine_runtime.rigs["axel"].world_joints(pose)
    door = exit_world(cine_runtime.env, "door1")
    reach = max(math.dist(j[f"hand_{s}"], j[f"shoulder_{s}"]) for s in "nf")
    assert reach > 30
    # the more extended hand is the one closer to the door than the shoulder is
    s = max("nf", key=lambda s: math.dist(j[f"hand_{s}"], j[f"shoulder_{s}"]))
    assert math.dist(j[f"hand_{s}"], door) < math.dist(j[f"shoulder_{s}"], door)


def test_torso_twist_offsets_shoulders():
    from apex.rig.stickman import Pose, StickmanRig, blend_poses
    rig = StickmanRig()
    a, b = Pose(), Pose(twist=1.0)
    off = rig.offsets(b)
    assert off["upper_arm_n"][0] > 0 > off["upper_arm_f"][0]
    assert abs(blend_poses(a, b, 0.5).twist - 0.5) < 1e-9
    jn = rig.world_joints(b)
    assert jn["shoulder_n"] != jn["shoulder_f"]


# ---------------------------------------------------------------- secondary motion
def test_scarf_integrity(cine_runtime):
    sc = cine_runtime.result.scarves["axel"]
    assert sc.max_stretch() < 1.35
    assert sc.anchor_err < 0.5
    hw, rh = cine_runtime.env.room.width / 2, cine_runtime.env.room.height
    for t in np.linspace(0, cine_runtime.result.duration - 1e-3, 40):
        for tail in sc.at(float(t)):
            assert np.all(np.isfinite(tail))
            assert tail[:, 0].min() >= -hw - 1e-6 and tail[:, 0].max() <= hw + 1e-6
            assert tail[:, 1].min() >= -1e-6 and tail[:, 1].max() <= rh + 1e-6


def test_scarf_hangs_toward_gravity(cine_runtime):
    """At rest the tails trail along the gravity vector, before and after the switch."""
    sc = cine_runtime.result.scarves["axel"]
    res = cine_runtime.result
    for t in (1.7, res.duration - 0.3):
        g = res.gravity.at(t)
        tail = sc.at(t)[0]
        d = tail[-1] - tail[0]
        assert (d[0] * g[0] + d[1] * g[1]) / (np.hypot(*d) + 1e-9) > 0.2, (t, d, g)


def test_dust_stays_in_room_and_reacts(cine_runtime):
    dust = cine_runtime.result.dust
    hw, rh = cine_runtime.env.room.width / 2, cine_runtime.env.room.height
    for t in (0.0, 5.0, 9.4, 13.0):
        p = dust.at(t)
        assert np.all(np.isfinite(p))
        assert p[:, 0].min() >= -hw - 1 and p[:, 0].max() <= hw + 1
        assert p[:, 1].min() >= -1 and p[:, 1].max() <= rh + 1
    assert not np.allclose(dust.at(8.0), dust.at(9.0))


# ---------------------------------------------------------------- camera
def test_gravity_roll_values():
    assert abs(gravity_roll((0.0, -1.0))) < 1e-9
    assert abs(gravity_roll((1.0, 0.0)) - 90.0) < 1e-9
    assert abs(gravity_roll((-1.0, 0.0)) + 90.0) < 1e-9


@pytest.mark.parametrize("roll", [0.0, 17.0, 45.0, 63.0, 90.0, -120.0])
def test_frame_guard_is_exact_under_roll(roll):
    """The guard must place the subject inside the *rolled* safe area for any roll angle."""
    box = (300.0, 50.0, 360.0, 230.0)
    cam = CameraDirector([], 16 / 9, bbox=lambda c, t: box, velocity=lambda c, t: (0.0, 0.0))
    cx, cy, vh = cam._frame_guard("x", 0.0, -400.0, 600.0, 200.0, roll)
    r = math.radians(roll)
    A, B = vh * 16 / 9 / 2 * SAFE, vh / 2 * SAFE
    for (x, y) in ((box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])):
        dx, dy = x - cx, -(y - cy)
        sx, sy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
        assert abs(sx) <= A + 1e-6 and abs(sy) <= B + 1e-6


def test_frame_guard_leaves_framed_subject_alone():
    box = (-20.0, 0.0, 20.0, 150.0)
    cam = CameraDirector([], 16 / 9, bbox=lambda c, t: box, velocity=lambda c, t: (0.0, 0.0))
    assert cam._frame_guard("x", 0.0, 0.0, 75.0, 400.0, 30.0) == (0.0, 75.0, 400.0)


def test_cinematic_camera_rolls_to_gravity(cine_camera, cine_runtime):
    s6 = next(s for s in cine_camera.shots if s.id == "s6_recover")
    start, end = cine_camera.at(s6.start + 1e-3), cine_camera.at(s6.end - 1e-3)
    assert abs(start.roll) < 5.0  # the turn starts from the authored roll so the viewer sees it
    assert abs(end.roll - gravity_roll(cine_runtime.result.gravity.at(s6.end))) < 3.0


def test_insert_shot_frames_switch(cine_camera, cine_runtime):
    sw = cine_runtime.env.switches[0]
    s4 = next(s for s in cine_camera.shots if s.id == "s4_insert")
    assert s4.kind == "insert"
    region = (sw.x - 15, sw.height - 15, sw.x + 15, sw.height + 15)
    for t in np.linspace(s4.start, s4.end - 1e-3, 12):
        assert cine_camera.subject_visible("axel", float(t), region)


def test_inspector_passes_1c(cine_report):
    assert cine_report.passed, cine_report.summary()
    by = {c.name: c for c in cine_report.checks}
    for name in ("subject_in_frame", "camera_roll_rate", "gravity_indicator_matches_physics", "screen_direction_across_cuts",
                 "static_layout", "min_shot_length", "scarf_integrity[axel]", "dust_inside_room"):
        assert name in by, name
        assert by[name].status == "PASS", by[name]
    assert by["subject_in_frame"].metric >= 0.99


# ---------------------------------------------------------------- review tooling
@pytest.fixture(scope="session")
def tiny_video(tmp_path_factory):
    from apex.render.video import ffmpeg_bin
    p = tmp_path_factory.mktemp("media") / "tiny.mp4"
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24:duration=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(p)], check=True)
    return str(p)


def test_decode_check(tiny_video, tmp_path):
    from apex.qa.media import decode_check
    r = decode_check(tiny_video)
    assert r["ok"] and r["video_frames_decoded"] == 24
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(open(tiny_video, "rb").read()[:2000])
    assert not decode_check(str(bad))["ok"]


def test_contact_sheet(tiny_video, tmp_path):
    from apex.qa.media import contact_sheet
    out = contact_sheet(tiny_video, str(tmp_path / "sheet.png"), [0.0, 0.5, 0.9], ["a", "b", "c"], cols=2, thumb_w=160, title="t")
    import skia
    img = skia.Image.open(out)
    assert img.width() == 2 * (160 + 6) + 6 and img.height() > 2 * 90


def test_diagnostics_and_chart(gravity_runtime, tmp_path):
    from apex.qa.media import diagnostics_chart
    from apex.render.pipeline import build_camera, compute_diagnostics
    cam = build_camera(gravity_runtime, 16 / 9)
    diag = compute_diagnostics(gravity_runtime, cam, 24)
    assert len(diag) == int(round(gravity_runtime.result.duration * 24))
    keys = {"t", "shot", "state", "speed", "height", "tilt", "gravity_deg", "gravity_state", "planted_n", "planted_f", "roll"}
    assert keys <= set(diag[0])
    assert {d["gravity_state"] for d in diag} >= {"G0", "G1"}
    shots = [(s.id, s.start, s.end) for s in cam.shots]
    out = diagnostics_chart(diag, str(tmp_path / "diag.png"), shots, "1B")
    import os
    assert os.path.getsize(out) > 1000


def test_new_sound_bindings_render(tmp_path):
    from apex.audio.sound_director import DEFAULT_BINDINGS, SoundDirector
    from apex.motion.controller import Event
    assert DEFAULT_BINDINGS["notice"] and DEFAULT_BINDINGS["point"] and DEFAULT_BINDINGS["switch_activated"]
    ev = [Event(0.2, "notice", "axel"), Event(0.6, "switch_activated", "axel"), Event(1.0, "gravity_shift", "axel"),
          Event(1.4, "point", "axel")]
    cues = SoundDirector(3).render(ev, 2.0, str(tmp_path / "a.wav"))
    assert {c.sound for c in cues} >= {"notice", "startle", "chime"}
