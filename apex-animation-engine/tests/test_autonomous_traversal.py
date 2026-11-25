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
