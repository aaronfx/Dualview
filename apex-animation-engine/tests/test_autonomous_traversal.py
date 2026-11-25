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
