import runpy
from apex.scene.schema import ProjectSpec

module=runpy.run_path("examples/build_lockdown_master.py")
def test_master_plan_and_continuity():
    raw=module["build"]()
    p=ProjectSpec.model_validate(raw)
    sc=p.scene("s")
    assert sc.duration==160
    assert len(p.scenes)==1 and len(sc.placements)==10 and not sc.actions
    assert len(sc.shots)==7
    assert sc.shots[0].start==0 and sc.shots[-1].end==160
    assert all(a.end==b.start for a,b in zip(sc.shots,sc.shots[1:]))
    assert len({a.combat_style for a in sc.ensemble.actors if a.character!="iko"})==9

def test_progress_gaps_fail_closed():
    assert module["longest_gap"]([],0,15)==15
    assert module["longest_gap"]([2,5,9],0,12)==4
