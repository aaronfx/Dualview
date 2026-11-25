import runpy
from apex.scene.schema import ProjectSpec

module=runpy.run_path("examples/build_lockdown_master.py")
def test_master_plan_and_continuity():
    raw=module["build"]()
    p=ProjectSpec.model_validate(raw)
    sc=p.scene("s")
    assert sc.duration==180
    assert len(p.scenes)==1 and len(sc.placements)==10 and not sc.actions
    assert len(sc.shots)==7
    assert sc.shots[0].start==0 and sc.shots[-1].end==180
    assert all(a.end==b.start for a,b in zip(sc.shots,sc.shots[1:]))
    assert len({a.combat_style for a in sc.ensemble.actors if a.character!="iko"})==9

def test_progress_gaps_fail_closed():
    assert module["longest_gap"]([],0,15)==15
    assert module["longest_gap"]([2,5,9],0,12)==4


def test_opening_preview_preserves_native_initial_state():
    raw=module["build"]()
    preview=module["opening_preview"](raw)
    p=ProjectSpec.model_validate(preview)
    sc=p.scene("s")
    assert sc.duration==15 and len(sc.shots)==1 and not sc.actions
    assert preview["environments"]==raw["environments"]
    assert preview["scenes"][0]["placements"]==raw["scenes"][0]["placements"]
    assert preview["scenes"][0]["ensemble"]==raw["scenes"][0]["ensemble"]


def test_extended_route_preserves_opening_contact_and_native_hazards():
    raw=module["build"]()
    scene=raw["scenes"][0]
    env=raw["environments"][0]
    assert env["room"]["width"]>45000
    assert scene["placements"][1]["x"]-scene["placements"][0]["x"]==90
    assert len(env["obstacles"])==12
    assert scene["ensemble"]["actors"][0]["destination_x"]-scene["placements"][0]["x"]>44000
    assert not scene["actions"]
