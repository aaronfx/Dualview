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
