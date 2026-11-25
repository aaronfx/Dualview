from pathlib import Path
import runpy
import pytest
from apex.ai.objective_planner import compile_objectives,plan_objectives
from apex.scene.schema import ProjectSpec

def world():
    p=runpy.run_path(str(Path(__file__).parents[1]/"examples/build_impossible_crossing.py"))["world"]()
    # Two actors observing and signalling independently; dependency becomes an event wait.
    p["characters"].append({"id":"pell","name":"PELL"})
    s=p["scenes"][0];s["duration"]=5;s["shots"][0]["end"]=5
    s["placements"].append({"character":"pell","x":-500,"facing":1,"z":45})
    s["actions"]=[]
    s["goals"]=["notice@iko[target=prop:spark]","point@pell[target=prop:spark]"]
    return ProjectSpec.model_validate(p)

def request():
    return {"scene_id":"cross","tasks":[{"id":"observe","actor":"iko","kind":"observe","target":"prop:spark"},
        {"id":"signal","actor":"pell","kind":"signal","target":"prop:spark","after":["observe"]}],"max_trials":2}

def test_high_level_intents_compile_to_native_actors_and_proofs():
    p=world();r,trace=compile_objectives(p,request())
    assert len(r.tasks)==2 and r.tasks[1].after==["observe"]
    assert r.tasks[1].proof=="point@pell[target=prop:spark]"
    assert trace[0]["intent"] in ("observe","approach","explore")
def test_objective_rejects_nonexistent_target():
    req=request();req["tasks"][0]["target"]="prop:fake"
    with pytest.raises(ValueError,match="does not exist"):compile_objectives(world(),req)


@pytest.mark.parametrize("kind,target,proof,action", [
    ("vault","obstacle:barrier","vault@iko[target=obstacle:barrier]","vault"),
    ("block","char:pell","block_hit@iko[by=pell]","guard"),
    ("evade","char:pell","evaded@iko[by=pell]","dodge"),
    ("recover","char:iko","stood_up@iko","get_up"),
    ("pull_up","char:pell","pulled_up@pell[by=iko]","pull_up"),
    ("celebrate","char:pell","fist_bump@iko[with=pell]","gesture"),
    ("lift","prop:crate","lift_ok@iko[prop=crate]","lift"),
    ("attack","char:pell","hit@iko[target=pell]","strike"),
    ("help_up","char:pell","hand_grab@pell[with=iko]","offer_hand"),
])
def test_advanced_native_objectives_compile_with_specific_evidence(kind,target,proof,action):
    req={"scene_id":"cross","tasks":[{"id":"advanced","actor":"iko","kind":kind,"target":target}]}
    result,trace=compile_objectives(world(),req)
    assert result.tasks[0].proof==proof
    assert all(any(a.type==action for a in seq) for seq in result.tasks[0].alternatives)


def test_defense_and_recovery_target_must_be_correct():
    for kind,target in (("block","char:iko"),("recover","char:pell"),("evade","prop:spark")):
        req={"scene_id":"cross","tasks":[{"id":"invalid","actor":"iko","kind":kind,"target":target}]}
        with pytest.raises(ValueError):
            compile_objectives(world(),req)


def test_compiled_block_uses_actual_native_combat():
    from tests.test_combat import _fight
    from apex.scene.runtime import SceneRuntime
    from apex.scene.goals import matches
    from apex.ai.ensemble_planner import compile_ensemble
    raw=_fight([{"character":"kai","type":"strike","target":"char:rho","move":"jab"}],duration=5)
    raw["scenes"][0]["goals"]=["block_hit@rho[by=kai]"]
    req={"scene_id":"s","tasks":[{"id":"defend","actor":"rho","kind":"block","target":"char:kai"}]}
    project=ProjectSpec.model_validate(raw)
    compiled,_=compile_objectives(project,req)
    base,candidates,tasks=compile_ensemble(project,compiled)
    from apex.ai.capabilities import validate_candidate
    candidate=validate_candidate(base,"s",candidates[0].actions)
    sim=SceneRuntime(candidate,"s").simulate(physics_only=True)
    assert any(matches(tasks[0].proof,e) for e in sim.events)
    assert not any(e.type=="hit" and e.character=="kai" for e in sim.events)
    assert not any(c.violation for c in sim.controllers.values())
