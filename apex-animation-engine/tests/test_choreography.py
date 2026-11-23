"""M3 deterministic choreography selection tests."""
from apex.scene.choreography import Candidate, choose_with_simulation, propose
from apex.scene.schema import ActionSpec, EnvironmentSpec, ProjectSpec


def env(obstacles=None):
    return EnvironmentSpec.model_validate({
        "id": "route", "room": {"width": 1600, "height": 950, "entry_door": False},
        "gravity": [0, -1568], "obstacles": obstacles or [],
    })


def test_clear_ground_generates_fastest_first():
    cs = propose(env(), "iko", -400, 400)
    assert len(cs) == 3
    assert cs[0].name == "ground_560"
    assert all(len(c.actions) == 1 and c.actions[0].type == "run_to" for c in cs)


def test_impossible_tower_does_not_get_fake_clear_route():
    tower = {"id": "tower", "kind": "platform", "center": [0, 220], "size": [90, 440]}
    cs = propose(env([tower]), "iko", -450, 450)
    assert cs == ()


def test_route_proposals_are_repeatable_and_budgeted():
    a = propose(env(), "iko", -300, 300, max_candidates=2)
    b = propose(env(), "iko", -300, 300, max_candidates=2)
    assert a == b and len(a) == 2


def test_nonfinite_or_unbounded_search_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        propose(env(), "iko", float("nan"), 300)
    with pytest.raises(ValueError):
        propose(env(), "iko", -300, 300, max_candidates=999)


def minimal():
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "planner_test", "title": "Plan, test, retry",
        "fps": 24, "width": 640, "height": 360,
        "characters": [{"id": "iko", "name": "IKO"}],
        "environments": [{"id": "room", "room": {"width": 1200, "height": 900,
                                               "entry_door": False}, "gravity": [0, -1568]}],
        "scenes": [{
            "id": "try", "environment": "room", "duration": 5,
            "placements": [{"character": "iko", "x": -200, "facing": 1}],
            "actions": [{"type": "idle", "character": "iko", "duration": 1}],
            "shots": [{"id": "wide", "kind": "wide", "start": 0, "end": 5,
                       "camera": {"mode": "static", "center": [0, 200], "view_height": 600}}]
        }]
    })


def test_reject_missing_events_without_mutating_original():
    p = minimal()
    cs = propose(p.environments[0], "iko", -200, 200)
    result = choose_with_simulation(p, "try", "iko", cs, required_events=("takeoff",))
    assert not result.accepted
    assert len(result.attempts) == 3
    assert all("takeoff" in a.reason for a in result.attempts)
    assert p.scene("try").actions[0].type == "idle"


def test_verified_ground_route_when_no_jump_required():
    p = minimal()
    cs = propose(p.environments[0], "iko", -200, 200)
    result = choose_with_simulation(p, "try", "iko", cs, required_events=())
    assert result.accepted
    assert result.candidate.actions[0].type == "run_to"
    assert result.attempts[-1].accepted
