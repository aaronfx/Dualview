import math
import random

from apex.scene.runtime import SceneRuntime


def test_gravity_switch_causal_event_order(gravity_runtime):
    ev = gravity_runtime.result.events
    first = {}
    for e in ev:
        first.setdefault(e.type, e)
    order = ["press_contact", "switch_activated", "gravity_shift", "lost_support", "brace", "impact", "recovered"]
    times = [first[k].t for k in order]
    assert times == sorted(times)
    assert first["impact"].data["surface"] == "wall_right"
    tr = gravity_runtime.result.gravity.transitions[0]
    assert tr.cause == "gswitch"


def test_ends_standing_on_the_wall(gravity_runtime):
    ctrl = gravity_runtime.result.controllers["axel"]
    last = ctrl.segments[-1]
    assert last.kind == "idle" and last.frame == "wall_right"
    pose = gravity_runtime.evaluate(gravity_runtime.scene.duration - 0.01).poses["axel"]
    assert abs(math.degrees(pose.body_angle) - 90) < 1.0  # upright relative to the wall (head toward room centre)


def test_arbitrary_timestamp_evaluation_is_finite(gravity_runtime):
    rnd = random.Random(5)
    rig = gravity_runtime.rigs["axel"]
    for _ in range(200):
        t = rnd.uniform(-0.5, gravity_runtime.scene.duration + 0.5)
        j = rig.world_joints(gravity_runtime.evaluate(t).poses["axel"])
        assert all(math.isfinite(x) and math.isfinite(y) for x, y in j.values())


def test_deterministic_replay(gravity_project):
    ts = [i * 0.37 for i in range(28)]
    a = SceneRuntime(gravity_project, "switch_and_fall")
    a.simulate()
    b = SceneRuntime(gravity_project, "switch_and_fall")
    b.simulate()
    assert a.state_hash(ts) == b.state_hash(ts)


def test_motion_scene_jump_is_ballistic_and_lands(motion_runtime):
    ev = [e.type for e in motion_runtime.result.events]
    assert "takeoff" in ev and "impact" in ev
    assert sum(1 for e in motion_runtime.result.events if e.type == "footstep") >= 8
