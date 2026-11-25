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
from ..scene.goals import parse_goal, check_event, matches

class ProjectileReaction(Strict):
    thrower: str
    prop: str


class Task(Strict):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")
    actor: str
    after: list[str] = Field(default_factory=list,max_length=12)
    proof: str
    projectile_reaction: ProjectileReaction | None = None
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
        if self.projectile_reaction is not None:
            if self.projectile_reaction.thrower == self.actor or self.after:
                raise ValueError("projectile reaction requires independent defender and distinct thrower")
            if typ != "dodge" or who != self.actor:
                raise ValueError("projectile reaction proof must identify the defender's dodge")
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

def verify_task_evidence(tasks, events, duration, *, budget=20000):
    """One consistent, injective assignment of actual events to the task DAG.

    Distinct proof strings may overlap in what they match. Independent
    per-task or per-edge checks can reuse a witness or choose contradictory
    times for a shared predecessor. Search for a single assignment instead.
    Same-tick distinct events remain valid (runtime sorts them by type).
    """
    ordered = topological(tasks)
    indexed = sorted(enumerate(e for e in events if 0 <= e.t <= duration),
                     key=lambda pair: (pair[1].t, pair[0]))
    options = {task.id: [(i,e) for i,e in indexed if matches(task.proof,e)]
               for task in ordered}
    for task in ordered:
        if not options[task.id]:
            raise ValueError(f"Missing native task proof: {task.id}: {task.proof}")
    chosen, used = {}, set()
    explored = 0

    def assign(k):
        nonlocal explored
        if k == len(ordered):
            return True
        task = ordered[k]
        earliest = max((chosen[dep][1].t for dep in task.after), default=0.0)
        for i,event in options[task.id]:
            explored += 1
            if explored > budget:
                raise ValueError("Native task evidence search budget exhausted")
            if i in used or event.t + 1e-9 < earliest:
                continue
            chosen[task.id] = (i,event)
            used.add(i)
            if assign(k+1):
                return True
            used.remove(i)
            del chosen[task.id]
        return False

    if not assign(0):
        raise ValueError("No distinct, causally consistent native task witnesses")
    return [{"task": task.id, "proof": task.proof, "t": float(chosen[task.id][1].t),
             "event_index": chosen[task.id][0]} for task in ordered]


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

def verify_reactions(project, scene_id, tasks, sim):
    from .reaction_proof import verify_projectile_reaction
    return [verify_projectile_reaction(project, scene_id, task.actor,
                                      task.projectile_reaction.thrower,
                                      task.projectile_reaction.prop, sim)
            for task in tasks if task.projectile_reaction is not None]


def plan_ensemble(project,request):
    r=EnsembleRequest.model_validate(request)
    p,candidates,tasks=compile_ensemble(project,r)
    # Preflight each complete candidate with native evidence and each DAG edge,
    # then use the existing strict Inspector-backed rehearsal selection.
    from ..scene.runtime import SceneRuntime
    from .capabilities import validate_candidate
    from .smart_director import Trial,Selection
    accepted=[];rejected=[];reaction_reports={}
    for candidate in candidates:
        try:
            candidate_project=validate_candidate(p,r.scene_id,candidate.actions)
            sim=SceneRuntime(candidate_project,r.scene_id,strict=False).simulate(physics_only=True)
            verify_task_evidence(tasks, sim.events, sim.duration)
            reaction_reports[candidate.name] = verify_reactions(candidate_project, r.scene_id, tasks, sim)
            accepted.append(candidate)
        except (ValueError,RuntimeError,KeyError,TypeError,IndexError,ArithmeticError) as e:
            rejected.append(Trial(candidate.name,False,str(e)))
    if not accepted:return Selection(None,r.scene_id,rejected)
    selection=rehearse(p,r.scene_id,accepted,max_trials=r.max_trials)
    for trial in selection.trials:
        trial.checks.extend({"name":"projectile_counterfactual", "status":"PASS", "evidence":proof}
                            for proof in reaction_reports.get(trial.name, []))
    selection.trials=rejected+selection.trials
    return selection
