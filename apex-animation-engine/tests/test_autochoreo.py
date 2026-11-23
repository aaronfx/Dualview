"""M3 bounded choreography acceptance: no fake physical success."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path

import pytest

from apex.scene.autochoreo import Objective, evaluate, propose, search
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


@pytest.fixture(scope="module")
def example():
    path = Path(__file__).resolve().parents[1] / "examples" / "build_impossible_crossing.py"
    spec = importlib.util.spec_from_file_location("apex_m3_impossible_crossing", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mission(example):
    project = ProjectSpec.model_validate(example.world())
    obj = Objective("cross", "iko", "barrier", "spark",
                    max_trial_seconds=19.0, max_jump_apex=210.0,
                    movable_prop_id="crate", prefer_prop_interaction=True)
    return project, obj


def test_tactics_are_generated_from_scene_geometry(mission):
    p, obj = mission
    c = propose(p, obj)
    names = [x.name for x in c]
    assert names == ["direct_run", "low_jump", "powered_jump", "vault",
                     "climb_then_drop", "shift_crate_then_climb"]
    for plan in c:
        assert plan.actions[0]["type"] == "notice"
        assert plan.actions[1]["clip"] == "doubt_to_dash"
        assert any(a["type"] == "pick_up" and a["target"] == "prop:spark" for a in plan.actions)
    assert next(x for x in c if x.name == "low_jump").check_jump_height <= obj.max_jump_apex


def test_invalid_objective_is_rejected_instead_of_hallucinated(mission):
    p, obj = mission
    with pytest.raises(ValueError, match="real obstacle"):
        propose(p, replace(obj, obstacle_id="imaginary_bridge"))
    with pytest.raises(ValueError, match="real obstacle"):
        propose(p, replace(obj, goal_prop_id="imaginary_gem"))
    with pytest.raises(ValueError, match="movable_prop_id"):
        propose(p, replace(obj, movable_prop_id="spark"))
    with pytest.raises(ValueError, match="downward gravity"):
        data = p.model_dump(mode="json")
        data["environments"][0]["gravity"] = [0, 1600]
        propose(ProjectSpec.model_validate(data), obj)


def test_impossible_jumps_rejected_by_geometry_preflight(mission):
    p, obj = mission
    candidates = propose(p, obj)
    low = next(c for c in candidates if c.name == "low_jump")
    verdict = evaluate(p, obj, low)
    assert not verdict.accepted
    assert verdict.score is None
    assert "geometry preflight rejected" in verdict.reason


@pytest.fixture(scope="module")
def solved(mission):
    p, obj = mission
    return search(p, obj)


def test_search_has_proven_solution_and_auditable_rejections(solved):
    assert solved.succeeded
    assert solved.chosen in {"climb_then_drop", "shift_crate_then_climb"}
    assert len(solved.trials) == 6
    assert any(not t.accepted for t in solved.trials)
    accepted = next(t for t in solved.trials if t.candidate == solved.chosen)
    assert accepted.accepted
    assert accepted.event_times["pick_up"] < 18.4
    if solved.chosen == "shift_crate_then_climb":
        assert accepted.prop_displacement is not None
        assert accepted.prop_displacement >= 12
    rep = solved.report()
    assert rep["chosen"] == solved.chosen
    assert rep["attempted"] == 6
    assert rep["succeeded"]
    assert "physics" in rep["validity"]


def test_final_assembled_scene_replays_selected_physics(example):
    project, report = example.build()
    assert project.scenes[0].duration <= 19
    assert len(project.scenes[0].shots) >= 5
    assert project.scenes[0].shots[0].start == 0
    assert project.scenes[0].shots[-1].end == project.scenes[0].duration
    for a, b in zip(project.scenes[0].shots, project.scenes[0].shots[1:]):
        assert a.end == b.start
    assert report.succeeded
    rt = SceneRuntime(project, "cross")
    sim = rt.simulate(physics_only=True)
    events = [(e.type, e.t, e.data) for e in sim.events if e.character == "iko"]
    assert any(k == "pick_up" and d.get("prop") == "spark" for k,t,d in events)
    assert any(k == "climbed" for k,t,d in events)
    assert any(k == "impact" for k,t,d in events)
