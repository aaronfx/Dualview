"""Generate native task alternatives from bounded high-level actor objectives.

This is an intent compiler, not general-purpose online improvisation. Actors
and targets must exist. Native rehearsal selects feasible alternatives.
"""
from typing import Literal
from pydantic import Field
from .smart_director import Strict
from .ensemble_planner import Task,EnsembleRequest,plan_ensemble
from .character_brain import CharacterBrain,Personality,Perception,Intent
from ..scene.schema import ProjectSpec

class ActorObjective(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    actor:str
    kind:Literal["observe","signal","collect","climb","exit","help_up","attack"]
    target:str
    after:list[str]=Field(default_factory=list,max_length=12)
    urgency:Literal["calm","urgent"]="urgent"

class ObjectiveRequest(Strict):
    scene_id:str
    tasks:list[ActorObjective]=Field(min_length=1,max_length=12)
    max_trials:int=Field(6,ge=1,le=8)

def compile_objectives(project,request,memory=None):
    p=ProjectSpec.model_validate(project);r=ObjectiveRequest.model_validate(request)
    sc=p.scene(r.scene_id);env=p.environment(sc.environment)
    placed={pl.character for pl in sc.placements};props={v.id for v in env.props}
    known={"char":placed,"prop":props,"obstacle":{v.id for v in env.obstacles},"exit":{v.id for v in env.exits}}
    out=[];trace=[]
    for task in r.tasks:
        kind,sep,target=task.target.partition(":")
        if task.actor not in placed or not sep or kind not in known or target not in known[kind]:
            raise ValueError(f"{task.id}: actor or target does not exist in current scene")
        if kind=="char" and target==task.actor:raise ValueError("Actor cannot target itself")
        actor=task.actor
        brain=memory.actor_brain(p.id,actor) if memory else CharacterBrain(Personality())
        perception=Perception(ally_needs_help=task.kind=="help_up",goal_visible=True,target_id=target)
        intent=brain.choose(perception)
        def a(typ,**kw):return dict(character=actor,type=typ,**kw)
        gaze=a("notice",target=task.target,duration=.35 if task.urgency=="urgent" else .7)
        if task.kind=="observe":
            proof=f"notice@{actor}[target={task.target}]";seq=[[gaze]]
        elif task.kind=="signal":
            proof=f"point@{actor}[target={task.target}]";seq=[[gaze,a("point",target=task.target,duration=.6)],[a("point",target=task.target,duration=.8)]]
        elif task.kind=="collect" and kind=="prop":
            proof=f"pick_up@{actor}[prop={target}]"
            pickup=a("pick_up",target=task.target)
            seq=[[a("run_to",target=task.target,speed=310),pickup],[gaze,a("walk_to",target=task.target,speed=180),pickup],[gaze,pickup]]
            if intent==Intent.OBSERVE:seq.reverse()
        elif task.kind=="climb" and kind=="obstacle":
            proof=f"climbed@{actor}";seq=[[gaze,a("climb",target=task.target,tempo=1.2)],[a("climb",target=task.target)]]
        elif task.kind=="exit" and kind=="exit":
            proof=f"exit_reached@{actor}[exit={target}]";seq=[[a("reach_exit",target=task.target,speed=250)],[gaze,a("reach_exit",target=task.target,speed=160)]]
        elif task.kind=="help_up" and kind=="char":
            proof=f"hand_grab@{target}";seq=[[a("run_to",target=task.target),a("offer_hand",target=task.target)],[a("offer_hand",target=task.target)]]
        elif task.kind=="attack" and kind=="char":
            proof=f"hit@{actor}";seq=[[a("strike",target=task.target,move=m)] for m in ("jab","cross","front_kick")]
        else:raise ValueError(f"{task.id}: unsupported objective/target combination")
        out.append(Task(id=task.id,actor=actor,after=task.after,proof=proof,alternatives=seq))
        trace.append({"task":task.id,"actor":actor,"intent":intent.value,"target":task.target,"alternatives":len(seq)})
    return EnsembleRequest(scene_id=r.scene_id,tasks=out,max_trials=r.max_trials),trace

def plan_objectives(project,request,memory=None):
    compiled,trace=compile_objectives(project,request,memory)
    result=plan_ensemble(project,compiled)
    return result,trace
