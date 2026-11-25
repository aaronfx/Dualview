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

def test_ensemble_compiler_ten_roles_preserves_world_and_cast():
    import json
    from apex.ai.ensemble_brief_compiler import compile_ensemble_brief
    raw=build()
    sc=raw["scenes"][0]
    briefs={a["character"]:a["prompt"] for a in sc["ensemble"]["actors"]}
    class Fake:
        def complete(self,system,user,max_tokens):
            assert json.loads(user)["briefs"]==briefs
            return json.dumps(sc["ensemble"])
    p=compile_ensemble_brief(raw,"s",sc["storyline"],briefs,Fake())
    assert len(p.scene("s").ensemble.actors)==10
    assert p.environment("e")==ProjectSpec.model_validate(raw).environment("e")
    assert p.scene("s").placements==ProjectSpec.model_validate(raw).scene("s").placements
    with pytest.raises(ValueError):
        compile_ensemble_brief(raw,"s",sc["storyline"],briefs,None)

def test_shared_resources_are_acquired_once_by_native_actors():
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-300,300,0,[])
    scene=raw["scenes"][0]
    scene.update(duration=8,actions=[],storyline="Two teammates collect distinct emergency supply kits.",goals=["ensemble_completed"])
    scene["shots"][0]["end"]=8
    raw["environments"][0]["props"]=[{"id":k,"kind":"toolbox","position":[x,20],"size":[30,30],"mass":2,"solid":False,"collide_characters":False} for k,x in (("kit_a",-120),("kit_b",120))]
    scene["ensemble"]={"actors":[{"character":cid,"team":"rescue","prompt":"Collect one available emergency kit without taking your teammate's kit.","objective":"acquire","resources":["kit_a","kit_b"]} for cid in ("iko","pell")]}
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    pickups=[e for e in sim.events if e.type=="pick_up"]
    assert len(pickups)==2 and len({e.data["prop"] for e in pickups})==2
    assert {c.carrying for c in sim.controllers.values()}=={"kit_a","kit_b"}
    assert any(e.type=="ensemble_completed" for e in sim.events)

def test_ensemble_editor_uses_actual_completion():
    from apex.ai.ensemble_editor import finish_ensemble
    raw=finish_ensemble(build(),"s")
    assert raw["scenes"][0]["duration"]<9
    assert raw["scenes"][0]["actions"]==[]

def test_ten_actor_hostile_native_contact_and_no_friendly_fire():
    raw=runpy.run_path("examples/build_ensemble_combat.py")["build"]()
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    hits=[e for e in sim.events if e.type=="hit"]
    assert len({e.character for e in hits if e.character.startswith("amber")})>=3, [(e.t,e.character,e.type,e.data) for e in sim.events if e.type in ("hit","strike_start","ensemble_intent","autonomous_blocked")]
    assert all(e.character.split("_")[0]!=e.data["target"].split("_")[0] for e in hits)
    assert len({e.character for e in sim.events if e.type=="ensemble_intent" and e.data["intent"]=="intercept"})==5

def test_native_skill_registry_covers_action_schema():
    from apex.ai.live_skills import registry,observe_skill_outcome,Ticket
    from apex.scene.schema import ActionType,ActionSpec
    from apex.motion.controller import Event
    from typing import get_args
    assert set(registry())==set(get_args(ActionType))
    ticket=Ticket(ActionSpec(character="ren",type="offer_hand",target="char:iko"),1.)
    assert observe_skill_outcome(ticket,Event(.9,"hand_grab","iko",{"with":"ren"})) is None
    assert observe_skill_outcome(ticket,Event(1.2,"hand_grab","iko",{"with":"pell"})) is None
    assert observe_skill_outcome(ticket,Event(1.2,"hand_grab","iko",{"with":"ren"}))=="success"

def test_emotion_is_event_driven_and_native():
    from apex.ai.actor_emotion import affect_after_event,completion_performance
    from apex.ai.ensemble_runtime import ActorState
    from apex.motion.controller import Event
    from types import SimpleNamespace as NS
    role=NS(courage=.3,objective="reach")
    st=ActorState()
    affect_after_event(st,role,Event(1,"hurt","iko",{}))
    assert st.fear>0
    assert completion_performance("iko",st,role).clip=="recover_relief"

def test_cooperative_rescue_requires_actual_grip_and_assisted_stand():
    raw=runpy.run_path("examples/build_ensemble_rescue.py")["build"]()
    assert raw["scenes"][0]["actions"]==[]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    assert any(e.type=="knockdown" and e.character=="iko" for e in sim.events)
    assert any(e.type=="hand_grab" and e.character=="iko" and e.data.get("with")=="ren" for e in sim.events), [(e.t,e.type,e.character,e.data) for e in sim.events if e.type in ("ensemble_intent","autonomous_blocked","hand_offered","help_missed","stood_up","settled","hit","knockdown")]
    assert any(e.type=="stood_up" and e.character=="iko" and e.data.get("helper")=="ren" for e in sim.events)
    assert any(e.type=="autonomous_decision" and e.character=="ren" and e.data.get("skill")=="yield_rescue_space" for e in sim.events)
    evidence=[(e.t,e.type,e.character,e.data) for e in sim.events if e.type in ("ensemble_intent","ensemble_objective","ensemble_completed","ensemble_skill_outcome","autonomous_blocked","autonomous_reached","hand_offered","help_missed","stood_up","act")]
    final={cid:{"x":c.s,"mode":c.mode,"lying":c.lying,"current":c.cur.type if c.cur else None,"queue":[a.type for a in c.queue],"goal":c.autonomous_brain.goal,"done":c.autonomous_brain.done} for cid,c in sim.controllers.items()}
    assert any(e.type=="act" and e.character=="ren" and e.data.get("emotion")=="relieved" for e in sim.events), (evidence,final)
    import json
    assert any(e.type=="ensemble_completed" for e in sim.events), json.dumps({"events":evidence,"final":final},default=str,indent=2)

def test_ensemble_director_preserves_scene_and_native_actions():
    from apex.ai.ensemble_editor import event_camera_candidates
    from apex.motion.controller import Event
    from types import SimpleNamespace as NS
    raw=build()
    sim=NS(events=[Event(2.5,"hit","amber_0",{"target":"cyan_0"}),Event(4.5,"act","cyan_0",{"clip":"cheer"})],
           controllers={cid:NS(records=[NS(t=3.,pos=(0.,0.)),NS(t=4.,pos=(0.,0.))]) for cid in ("amber_0","cyan_0")})
    result=event_camera_candidates(raw,"s",sim)[0]
    a=result["scenes"][0]
    b=raw["scenes"][0]
    assert a["actions"]==b["actions"]==[]
    assert a["placements"]==b["placements"]
    assert result["environments"]==raw["environments"]
    assert a["shots"][0]["start"]==0 and a["shots"][-1]["end"]==a["duration"]
    assert all(x["end"]-x["start"]>=.5 for x in a["shots"])
    assert all(x["end"]==y["start"] for x,y in zip(a["shots"],a["shots"][1:]))
    ProjectSpec.model_validate(result)
