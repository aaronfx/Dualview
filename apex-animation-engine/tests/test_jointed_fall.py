"""Opt-in articulated-ragdoll integration and isolation smoke checks."""
import json
import math
import os

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

from .conftest import ROOT


def test_jointed_rescue_samples_are_physical_and_deterministic():
    previous = {key: os.environ.get(key) for key in
                ("APEX_EXPERIMENTAL_ACTIVE_FALL", "APEX_EXPERIMENTAL_JOINTED_FALL")}
    os.environ["APEX_EXPERIMENTAL_ACTIVE_FALL"] = "1"
    os.environ["APEX_EXPERIMENTAL_JOINTED_FALL"] = "1"
    try:
        scene = json.loads((ROOT / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
        rt = SceneRuntime(ProjectSpec.model_validate(scene), "rescue")
        rt.simulate()
        ctl = rt.result.controllers["milo"]
        fall = next(seg for seg in ctl.segments if seg.kind == "fall")
        assert fall.data.get("jointed_fall") is True
        samples = fall.data["ragdoll_samples"]
        assert len(samples) > 20
        names = {"head", "upper_arm_n", "forearm_n", "upper_arm_f", "forearm_f",
                 "thigh_n", "shin_n", "thigh_f", "shin_f"}
        assert all(set(p["angles"]) == names for p in samples)
        assert all(math.isfinite(a) for p in samples for a in p["angles"].values())
        assert any(abs(samples[-1]["angles"][name] - samples[0]["angles"][name]) > 0.1
                   for name in names)
        for t in [fall.t0 + 0.16, fall.t0 + 0.4, min(fall.t1 - 0.02, fall.t0 + 0.72)]:
            pose = rt.result.animators["milo"].pose_at(t)
            assert all(math.isfinite(a) for a in pose.local.values())
        assert any(e.type == "body_fall" and e.character == "milo" for e in rt.result.events)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_legacy_fall_keeps_opt_in_off():
    before = os.environ.pop("APEX_EXPERIMENTAL_JOINTED_FALL", None)
    try:
        d = json.loads((ROOT / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
        rt = SceneRuntime(ProjectSpec.model_validate(d), "rescue")
        rt.simulate()
        fall = next(s for s in rt.result.controllers["milo"].segments if s.kind == "fall")
        assert not fall.data.get("jointed_fall")
    finally:
        if before is not None:
            os.environ["APEX_EXPERIMENTAL_JOINTED_FALL"] = before
