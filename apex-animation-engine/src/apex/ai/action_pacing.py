"""Goal-driven editorial timing, without changing native simulation speed."""
import math
from copy import deepcopy
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime
from ..qa.actor_pacing import audit_character

def fit_goal_scene(raw, scene_id, actor, *, tail=.25, fps=24):
    if not .1<=tail<=.5 or fps<=0:
        raise ValueError("invalid action pacing budget")
    result=deepcopy(raw)
    sim=SceneRuntime(ProjectSpec.model_validate(result),scene_id).simulate()
    reached=[e.t for e in sim.events if e.character==actor and e.type=="autonomous_reached"]
    if not reached:
        raise ValueError("cannot edit away an incomplete objective")
    scene=next(s for s in result["scenes"] if s["id"]==scene_id)
    if len(scene["shots"])!=1 or scene["shots"][0]["end"]!=scene["duration"]:
        raise ValueError("goal fitting supports single-shot scenes only")
    duration=min(scene["duration"],math.ceil((reached[0]+tail)*fps)/fps)
    scene["duration"]=duration
    scene["shots"][0]["end"]=duration
    check=SceneRuntime(ProjectSpec.model_validate(result),scene_id).simulate()
    if not any(e.type=="autonomous_reached" and e.character==actor for e in check.events):
        raise ValueError("shortened scene lost objective completion")
    report=audit_character(check,actor,min_pause=.38,max_waste=.65)
    if not report.passed:
        raise ValueError(f"action pacing failed: {report.to_dict()}")
    from ..qa.hostile_liveness import audit_hostile_liveness
    reports=audit_hostile_liveness(check,scene["placements"])
    if any(not r["passed"] for r in reports.values()):
        raise ValueError(f"story actor liveness failed: {reports}")
    return result
