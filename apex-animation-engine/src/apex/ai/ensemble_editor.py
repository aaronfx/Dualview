"""Native outcome-driven editorial timing for live ensembles."""
from copy import deepcopy
from math import ceil
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime

def finish_ensemble(raw,scene_id,tail=.35):
    if not .1<=tail<=.65:
        raise ValueError("invalid final hold")
    raw=deepcopy(raw)
    p=ProjectSpec.model_validate(raw)
    sim=SceneRuntime(p,scene_id).simulate(physics_only=True)
    sc=next(s for s in raw["scenes"] if s["id"]==scene_id)
    actors={a["character"] for a in sc["ensemble"]["actors"]}
    witnesses={e.character for e in sim.events if e.type=="ensemble_objective"}
    end=next((e.t for e in sim.events if e.type=="ensemble_completed"),None)
    if end is None or witnesses!=actors:
        raise ValueError("cannot edit away unfinished ensemble objectives")
    if len(sc["shots"])!=1:
        raise ValueError("automatic trim currently requires a single shot")
    duration=min(sc["duration"],ceil((end+tail)*p.fps)/p.fps)
    sc["duration"]=duration
    sc["shots"][0]["end"]=duration
    check=SceneRuntime(ProjectSpec.model_validate(raw),scene_id).simulate(physics_only=True)
    if {e.character for e in check.events if e.type=="ensemble_objective"}!=actors or not any(e.type=="ensemble_completed" for e in check.events):
        raise ValueError("edited scene lost native outcome evidence")
    return raw
