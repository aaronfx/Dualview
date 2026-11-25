"""Freeze the historical CORE RUN capabilities independently of authored goals.

No render or LLM is needed: actual native simulation events must prove the
retained story beats. This does not certify artistic quality or autonomy.
"""
import json
from pathlib import Path

import pytest

from apex.ai.capabilities import catalogue
from apex.scene.goals import matches
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "city": ("break@case", "vault@iko", "hurt@iko", "hand_offered@pell", "exit_reached@iko"),
    "tower": ("climbed@iko", "knockdown@iko", "hand_offered@pell", "point@pell", "exit_reached@iko"),
    "canyon": ("collapse@bridge", "orb_jump@iko", "throw_start@pell", "creature_break@drone", "exit_reached@iko"),
    "arena": ("knockdown@iko", "disarm@vex", "stood_up@iko", "knockdown@vex", "pick_up@iko[prop=core]", "exit_reached@pell"),
    "summit": ("place@iko", "gesture_start@iko", "fist_bump@iko"),
}


@pytest.fixture(scope="module")
def core_run():
    return ProjectSpec.model_validate_json((ROOT / "examples/core_run.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("scene_id", list(REQUIRED))
def test_core_run_retains_actual_story_events(core_run, scene_id):
    result = SceneRuntime(core_run, scene_id).simulate(physics_only=True)
    assert not [c.violation for c in result.controllers.values() if c.violation]
    assert not [e for e in result.events if e.type == "action_impossible"]
    assert not [goal for goal in REQUIRED[scene_id]
                if not any(matches(goal, e) and e.t <= result.duration for e in result.events)]


@pytest.mark.parametrize("filename", ["core_run.json", "last_retry.json", "the_rescue.json"])
def test_existing_films_native_primitives_remain_discoverable(filename):
    project = ProjectSpec.model_validate_json((ROOT / "examples" / filename).read_text(encoding="utf-8"))
    catalog = catalogue()
    actions = {entry["name"] for entry in catalog["actions"]}
    clips = set(catalog["motion_clips"])
    for scene in project.scenes:
        assert {a.type for a in scene.actions} <= actions
        assert {a.clip for a in scene.actions if a.clip is not None} <= clips
