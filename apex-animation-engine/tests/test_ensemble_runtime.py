import runpy
from copy import deepcopy
import pytest
from apex.scene.schema import ProjectSpec,EnsembleSpec
from apex.scene.runtime import SceneRuntime

def build():
    return runpy.run_path("examples/build_ensemble_ten.py")["build"]()

def test_ten_actors_live_native_objectives():
    raw=build()
    assert not raw["scenes"][0]["actions"]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    completions=[e for e in sim.events if e.type=="ensemble_objective"]
    assert len(completions)==10, [(e.t,e.character,e.type,e.data) for e in sim.events if e.type in ("ensemble_objective","autonomous_blocked","ensemble_intent")]
    assert len({e.character for e in completions})==10
    assert any(e.type=="ensemble_completed" for e in sim.events)
    for role in raw["scenes"][0]["ensemble"]["actors"]:
        c=sim.controllers[role["character"]]
        x=c.records[-1].pos[0]
        if role["objective"]=="reach":
            assert abs(x-role["destination_x"])<5
        else:
            leader=sim.controllers[role["target"]].records[-1].pos[0]
            assert abs(x-leader-role["offset"])<18
        assert abs(c.records[0].pos[0]-x)>300
    assert not any(e.type=="hit" for e in sim.events)

def test_ensemble_rejects_friend_attack_and_mixed_authoring():
    raw=build()
    r=raw["scenes"][0]["ensemble"]["actors"][1]
    r.update(objective="intercept",target="amber_0")
    with pytest.raises(ValueError):
        ProjectSpec.model_validate(raw)
    raw=build()
    raw["scenes"][0]["actions"]=[{"character":"amber_0","type":"idle","duration":1}]
    with pytest.raises(ValueError):
        ProjectSpec.model_validate(raw)

def test_target_reservations_distribute_across_hostile_team():
    from apex.ai.ensemble_runtime import EnsembleRuntime,Observation
    from types import SimpleNamespace as NS
    roles=[]
    for i in range(5):
        roles.append({"character":f"h{i}","team":"red","prompt":"Intercept one opposing team member.","objective":"intercept"})
        roles.append({"character":f"f{i}","team":"blue","prompt":"Escape to your own safe destination.","objective":"reach","destination_x":900+i*100})
    spec=EnsembleSpec.model_validate({"actors":roles,"hostile_teams":[["red","blue"]]})
    controllers={a.character:NS(s=i*30) for i,a in enumerate(spec.actors)}
    en=EnsembleRuntime(spec,controllers,2000)
    obs={cid:Observation(c.s,0,0,"floor",True) for cid,c in controllers.items()}
    choices=en.assignments(obs)
    assert len(choices)==5 and len(set(choices.values()))==5
    assert all(en.hostile(k,v) for k,v in choices.items())
