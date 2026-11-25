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
    kind:Literal["observe","signal","collect","climb","exit","help_up","attack",
                 "vault","block","evade","recover","pull_up","celebrate","lift","throw_at"]
    target:str
    prop:str|None=None  # explicit projectile for throw_at; never guessed
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
        if kind=="char" and target==task.actor and task.kind!="recover":raise ValueError("Actor cannot target itself")
        actor=task.actor
        if task.kind != "throw_at" and task.prop is not None:
            raise ValueError(f"{task.id}: prop is only supported by throw_at")
        brain=memory.actor_brain(p.id,actor) if memory else CharacterBrain(Personality())
        perception=Perception(ally_needs_help=task.kind in ("help_up","pull_up"),
                              recovering=task.kind=="recover",goal_visible=True,target_id=target)
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
            proof=f"climbed@{actor}[target={task.target}]";seq=[[gaze,a("climb",target=task.target,tempo=1.2)],[a("climb",target=task.target)]]
        elif task.kind=="exit" and kind=="exit":
            proof=f"exit_reached@{actor}[exit={target}]";seq=[[a("reach_exit",target=task.target,speed=250)],[gaze,a("reach_exit",target=task.target,speed=160)]]
        elif task.kind=="help_up" and kind=="char":
            proof=f"hand_grab@{target}[with={actor}]";seq=[[a("run_to",target=task.target),a("offer_hand",target=task.target)],[a("offer_hand",target=task.target)]]
        elif task.kind=="attack" and kind=="char":
            proof=f"hit@{actor}[target={target}]";seq=[[a("strike",target=task.target,move=m)] for m in ("jab","cross","front_kick")]
        elif task.kind=="vault" and kind in ("obstacle","prop"):
            proof=f"vault@{actor}[target={task.target}]"
            seq=[[a("vault",target=task.target)],[gaze,a("vault",target=task.target)]]
        elif task.kind=="block" and kind=="char":
            # A guard pose alone does not prove successful defense.
            proof=f"block_hit@{actor}[by={target}]"
            seq=[[a("guard",until="next:"+proof)]]
        elif task.kind=="evade" and kind=="char":
            proof=f"evaded@{actor}[by={target}]"
            wait=a("wait_for",until=f"next:strike_start@{target}[target={actor}]")
            seq=[[wait,a("dodge",dodge=style)] for style in ("back","duck")]
        elif task.kind=="recover" and kind=="char" and target==actor:
            proof=f"stood_up@{actor}"
            seq=[[a("wait_for",until=f"event:settled@{actor}"),a("get_up")],
                 [a("get_up")]]
        elif task.kind=="pull_up" and kind=="char":
            proof=f"pulled_up@{target}[by={actor}]"
            seq=[[a("pull_up",target=task.target)]]
        elif task.kind=="celebrate" and kind=="char":
            proof=f"fist_bump@{actor}[with={target}]"
            seq=[[a("gesture",target=task.target,gesture="fist_bump"),a("act",clip="cheer",emotion="joyful",duration=.8)],
                 [a("gesture",target=task.target,gesture="fist_bump")]]
        elif task.kind=="lift" and kind=="prop":
            proof=f"lift_ok@{actor}[prop={target}]"
            seq=[[a("lift",target=task.target,effort=e)] for e in (1.0,1.4)]
        elif task.kind=="throw_at" and kind=="char":
            # Recover the M1 causal contract using the existing symbolic
            # search implementation. Native pickup/throw and rehearsal
            # remain the only authority on physical success.
            from apex_extension.planning import Action, plan
            if task.prop is None or task.prop not in {"prop:"+pid for pid in props}:
                raise ValueError(f"{task.id}: throw_at requires an existing explicit prop: target")
            pid=task.prop.split(":",1)[1]
            held=f"held:{actor}:{pid}"
            available=f"available:{pid}"
            free=f"hand_free:{actor}"
            released=f"released:{actor}:{pid}:{target}"
            ops=[Action("acquire",frozenset({available,free}),frozenset({held}),frozenset({available,free})),
                 Action("release",frozenset({held}),frozenset({released,free}),frozenset({held}))]
            steps=plan({available,free},{released},ops,budget=32)
            if steps!=("acquire","release"):
                raise ValueError(f"{task.id}: causal acquisition plan failed")
            proof=f"throw@{actor}[prop={pid},target={task.target}]"
            pickup=a("pick_up",target=task.prop)
            release=a("throw",target=task.target)
            seq=[[pickup,release],[a("run_to",target=task.prop,speed=220),pickup,release]]
            # Native proof is release toward target, not hit or evasion.
            trace.append({"task":task.id,"causal_steps":list(steps),"proof":proof})
        else:raise ValueError(f"{task.id}: unsupported objective/target combination")
        out.append(Task(id=task.id,actor=actor,after=task.after,proof=proof,alternatives=seq))
        trace.append({"task":task.id,"actor":actor,"intent":intent.value,"target":task.target,"alternatives":len(seq)})
    return EnsembleRequest(scene_id=r.scene_id,tasks=out,max_trials=r.max_trials),trace

def plan_objectives(project,request,memory=None):
    compiled,trace=compile_objectives(project,request,memory)
    result=plan_ensemble(project,compiled)
    return result,trace
