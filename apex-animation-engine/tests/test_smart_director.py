from types import SimpleNamespace
from pathlib import Path
import runpy
import pytest
from apex.ai.capabilities import catalogue, validate_candidate
from apex.ai.smart_director import ordered_evidence, CrossRequest, rehearse, render_selection, Selection
from apex.scene.schema import ProjectSpec, ActionType
from typing import get_args

def ev(kind,t,who="iko",**data):
    return SimpleNamespace(type=kind,t=t,character=who,data=data)

def test_catalogue_matches_native_schema():
    c=catalogue()
    assert {a["name"] for a in c["actions"]}==set(get_args(ActionType))
    assert all(a["requires_rehearsal"] for a in c["actions"])
    assert "pick_up" in c["events"]
    assert "doubt_to_dash" in c["motion_clips"]

def test_strict_goal_evidence():
    events=[ev("pick_up",1,prop="spark"),ev("notice",2)]
    with pytest.raises(ValueError,match="Missing ordered"):
        ordered_evidence(["notice@iko","pick_up@iko[prop=spark]"],events,3)
    with pytest.raises(ValueError):
        ordered_evidence(["notice@iko","notice@iko"],events,3)
    assert ordered_evidence(["pick_up@iko[prop=spark]"],events,3)[0]["t"]==1

def test_typed_objective_rejects_invented_fields():
    with pytest.raises(ValueError):
        CrossRequest(scene_id="s",actor="a",obstacle_id="b",goal_prop_id="c",teleport=True)

def test_refuse_render_of_rejected_plan(tmp_path):
    with pytest.raises(ValueError,match="No native rehearsal"):
        render_selection(Selection(None,"s",[]),tmp_path)

def test_native_rehearsal_known_crossing():
    builder=runpy.run_path(str(Path(__file__).parents[1]/"examples/build_impossible_crossing.py"))
    project,_=builder["build"]()
    sc=project.scene("cross")
    before=project.model_dump_json()
    candidates=[{"name":"fake","actions":[{"type":"idle","character":"iko","duration":2}]},
                {"name":"native","actions":[a.model_dump(mode="json") for a in sc.actions]}]
    result=rehearse(project,sc.id,candidates,max_trials=2)
    assert result.selected=="native", result.report()
    assert not result.trials[0].accepted
    assert result.trials[1].accepted
    assert project.model_dump_json()==before


def test_same_tick_distinct_events_are_not_alphabetical_causality():
    events=[ev("act",1,clip="doubt_to_dash"),ev("notice",1)]
    proof=ordered_evidence(["notice@iko","act@iko[clip=doubt_to_dash]"],events,2)
    assert [p["t"] for p in proof]==[1,1]


def test_catalogue_discloses_existing_typed_planners():
    from apex.ai.objective_planner import ObjectiveRequest
    from apex.ai.ensemble_planner import EnsembleRequest
    from apex.ai.mission import TOOL_SCHEMA
    cat = catalogue()
    assert {"objectives", "ensemble"} <= set(cat["tools"])
    assert cat["typed_planner_schemas"]["objectives"] == ObjectiveRequest.model_json_schema()
    assert cat["typed_planner_schemas"]["ensemble"] == EnsembleRequest.model_json_schema()
    schema = TOOL_SCHEMA.json_schema()
    assert {"objectives", "ensemble"} <= set(schema["discriminator"]["mapping"])
