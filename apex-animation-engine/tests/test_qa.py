from apex.camera.director import CameraDirector
from apex.qa.inspector import Inspector
from apex.rig.stickman import Pose


def _camera(rt, aspect=16 / 9):
    an = rt.result.animators

    def bbox(cid, t):
        j = rt.rigs[cid].world_joints(an[cid].pose_at(t))
        xs, ys = [p[0] for p in j.values()], [p[1] for p in j.values()]
        return min(xs) - 12, min(ys) - 6, max(xs) + 12, max(ys) + 14

    def vel(cid, t):
        a, b = an[cid].pose_at(t - 0.05).root, an[cid].pose_at(t + 0.05).root
        return ((b[0] - a[0]) / 0.1, (b[1] - a[1]) / 0.1)

    return CameraDirector(rt.scene.shots, aspect, bbox, vel)


def test_both_milestone_scenes_pass_structural_qa(gravity_runtime, motion_runtime):
    for rt in (gravity_runtime, motion_runtime):
        rep = Inspector(rt, _camera(rt), 24).run(check_determinism=False)
        assert rep.passed, rep.summary()


def test_inspector_detects_teleport_and_foot_slide(gravity_runtime):
    an = gravity_runtime.result.animators["axel"]
    orig = an.pose_at

    def broken(t):
        p = orig(t)
        if 2.0 <= t < 2.05:  # inject a 300-unit jump for one frame
            p = p.copy()
            p.root = (p.root[0] + 300, p.root[1])
        return p

    an.pose_at = broken
    try:
        rep = Inspector(gravity_runtime, _camera(gravity_runtime), 24).run(check_determinism=False)
    finally:
        an.pose_at = orig
    failed = {c.name for c in rep.checks if c.status == "FAIL"}
    assert "no_teleport_root[axel]" in failed and "foot_sliding[axel]" in failed


def test_camera_keeps_subject_in_frame(gravity_runtime):
    cam = _camera(gravity_runtime)
    vis = [cam.subject_visible("axel", i / 24) for i in range(int(gravity_runtime.scene.duration * 24))]
    assert sum(vis) / len(vis) > 0.95
    assert all(cam.at(i / 24).valid() for i in range(0, 250, 7))
