"""M1 causal evidence and goal-driven projectile acquisition over native actions."""
from types import SimpleNamespace as E
import pytest
from apex.ai.ensemble_planner import Task, verify_task_evidence, compile_ensemble
from apex.ai.objective_planner import compile_objectives
from apex.ai.capabilities import validate_candidate
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def task(id, proof, after=()):
    return Task(id=id,actor="kai",proof=proof,after=list(after),
                alternatives=[[{"character":"kai","type":"idle","duration":1}]])


def event(t, target):
    return E(t=t,type="notice",character="kai",data={"target":target})


def test_one_native_event_cannot_prove_two_tasks():
    tasks=[task("a","notice@kai"),task("b","notice@kai[target=prop:x]",["a"])]
    with pytest.raises(ValueError,match="distinct"):
        verify_task_evidence(tasks,[event(1,"prop:x")],3)


def test_dependencies_share_one_consistent_assignment():
    tasks=[task("a","notice@kai[target=prop:x]"),
           task("b","notice@kai",["a"]),
           task("c","notice@kai[target=prop:y]",["b"])]
    # Independent edges appear feasible if b uses x at t1 for one edge
    # and y at t2 for another, but neither can be reused.
    with pytest.raises(ValueError,match="distinct"):
        verify_task_evidence(tasks,[event(1,"prop:x"),event(2,"prop:y")],3)


def test_witness_search_backtracks_and_allows_distinct_same_tick():
    tasks=[task("a","notice@kai"),task("b","notice@kai[target=prop:x]")]
    proof=verify_task_evidence(tasks,[event(1,"prop:x"),event(1,"prop:y")],3)
    assert [p["event_index"] for p in proof]==[1,0]


def test_throw_at_uses_native_pickup_before_release():
    raw={"schema_version":"0.1","id":"causal","title":"causal","fps":24,
         "width":640,"height":360,"seed":3,
         "characters":[{"id":"kai","name":"KAI"},{"id":"rho","name":"RHO"}],
         "environments":[{"id":"e","room":{"width":1800,"height":900,"entry_door":False},
                          "props":[{"id":"plus","kind":"glyph","glyph":"+","position":[-300,30],
                                    "size":[56,56],"mass":6}],"dust":0}],
         "scenes":[{"id":"s","environment":"e","duration":7,
                    "placements":[{"character":"kai","x":-500,"facing":1},{"character":"rho","x":300,"facing":-1}],
                    "actions":[],"goals":["pick_up@kai[prop=plus]","throw@kai[prop=plus,target=char:rho]"],
                    "shots":[{"id":"a","start":0,"end":7,"camera":{"mode":"follow","target":"kai","view_height":600}}]}]}
    p=ProjectSpec.model_validate(raw)
    request={"scene_id":"s","max_trials":1,"tasks":[{"id":"send","actor":"kai","kind":"throw_at",
                 "target":"char:rho","prop":"prop:plus"}]}
    compiled,trace=compile_objectives(p,request)
    assert any(t.get("causal_steps")==["acquire","release"] for t in trace)
    base,candidates,tasks=compile_ensemble(p,compiled)
    candidate=validate_candidate(base,"s",candidates[0].actions)
    sim=SceneRuntime(candidate,"s").simulate(physics_only=True)
    proof=verify_task_evidence(tasks,sim.events,sim.duration)
    from apex.ai.smart_director import ordered_evidence
    assert ordered_evidence(p.scene("s").goals,sim.events,sim.duration)
    assert proof[0]["proof"]=="throw@kai[prop=plus,target=char:rho]"
    request["tasks"][0].pop("prop")
    with pytest.raises(ValueError,match="explicit prop"):
        compile_objectives(p,request)
