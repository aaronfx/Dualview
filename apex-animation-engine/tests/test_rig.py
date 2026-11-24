import math
import random

import pytest

from apex.rig.ik import solve_two_bone
from apex.rig.skeleton import Bone, Skeleton
from apex.rig.stickman import PI, Pose, StickmanRig, base_pose, blend_poses


def test_hierarchy_must_be_ordered_and_unique():
    with pytest.raises(ValueError):
        Skeleton([Bone("child", "root", 10, 0), Bone("root", None, 10, 0)])
    with pytest.raises(ValueError):
        Skeleton([Bone("a", None, 10, 0), Bone("a", None, 10, 0)])


def test_stickman_joint_hierarchy():
    rig = StickmanRig()
    sk = rig.skeleton
    assert sk["shin_n"].parent == "thigh_n" and sk["thigh_n"].parent is None
    assert sk["forearm_f"].parent == "upper_arm_f" and sk["upper_arm_f"].parent == "chest"
    assert set(sk.children("chest")) == {"neck", "upper_arm_n", "upper_arm_f"}


def test_fk_preserves_bone_lengths_for_arbitrary_angles():
    rig = StickmanRig()
    rnd = random.Random(1)
    for _ in range(50):
        local = {b.name: rnd.uniform(-PI, PI) for b in rig.skeleton.bones}
        fk = rig.skeleton.fk_character(local)
        for b in rig.skeleton.bones:
            s, e, _ = fk[b.name]
            assert abs(math.dist(s, e) - b.length) < 1e-9


def test_two_bone_ik_reaches_reachable_targets():
    rnd = random.Random(2)
    for _ in range(200):
        ang, d = rnd.uniform(-PI, PI), rnd.uniform(5, 85)
        tgt = (math.cos(ang) * d, math.sin(ang) * d)
        sol = solve_two_bone((0, 0), tgt, 44, 42, bend=1)
        assert sol.reached and sol.distance_error < 1e-6


def test_two_bone_ik_unreachable_is_straight_and_stretch_is_capped():
    sol = solve_two_bone((0, 0), (200, 0), 44, 42, bend=1, max_stretch=1.1)
    assert not sol.reached and abs(sol.a1 - sol.a2) < 0.05 and sol.stretch == pytest.approx(1.1)


@pytest.mark.parametrize("facing,body", [(1, 0.0), (-1, 0.0), (1, PI / 2), (-1, -1.1)])
def test_leg_ik_places_ankle_in_world(facing, body):
    rig = StickmanRig()
    pose = Pose(root=(100.0, 200.0), body_angle=body, facing=facing, local=base_pose())
    from apex.core.mathx import v_add, v_rot
    target = v_add((100.0, 200.0), v_rot((15.0 * facing, -80.0), body))
    rig.leg_ik(pose, "n", target)
    assert math.dist(rig.world_joints(pose)["ankle_n"], target) < 1e-6


def test_pose_blend_is_angle_aware_and_exact_at_ends():
    a = Pose(local={"spine": math.radians(170)})
    b = Pose(local={"spine": math.radians(-170)})
    assert blend_poses(a, b, 0.0).local["spine"] == pytest.approx(a.local["spine"])
    mid = blend_poses(a, b, 0.5).local["spine"]
    assert abs(abs(math.atan2(math.sin(mid), math.cos(mid))) - PI) < 1e-9
