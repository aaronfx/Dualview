"""Bounded causal multi-character choreography over native action queues.

A task expresses a goal and alternative native performances. Dependencies
become native event waits, not guessed timestamps. Full-scene rehearsal is
authoritative. No new physics or action executor.
"""
from __future__ import annotations
from itertools import product, islice
from pydantic import Field, model_validator
from .smart_director import Strict, ActionCandidate, rehearse
from ..scene.schema import ActionSpec, ProjectSpec
from ..scene.goals import parse_goal, check_event

class Task(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    actor: str
    after: list[str] = Field(default_factory=list,max_length=12)
    proof: str
    alternatives: list[list[ActionSpec]] = Field(min_length=1,max_length=4)
    @model_validator(mode="after")
    def valid(self):
        typ,who,_=parse_goal(self.proof)
        check_event(typ,"ensemble task")
        if who is None:raise ValueError("task proof must identify an actor or object")
        if len(set(self.after))!=len(self.after) or self.id in self.after:
            raise ValueError("duplicate or self dependency")
        if any(not seq or len(seq)>32 or any(a.character!=self.actor for a in seq) for seq in self.alternatives):
            raise ValueError("each alternative must contain 1..32 actions for the task actor")
        return self

class EnsembleRequest(Strict):
    scene_id: str
    tasks: list[Task] = Field(min_length=1,max_length=12)
    max_trials: int = Field(6,ge=1,le=8)

def topological(tasks):
    by={t.id:t for t in tasks}
    if len(by)!=len(tasks):raise ValueError("duplicate task id")
    if len({t.proof for t in tasks})!=len(tasks):raise ValueError("task proofs must be distinct")
    if any(d not in by for t in tasks for d in t.after):raise ValueError("unknown dependency")
    done=set();ordered=[]
    while len(ordered)<len(tasks):
        ready=[t for t in tasks if t.id not in done and set(t.after)<=done]
        if not ready:raise ValueError("cyclic task dependency")
        for t in ready:
            ordered.append(t);done.add(t.id)
    return ordered

def compile_ensemble(project,request):
    p=ProjectSpec.model_validate(project);r=EnsembleRequest.model_validate(request)
    sc=p.scene(r.scene_id);tasks=topological(r.tasks);by={t.id:t for t in tasks}
    actors={t.actor for t in tasks}
    if not actors<={pl.character for pl in sc.placements}:raise ValueError("task actor not placed")
    other=[a.model_dump(mode="json") for a in sc.actions if a.character not in actors]
    # Author goals are retained, but independent task completions are checked
    # separately in rehearsal; unrelated actors need not finish in one order.
    raw=p.model_dump(mode="json")
    s=next(x for x in raw["scenes"] if x["id"]==r.scene_id)
    if not s["goals"]:raise ValueError("ensemble requires explicit scene outcome goals")
    candidates=[]
    for i,choices in enumerate(islice(product(*(t.alternatives for t in tasks)),r.max_trials)):
        actions=list(other)
        for task,seq in zip(tasks,choices):
            for dep in task.after:
                if by[dep].actor!=task.actor:
                    actions.append({"type":"wait_for","character":task.actor,"until":"event:"+by[dep].proof})
            actions.extend(a.model_dump(mode="json") for a in seq)
        candidates.append(ActionCandidate(name=f"ensemble_{i+1}",actions=actions))
    return ProjectSpec.model_validate(raw),candidates,tasks

def plan_ensemble(project,request):
    r=EnsembleRequest.model_validate(request)
    p,candidates,tasks=compile_ensemble(project,r)
    # Preflight each complete candidate with native evidence and each DAG edge,
    # then use the existing strict Inspector-backed rehearsal selection.
    from ..scene.runtime import SceneRuntime
    from .capabilities import validate_candidate
    from .smart_director import Trial,Selection,ordered_evidence
    accepted=[];rejected=[]
    for candidate in candidates:
        try:
            candidate_project=validate_candidate(p,r.scene_id,candidate.actions)
            sim=SceneRuntime(candidate_project,r.scene_id,strict=False).simulate(physics_only=True)
            for task in tasks:
                ordered_evidence([task.proof],sim.events,sim.duration)
                for dep in task.after:
                    parent=next(t for t in tasks if t.id==dep)
                    ordered_evidence([parent.proof,task.proof],sim.events,sim.duration)
            accepted.append(candidate)
        except (ValueError,RuntimeError,KeyError,TypeError,IndexError,ArithmeticError) as e:
            rejected.append(Trial(candidate.name,False,str(e)))
    if not accepted:return Selection(None,r.scene_id,rejected)
    selection=rehearse(p,r.scene_id,accepted,max_trials=r.max_trials)
    selection.trials=rejected+selection.trials
    return selection
