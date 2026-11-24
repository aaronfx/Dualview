import copy

import pytest
from pydantic import ValidationError

from apex.scene.schema import ProjectSpec


def test_examples_validate(motion_project, gravity_project):
    assert motion_project.scene("locomotion").duration == 8.5
    assert gravity_project.environment("chamber").switches[0].id == "gswitch"


def _bad(proj, mutate):
    d = proj.model_dump(mode="json")
    mutate(d)
    with pytest.raises(ValidationError):
        ProjectSpec.model_validate(d)


def test_rejects_unknown_switch_and_gapped_shots_and_bad_actions(gravity_project):
    _bad(gravity_project, lambda d: d["scenes"][0]["actions"][2].__setitem__("switch", "nope"))
    _bad(gravity_project, lambda d: d["scenes"][0]["shots"][1].__setitem__("start", 3.7))
    _bad(gravity_project, lambda d: d["scenes"][0]["actions"].append({"type": "walk_to", "character": "axel"}))
    _bad(gravity_project, lambda d: d.__setitem__("schema_version", "9.9"))
    _bad(gravity_project, lambda d: d["scenes"][0]["shots"][0]["camera"].__setitem__("target", "ghost"))
