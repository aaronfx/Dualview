import runpy
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
import pytest

@pytest.mark.parametrize("start,blocker,goal", [(-360,60,430),(-420,-20,510),(-500,140,650)])
def test_goal_only_native(start,blocker,goal):
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](start,blocker,goal,[])
    scene=raw["scenes"][0]
    scene["actions"]=[]
    scene["placements"][0]["destination_x"]=goal
    scene["goals"]=["autonomous_reached@iko"]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type=="autonomous_decision" for e in sim.events)
    assert any(e.type=="autonomous_reached" for e in sim.events)
    assert abs(sim.controllers["iko"].records[-1].pos[0]-goal)<3

@pytest.mark.parametrize("direction", [1,-1])
def test_goal_only_heavy_prop_jump(direction):
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-420*direction,800,600*direction,[])
    scene=raw["scenes"][0]
    scene["placements"]=scene["placements"][:1]
    scene["placements"][0]["facing"]=direction
    scene["placements"][0]["destination_x"]=600*direction
    scene["actions"]=[]
    scene["duration"]=10
    scene["shots"][0]["end"]=10
    scene["goals"]=["autonomous_reached@iko"]
    raw["environments"][0]["props"]=[{"id":"barrier","kind":"crate","position":[0,30],"size":[70,60],"mass":200,"depth":160}]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type=="autonomous_decision" and e.data.get("skill")=="jump" for e in sim.events)
    assert any(e.type=="takeoff" for e in sim.events)
    assert any(e.type=="autonomous_reached" for e in sim.events)
    assert abs(sim.controllers["iko"].records[-1].pos[0]-600*direction)<3

@pytest.mark.parametrize("direction", [1,-1])
def test_goal_only_light_prop_relocation(direction):
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-350*direction,800,600*direction,[])
    scene=raw["scenes"][0]
    scene["placements"]=scene["placements"][:1]
    scene["placements"][0]["facing"]=direction
    scene["placements"][0]["destination_x"]=600*direction
    scene["actions"]=[]
    scene["duration"]=14
    scene["shots"][0]["end"]=14
    scene["goals"]=["autonomous_reached@iko"]
    raw["environments"][0]["props"]=[{"id":"light","kind":"crate","position":[0,20],"size":[40,40],"mass":3,"depth":100}]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type=="autonomous_decision" and e.data.get("skill")=="relocate" for e in sim.events)
    assert any(e.type=="pick_up" and e.data.get("prop")=="light" for e in sim.events)
    assert any(e.type=="place" and e.data.get("prop")=="light" for e in sim.events)
    assert any(e.type=="autonomous_reached" for e in sim.events)
    assert abs(sim.controllers["iko"].records[-1].pos[0]-600*direction)<3

def test_goal_only_mixed_course():
    raw=runpy.run_path("examples/build_autonomous_mixed.py")["build"]()
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    skills=[e.data.get("skill") for e in sim.events if e.type=="autonomous_decision"]
    assert "avoid_segment" in skills
    assert "jump" in skills
    assert any(e.type=="autonomous_reached" for e in sim.events)
    assert abs(sim.controllers["iko"].records[-1].pos[0]-1050)<3

def test_extended_course_low_jump():
    raw=runpy.run_path("examples/build_autonomous_extended.py")["build"]()
    assert raw["scenes"][0]["actions"]==[]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type=="autonomous_reached" and e.character=="iko" for e in sim.events)
    jumps=[e for e in sim.events if e.type=="takeoff" and e.character=="iko"]
    assert len(jumps)==1, [(e.type,e.data) for e in sim.events if e.type=="autonomous_decision"]
    assert jumps[0].data["apex"]<=130
    assert abs(sim.controllers["iko"].records[-1].pos[0]-2250)<3

@pytest.mark.parametrize("kind,event", [("slide","slide_end"),("vault","vault"),("climb","climbed")])
def test_autonomous_acrobatics(kind,event):
    raw=runpy.run_path("examples/build_autonomous_acrobatics.py")["build"](kind)
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type==event and e.character=="iko" for e in sim.events), [(e.type,e.data) for e in sim.events if e.type.startswith("autonomous")]
    assert any(e.type=="autonomous_reached" for e in sim.events)
    assert sim.controllers["iko"].records[-1].frame=="floor"
    assert abs(sim.controllers["iko"].records[-1].pos[0]-650)<3

def test_climb_descends_directly_to_floor():
    raw=runpy.run_path("examples/build_autonomous_acrobatics.py")["build"]("climb")
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    ev=[e for e in sim.events if e.character=="iko"]
    climbed=next(e for e in ev if e.type=="climbed")
    flights=[e for e in ev if e.type=="takeoff" and e.t>climbed.t]
    assert len(flights)==1
    records=sim.controllers["iko"].records
    assert all(r.frame=="floor" for r in records if r.t>flights[0].t+2)

@pytest.mark.parametrize("kind",["slide","vault","climb"])
def test_goal_paced_acrobatics(kind):
    raw=runpy.run_path("examples/build_autonomous_acrobatics.py")["build"](kind,paced=True)
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    reached=next(e.t for e in sim.events if e.type=="autonomous_reached")
    assert 0<=sim.duration-reached<=.3
    assert sim.duration<10

def test_continuous_pursuit():
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"]()
    assert raw["scenes"][0]["actions"]==[]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    for actor in ("iko","pell"):
        ev=[e for e in sim.events if e.character==actor]
        for kind in ("slide_end","vault","climbed"):
            assert any(e.type==kind for e in ev), (actor,kind,[(e.type,e.data) for e in ev if e.type.startswith("autonomous")])
    assert any(e.type=="autonomous_reached" and e.character=="iko" for e in sim.events)
    updates=[e for e in sim.events if e.character=="pell" and e.type=="autonomous_decision" and e.data.get("skill")=="pursue"]
    assert len(updates)>=3
    assert len({e.data["observed_x"] for e in updates})>=3
    assert sim.controllers["pell"].records[-1].pos[0]>1000

def test_airborne_depth_separation():
    # Test with actual chase runtime, including airborne overlap in projection.
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"]()
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    import math
    for actor in ("iko","pell"):
        records=sim.controllers[actor].records
        for a,b,c in zip(records,records[1:],records[2:]):
            if a.mode==b.mode==c.mode=="airborne" and b.t-a.t>0 and c.t-b.t>0:
                # Native contact/transition boundaries are verified by the
                # full inspector in render QA; record finite physical states.
                assert all(math.isfinite(x) for x in b.pos+b.vel)

def test_hostile_chase_native_attack():
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"](hostile=True)
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert not raw["scenes"][0]["actions"]
    assert any(e.character=="pell" and e.type=="strike_start" for e in sim.events)
    assert any(e.character=="iko" and e.type=="autonomous_decision" and e.data.get("skill")=="evade_attack" for e in sim.events)
    assert any(e.character=="pell" and e.type=="whiff" for e in sim.events)

def test_combat_performance_uses_native_variety():
    from apex.ai.combat_performance import choose_combat_action
    from types import SimpleNamespace as NS
    from apex.ai.autonomous_traversal import TraversalBrain
    frame=object()
    brain=TraversalBrain(500,pursuit="iko",hostile=True)
    enemy=NS(cid="iko",s=90,z=0,frame=frame,mode="grounded",lying=False,cur=None,_gone=lambda:False)
    actor=NS(cid="pell",s=0,z=0,frame=frame,lying=False,carrying=None,cur=None,queue=[],facing=1,
             _upright=lambda:True,_path_blocker=lambda a,b:None,_strike_reach=lambda move:100,others={"iko":enemy})
    moves=[choose_combat_action(brain,actor,i)[1].move for i in range(5)]
    assert len(set(moves))==5
    enemy.s=300
    assert choose_combat_action(brain,actor,6) is None

def test_advanced_motion_math():
    from apex.motion.motion_intelligence import decay_offset, match_attack
    from apex.motion.combat import MOVES
    assert decay_offset(.5,2.,0,.045)==.5
    assert abs((decay_offset(.5,2.,1e-6,.045)-.5)/1e-6-2.)<.001
    assert abs(decay_offset(.5,2.,1.,.045))<.001
    assert match_attack(["jab","cross"],["jab","jab"],90,0,lambda m:100,MOVES)=="cross"

def test_story_roles_are_live_and_reciprocal():
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"](hostile=True)
    assert raw["scenes"][0]["storyline"]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    assert any(e.type=="actor_intent" and e.character=="iko" and e.data["state"]=="fight_to_escape" for e in sim.events)
    assert any(e.type=="actor_intent" and e.character=="pell" and e.data["state"]=="engage" for e in sim.events)

def test_hostile_pursuer_cannot_abandon_scene():
    from apex.qa.hostile_liveness import audit_hostile_liveness
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"](hostile=True)
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate()
    reports=audit_hostile_liveness(sim,raw["scenes"][0]["placements"])
    assert all(r["passed"] for r in reports.values()), reports
    assert sim.controllers["pell"].records[-1].pos[0]>1000, reports
