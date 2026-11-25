"""D10.5 independent story verification — the requested story is checked against actual native simulation events,
independently of the animation plan. A technically valid film that tells the wrong story is rejected (reproduces
Failure 5). Offline requests for unsupported archetypes produce a clear limitation, not a silent substitution."""
import json
import os

import pytest

from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.ai.story_check import verify_brief, requirements_for, offline_support, detect_archetype

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESCUE_BRIEF = "Make a two-character rescue: one is trapped under a heavy object and the other frees them with a lever."


def _sim(project):
    p = ProjectSpec.model_validate(project)
    return p, SceneRuntime(p, p.scenes[0].id).simulate().events


def test_real_rescue_film_passes_every_required_beat():
    with open(os.path.join(HERE, "examples", "the_rescue.json")) as f:
        p, events = _sim(json.load(f))
    rep = verify_brief(RESCUE_BRIEF, p, events)
    assert rep["archetype"] == "rescue" and rep["story_pass"] is True
    assert {r["id"] for r in rep["requirements"] if r["met"]} == {
        "two_characters", "trapped", "discovery", "failed_lift", "lever", "release", "recovery", "friendship"}


def test_f5_single_character_switch_scene_fails_the_rescue_story():
    # A technically valid single-character "press a switch" scene must NOT be accepted as a two-character rescue.
    switch_scene = {
        "schema_version": "0.1", "id": "f5", "title": "wrong", "fps": 24, "width": 1280, "height": 720, "seed": 1,
        "characters": [{"id": "iko", "name": "IKO"}],
        "environments": [{"id": "e", "room": {"width": 1600, "height": 800, "entry_door": False}, "props": [],
                          "obstacles": [], "exits": []}],
        "scenes": [{"id": "f5", "environment": "e", "duration": 6.0,
                    "placements": [{"character": "iko", "x": -200, "facing": 1}],
                    "actions": [{"character": "iko", "type": "walk_to", "target_x": 150},
                                {"character": "iko", "type": "idle", "duration": 1.0}],
                    "goals": [], "shots": [{"id": "s", "start": 0, "end": 6.0,
                                            "camera": {"mode": "follow", "target": "iko", "view_height": 600}}]}],
    }
    p, events = _sim(switch_scene)
    rep = verify_brief(RESCUE_BRIEF, p, events)
    assert rep["story_pass"] is False                         # rejected despite being a valid, renderable scene
    met = {r["id"] for r in rep["requirements"] if r["met"]}
    assert "two_characters" not in met and "trapped" not in met and "release" not in met


def test_unsupported_offline_brief_reports_a_clear_limitation():
    assert detect_archetype("a serene documentary about clouds") is None
    msg = offline_support("a serene documentary about clouds")
    assert msg and "Supported offline archetypes" in msg
    rep = verify_brief("a serene documentary about clouds", ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "x", "title": "x", "fps": 24, "width": 320, "height": 180, "seed": 1,
        "characters": [{"id": "iko", "name": "IKO"}],
        "environments": [{"id": "e", "room": {"width": 800, "height": 400, "entry_door": False}, "props": [],
                          "obstacles": [], "exits": []}],
        "scenes": [{"id": "x", "environment": "e", "duration": 3.0, "placements": [{"character": "iko", "x": 0}],
                    "actions": [], "goals": [], "shots": [{"id": "s", "start": 0, "end": 3.0,
                                                           "camera": {"mode": "static", "center": [0, 0]}}]}]}), [])
    assert rep["story_pass"] is None                          # no silent substitution; flagged as unverifiable


def test_rescue_requires_correct_event_order():
    # friendship before the release must not count as a satisfied rescue (ordered requirement)
    arch, reqs = requirements_for(RESCUE_BRIEF)
    from types import SimpleNamespace as E
    scrambled = [E(t=1.0, type="fist_bump", character="pell", data={}),
                 E(t=2.0, type="pinned", character="iko", data={}),
                 E(t=3.0, type="notice", character="pell", data={}),
                 E(t=4.0, type="lift_fail", character="pell", data={}),
                 E(t=5.0, type="lever_engage", character="pell", data={}),
                 E(t=6.0, type="freed", character="iko", data={}),
                 E(t=7.0, type="stood_up", character="iko", data={})]
    from apex.ai.story_check import verify
    rep = verify(reqs, _dummy_two_char(), scrambled)
    friendship = next(r for r in rep["requirements"] if r["id"] == "friendship")
    assert friendship["met"] is False                        # fist_bump happened before recovery -> not a valid payoff


def _dummy_two_char():
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "d", "title": "d", "fps": 24, "width": 320, "height": 180, "seed": 1,
        "characters": [{"id": "iko", "name": "IKO"}, {"id": "pell", "name": "PELL"}],
        "environments": [{"id": "e", "room": {"width": 800, "height": 400, "entry_door": False}, "props": [],
                          "obstacles": [], "exits": []}],
        "scenes": [{"id": "d", "environment": "e", "duration": 3.0,
                    "placements": [{"character": "iko", "x": -50}, {"character": "pell", "x": 50}],
                    "actions": [], "goals": [], "shots": [{"id": "s", "start": 0, "end": 3.0,
                                                           "camera": {"mode": "static", "center": [0, 0]}}]}]})
