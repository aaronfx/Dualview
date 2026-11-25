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
