"""Performance-only regression tests for The Rescue's push and stumble.

The physical event sequence stays controlled by APEX simulation. These tests
check that the updated rig poses clearly convey effort and protective landing;
human review is still required for artistic quality.
"""
import math

import pytest

from apex.motion.interaction_anim import STANCE
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime

from .conftest import ROOT


@pytest.fixture(scope="module")
def rescue():
    import json
    data = json.loads((ROOT / "examples" / "the_rescue.json").read_text())
    runtime = SceneRuntime(ProjectSpec.model_validate(data), "rescue")
    runtime.simulate()
    return runtime


def _segment(anim, kind):
    return next(seg for seg in anim.segments if seg.kind == kind)


def test_push_uses_braced_stance_and_progressive_weight_transfer(rescue):
    milo = rescue.result.animators["milo"]
    push = _segment(milo, "push")
    assert STANCE["push"][0] - STANCE["push"][1] >= 50.0
    early = milo._eval_push(push, push.t0 + 0.09)
    loaded = milo._eval_push(push, min(push.t0 + 1.0, push.t1 - 0.02))
    assert loaded.root[1] < early.root[1] - 12.0
    assert loaded.eye < early.eye
    assert abs(loaded.twist) > abs(early.twist) + 0.08


def test_stumble_has_distinct_flail_then_bracing_pose(rescue):
    milo = rescue.result.animators["milo"]
    fall = _segment(milo, "fall")
    early = milo._eval_fall(fall, fall.t0 + 0.16 * (fall.t1 - fall.t0))
    late = milo._eval_fall(fall, fall.t0 + 0.84 * (fall.t1 - fall.t0))
    assert early.eye > 1.2
    assert abs(early.local["upper_arm_n"] - early.local["upper_arm_f"]) > 0.2
    assert late.hands["n"] == "open"
    assert late.hands["f"] == "open"


def test_action_sequence_remains_physically_causal_and_pose_finite(rescue):
    milo = rescue.result.animators["milo"]
    events = [e for e in rescue.result.events if e.character == "milo"]
    kinds = [e.type for e in events]
    assert kinds.index("push_start") < kinds.index("push_lost") < kinds.index("body_fall")
    rig = rescue.rigs["milo"]
    for segment in (_segment(milo, "push"), _segment(milo, "fall")):
        for frac in (0.04, 0.25, 0.5, 0.75, 0.96):
            t = segment.t0 + frac * (segment.t1 - segment.t0)
            pose = milo.pose_at(t)
            for p in rig.world_joints(pose).values():
                assert math.isfinite(p[0]) and math.isfinite(p[1])
