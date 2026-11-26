import runpy
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime

def test_conflict_cast_and_no_authored_actions():
    raw=runpy.run_path("examples/build_one_vs_nine.py")["build"]()
    p=ProjectSpec.model_validate(raw)
    sc=p.scene("s")
    assert len(sc.placements)==10 and sc.duration==60 and not sc.actions
    assert len([a for a in sc.ensemble.actors if a.target=="iko"])==9

def test_sustained_conflict_does_not_end_on_first_strike():
    raw=runpy.run_path("examples/build_one_vs_nine.py")["build"]()
    sc=raw["scenes"][0]
    sc["duration"]=3
    sc["shots"][0]["end"]=3
    sc["goals"]=[]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    assert any(e.type=="conflict_engagement" for e in sim.events)
    assert any(e.type=="strike_start" for e in sim.events)
    assert not any(e.type=="ensemble_completed" for e in sim.events)
    assert not any(e.type=="conflict_escape" for e in sim.events)
    assert not any(e.type=="hit" and (e.character=="iko")== (e.data.get("target")=="iko") for e in sim.events)

def test_long_conflict_replans_locally_without_reducing_mission_goal():
    from apex.ai.autonomous_traversal import TraversalBrain
    raw=runpy.run_path("examples/build_one_vs_nine.py")["build"]()
    sc=raw["scenes"][0]
    sc["duration"]=8
    sc["shots"][0]["end"]=8
    sc["goals"]=[]
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    h=sim.controllers["iko"]
    assert h.autonomous_brain.goal==8600
    assert h.s>-8100, [(e.t,e.type,e.data) for e in sim.events if e.character=="iko" and e.type in ("autonomous_blocked","autonomous_decision","hit")]
