"""First-stage active-body fall tests.

This is a physically simulated torso *prototype*, not a fully articulated
limb ragdoll. All tests are local and do not call OpenRouter.
"""
import json
import math

import pytest

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

from .conftest import ROOT


@pytest.fixture(scope="module")
def dynamic_rescue():
    import os
    prior = os.environ.get("APEX_EXPERIMENTAL_ACTIVE_FALL")
    os.environ["APEX_EXPERIMENTAL_ACTIVE_FALL"] = "1"
    try:
        data = json.loads((ROOT / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
        rt = SceneRuntime(ProjectSpec.model_validate(data), "rescue")
        rt.simulate()
        return rt
    finally:
        if prior is None:
            os.environ.pop("APEX_EXPERIMENTAL_ACTIVE_FALL", None)
        else:
            os.environ["APEX_EXPERIMENTAL_ACTIVE_FALL"] = prior


def test_fall_uses_dynamic_mode_and_contact_records(dynamic_rescue):
    rt = dynamic_rescue
    ctl = rt.result.controllers["milo"]
    fall = next(s for s in ctl.segments if s.kind == "fall")
    assert fall.data.get("active_fall") is True
    impact = next(e for e in rt.result.events if e.type == "body_fall" and e.character == "milo")
    assert impact.data.get("simulated") is True
    assert impact.data.get("floor_contact") is True, "fall must reach a physical floor contact"
    assert impact.data.get("fallback_settle") is False, "no scripted pose-snap fallback permitted"
    assert fall.t0 < impact.t < 5.1
    records = [r for r in ctl.records if fall.t0 <= r.t <= fall.t1]
    assert len(records) > 20
    assert all(math.isfinite(r.pos[0]) and math.isfinite(r.pos[1]) and math.isfinite(r.angle)
               for r in records)
    assert abs(records[0].angle - records[-1].angle) > 0.5


def test_rescue_cause_and_effect_survives_dynamic_fall(dynamic_rescue):
    events = dynamic_rescue.result.events
    def at(name, who):
        return next(e.t for e in events if e.type == name and e.character == who)
    assert at("push_lost", "milo") < at("body_fall", "milo") < at("pinned", "milo")
    assert at("pinned", "milo") < at("lift_fail", "juno") < at("freed", "milo")
