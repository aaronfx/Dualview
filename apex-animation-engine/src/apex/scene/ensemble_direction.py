"""Bounded scene-level director with reusable native tactics and real outcome feedback.

A director may choose among valid native action candidates, but may not manufacture
contacts, override controller physics, or bypass Inspector. No network or LLM needed.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from .performance_upgrade import rehearse, fuse_notice_travel

@dataclass(frozen=True)
class Partner:
    actor: str
    wait_goal: str
    actions: tuple[dict,...]

    def compile(self):
        from .schema import ActionSpec
        from .goals import parse_goal,check_event
        event,_,_=parse_goal(self.wait_goal)
        check_event(event,'partner wait')
        if any(a.get('character')!=self.actor for a in self.actions):
            raise ValueError('partner directive has a different actor')
        items=[dict(character=self.actor,type='wait_for',until='event:'+self.wait_goal.removeprefix('event:')),*deepcopy(self.actions)]
        return [ActionSpec.model_validate(a).model_dump(mode='json',exclude_defaults=True,exclude_none=True) for a in items]


def tune_actions(actions, pace='active'):
    """Action-level variants. Physics, time and contacts are never globally scaled."""
    if pace not in ('active','measured'): raise ValueError('unknown pace')
    out=deepcopy(list(actions))
    if pace=='measured':return out
    out=fuse_notice_travel(out)
    for a in out:
        # Only accelerate authored expressive performance, not strikes, falls,
        # climbing or required event waits. Preserve explicit author durations.
        if a['type']=='act' and a.get('duration') is None and a.get('tempo',1.)<=1.:
            a['tempo']=1.3
    return out


def objective_variants(project, objective, partners=(), post_actions=()):
    """Expand native geometric route proposals into ensemble action lists.

    All candidates must be rehearsed against the full scene with the same
    obstacles, other actors and explicit story goals. Native single-actor
    proposals are never claimed feasible for a multi-actor world by themselves.
    """
    from .autochoreo import propose
    from .schema import ProjectSpec,ActionSpec
    p=ProjectSpec.model_validate(project)
    placed={q.character for q in p.scene(objective.scene_id).placements}
    actors=[objective.actor,*[q.actor for q in partners]]
    if len(set(actors))!=len(actors) or not set(actors)<=placed:raise ValueError('invalid ensemble')
    followers=[a for partner in partners for a in partner.compile()]
    for candidate in propose(p,objective):
        actions=[deepcopy(a) for a in candidate.actions]
        # Preserve the physical route and pickup; stage the ending from the
        # scene objective rather than the single-actor benchmark celebration.
        if post_actions:
            i=next(i for i,a in enumerate(actions) if a['type']=='pick_up')
            actions=actions[:i+1]+deepcopy(list(post_actions))
        actions+=deepcopy(followers)
        for a in actions:ActionSpec.model_validate(a)
        yield candidate.name,actions


def direct_ensemble(project, objective, partners=(), post_actions=(), *, max_trials=8):
    """Choose a successful native ensemble rehearsal and record actual outcomes.

    Brain is used at decision/rehearsal boundaries only. This is offline
    feedback, not a claim of arbitrary live per-frame autonomy.
    """
    from ..ai.character_brain import CharacterBrain,Personality,Perception,Intent
    brain=CharacterBrain(Personality(curiosity=.65,courage=.8,empathy=.8,playfulness=.5))
    intent=brain.choose(Perception(goal_visible=True,target_id=objective.goal_prop_id))
    if intent not in (Intent.APPROACH,Intent.EXPLORE):raise RuntimeError('actor declined the objective')
    winner,trace=rehearse(project,objective.scene_id,objective_variants(project,objective,partners,post_actions),max_trials=max_trials)
    for trial in trace['trials']:
        brain.record_outcome(f'{objective.goal_prop_id}:{trial["name"]}',intent,succeeded=trial['accepted'])
    trace['brain']={'intent':intent.value,'memory':dict(brain.snapshot()),'failed_tactics':[{ 'target':k[0],'intent':k[1].value,'count':v} for k,v in brain.failed_attempts.items()]}
    return winner,trace
