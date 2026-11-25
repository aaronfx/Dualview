"""Targeted pacing revision without rewriting approved scenes."""
from pathlib import Path
import shutil
from .local_production import read,atomic,safe_project,stage_project
from .smart_director import rehearse
from .capabilities import validate_candidate
from ..qa.director_critic import repair_candidates
from ..qa.actor_pacing import audit_character
from ..scene.runtime import SceneRuntime

def waste(p,sid):
    sim=SceneRuntime(p,sid,strict=False).simulate()
    return sum(audit_character(sim,cid).wasted_seconds for cid in sim.controllers)

def revise_scene(source,sid,destination):
    source,destination=Path(source),Path(destination)
    if source.resolve()==destination.resolve() or (destination.exists() and any(destination.iterdir())):
        raise ValueError("Revision must use a new empty directory")
    p=safe_project(read(source/"project.json"));baseline=waste(p,sid)
    passing=[]
    for c in repair_candidates(p,sid):
        if c["name"]=="original":continue
        result=rehearse(p,sid,[c],max_trials=1)
        if result.project is not None:
            score=waste(result.project,sid)
            if score+1e-4<baseline:passing.append((score,c["name"],result))
    if not passing:raise ValueError("No pacing repair improved this scene with native QA and goals retained")
    score,name,result=min(passing,key=lambda x:(x[0],x[1]))
    # All global/other scene fields are held by validate_candidate.
    stage_project(result.project,destination)
    atomic(destination/"revision.json",{"scene":sid,"old_waste":baseline,"new_waste":score,
           "selection":result.report(),"previous":source.name})
    # Cache contains content hashes and is validated before any reuse.
    old=source/"preview_scenes"
    if old.is_dir():shutil.copytree(old,destination/"preview_scenes")
    return result.project
