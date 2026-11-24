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
        assert plan.actions[0]["type"] == "run_to"
        assert plan.actions[0]["notice_while_moving"] is True
        assert plan.actions[0]["clip"] == "doubt_to_dash"
        assert plan.actions[0]["target"].startswith("point:")
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


def test_active_pace_is_an_explicit_director_contract_not_global_physics(mission):
    from apex.scene.pacing import actor_pace
    from dataclasses import replace
    p, obj = mission
    active = actor_pace("active")
    measured = actor_pace("measured")
    assert active.notice_seconds < measured.notice_seconds
    assert active.decision_seconds < 0.75
    assert active.recovery_seconds < 0.80
    assert active.final_tail <= 1.7
    assert active.travel_speed > measured.travel_speed
    fast = propose(p, obj)
    slow = propose(p, replace(obj, pacing="measured"))
    assert fast[0].actions[0]["notice_while_moving"] is True
    assert fast[0].actions[0]["clip"] == "doubt_to_dash"
    assert fast[0].actions[0]["tempo"] == active.decision_tempo
    assert slow[0].actions[0]["type"] == "notice"
    assert slow[0].actions[1]["type"] == "act"
    assert fast[0].actions[0]["tempo"] > slow[0].actions[1].get("tempo", 1)
    climber = next(c for c in fast if c.name == "climb_then_drop")
    assert next(a for a in climber.actions if a["type"] == "run_to")["speed"] >= active.travel_speed
    assert next(a for a in climber.actions if a.get("clip") == "land_and_dash")["tempo"] == active.recovery_tempo
    assert not any(a["type"] == "act" and a.get("clip") == "impact_to_grin" for a in climber.actions)
    assert climber.actions[-1]["type"] == "idle"
    assert climber.actions[-1]["duration"] <= 0.25


def test_short_notice_emits_event_before_next_action(example):
    d = example.world(duration=3)
    sc = d["scenes"][0]
    sc["actions"] = [
        {"type": "notice", "character": "iko", "target": "point:0,200", "duration": 0.28},
        {"type": "act", "character": "iko", "clip": "doubt_to_dash", "tempo": 1.72},
        {"type": "idle", "character": "iko", "duration": 0.2},
    ]
    sc["shots"][0]["end"] = 3
    sim = SceneRuntime(ProjectSpec.model_validate(d), "cross").simulate(physics_only=True)
    notice = next(e for e in sim.events if e.type == "notice" and e.character == "iko")
    acting = next(e for e in sim.events if e.type == "act" and e.character == "iko")
    assert 0 < notice.t < acting.t <= 0.30


def test_active_impact_recovers_into_movement_without_stationary_act(example):
    """An active actor keeps actual impact but runs toward the next goal."""
    film, _ = example.build()
    assert film.scenes[0].duration < 10.1
    sim = SceneRuntime(film, "cross").simulate(physics_only=True)
    events = [e for e in sim.events if e.character == "iko"]
    impact = next(e for e in events if e.type == "impact")
    acting = next(e for e in events if e.type == "act"
                  and e.data.get("clip") == "land_and_dash")
    pickup = next(e for e in events if e.type == "pick_up"
                  and e.data.get("prop") == "spark")
    assert impact.t <= acting.t < pickup.t
    assert acting.t - impact.t < 0.2
    assert pickup.t - impact.t < 3.0
    ctrl = sim.controllers["iko"]
    between = [s for s in ctrl.segments if s.kind == "idle"
               and s.t0 >= impact.t - 0.01 and s.t0 < pickup.t]
    assert sum(max(0.0, min(s.t1, pickup.t) - s.t0) for s in between) < 0.3


def test_moving_observation_proves_foot_travel_and_actor_cues(example):
    from apex.scene.autochoreo import Objective, propose
    p = ProjectSpec.model_validate(example.world())
    obj = Objective("cross", "iko", "barrier", "spark", pacing="active")
    run = propose(p, obj)[0].actions[0]
    d = p.model_dump(mode="json")
    sc = d["scenes"][0]
    sc["actions"] = [dict(run), {"type": "idle", "character": "iko", "duration": 0.2}]
    sim = SceneRuntime(ProjectSpec.model_validate(d), "cross").simulate(physics_only=True)
    ctrl = sim.controllers["iko"]
    notice = next(e for e in sim.events if e.type == "notice" and e.character == "iko")
    acting = next(e for e in sim.events if e.type == "act" and e.character == "iko")
    assert notice.data["while_moving"] is True
    assert acting.data["while_moving"] is True
    assert notice.t == acting.t
    assert ctrl.records[120].s > ctrl.records[0].s + 30
    moving = next(seg for seg in ctrl.segments if seg.kind == "loco")
    assert moving.data["motion_overlay"] == "doubt_to_dash"
    assert moving.data["gaze_mode"] == "notice"
    assert not any(seg.kind == "idle" and seg.t0 == 0.0 for seg in ctrl.segments if seg.t1-seg.t0 > 0.2)
