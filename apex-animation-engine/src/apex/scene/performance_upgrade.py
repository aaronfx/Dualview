"""P2/P4/P5 starter: bounded native rehearsal, not a replacement scene engine.

Candidate plans are validated and executed from scratch. Actual native events,
controller status and technical Inspector checks determine acceptance. This
is offline multi-character rehearsal, not live autonomous replanning.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, asdict
import math


def fuse_notice_travel(actions):
    """Only fuse a notice with the same actor's next matching travel target.

    Keep the other actors' order and all physical actions. Existing native
    notice_while_moving implements the actual event and animation. Never
    retime unrelated waits or remove contact/recovery segments.
    """
    out=deepcopy(list(actions)); last={}; remove=set()
    for i,a in enumerate(out):
        who=a['character']; j=last.get(who)
        if j is not None:
            n=out[j]
            if (n['type']=='notice' and a['type'] in ('run_to','walk_to')
                and n.get('target') and n['target']==a.get('target')
                and not any(n.get(k) is not None for k in ('until','lane','clip','emotion'))):
                a['notice_while_moving']=True
                remove.add(j)
        last[who]=i
    return [a for i,a in enumerate(out) if i not in remove]


def strict_events(goals, events, matches):
    """Find ordered, distinct actual events; equal timestamps are allowed."""
    ordered=sorted(enumerate(events),key=lambda item:(item[1].t,item[0]))
    found=[]; cursor=0
    for g in goals:
        for i in range(cursor,len(ordered)):
            e=ordered[i][1]
            if matches(g,e):
                found.append((g,float(e.t))); cursor=i+1; break
        else:
            return found,g
    return found,None


@dataclass(frozen=True)
class Trial:
    name:str
    accepted:bool
    reason:str
    events:tuple
    waste:float|None=None
    payoff:float|None=None
    failures:tuple=()


def rehearse(project, scene_id, alternatives, *, max_trials=8):
    """Select a bounded, physically verified multi-actor plan.

    `alternatives`: iterable (name, action dicts), all same world and goals.
    Return winning typed ProjectSpec + JSON-compatible evidence. On failure
    raise with the actual evidence; don't fabricate success. Final camera /
    render QA remains mandatory and separate.
    """
    from itertools import islice
    from .schema import ProjectSpec
    from .runtime import SceneRuntime
    from .goals import matches
    from ..qa.inspector import Inspector, gate_of
    from ..qa.actor_pacing import audit_character
    from ..render.pipeline import build_camera
    if not 1 <= max_trials <= 8: raise ValueError('max_trials must be 1..8')
    base=ProjectSpec.model_validate(project).model_dump(mode='json')
    idx=next(i for i,s in enumerate(base['scenes']) if s['id']==scene_id)
    if not 0 < base['scenes'][idx]['duration'] <= 60:
        raise ValueError('rehearse one bounded scene at a time (maximum 60 seconds)')
    goals=base['scenes'][idx].get('goals') or []
    if not goals: raise ValueError('explicit native event goals required')
    trials=[]; winners=[]
    for name,actions in islice(alternatives,max_trials):
        seen=[]
        try:
            candidate=deepcopy(base); candidate['scenes'][idx]['actions']=list(actions)
            p=ProjectSpec.model_validate(candidate)
            rt=SceneRuntime(p,scene_id,strict=False); sim=rt.simulate()
            seen,missing=strict_events(goals,sim.events,matches)
            violations=[f'{cid}: {c.violation}' for cid,c in sim.controllers.items() if c.violation]
            # Authored idle / guard may legally extend to the film tail. All
            # other unfinished directives or queues are an explicit failure.
            unfinished=[cid for cid,c in sim.controllers.items() if c.queue or
                        (c.cur is not None and c.cur.type not in ('idle','guard'))]
            bad_events=[f'{e.type}@{e.character}' for e in sim.events if e.type in ('action_impossible','fail')]
            if missing or violations or unfinished or bad_events:
                trials.append(Trial(name,False,f'missing={missing}; violations={violations}; unfinished={unfinished}; bad_events={bad_events}',tuple(seen))); continue
            report=Inspector(rt,build_camera(rt,p.width/p.height),p.fps,(p.width,p.height)).run(check_determinism=False)
            failed=tuple(c.name for c in report.checks if c.status=='FAIL' and gate_of(c.name)=='technical')
            if failed:
                trials.append(Trial(name,False,'native Inspector rejected plan',tuple(seen),failures=failed)); continue
            pacing=[audit_character(sim,cid) for cid in sim.controllers]
            waste=sum(r.wasted_seconds for r in pacing)
            payoff=seen[-1][1]
            if not math.isfinite(waste+payoff): raise ValueError('non-finite score')
            trials.append(Trial(name,True,'native events and technical Inspector passed; final shot QA pending',tuple(seen),waste,payoff))
            winners.append(((waste,payoff,name),p))
        except Exception as exc:
            trials.append(Trial(name,False,f'{type(exc).__name__}: {exc}',tuple(seen)))
    evidence={'trials':[asdict(t) for t in trials], 'goals':goals,
              'scope':'bounded offline rehearsal; not artistic certification'}
    if not winners:
        import json
        raise RuntimeError('No native plan passed: '+json.dumps(evidence,default=str))
    key,p=min(winners,key=lambda item:item[0]); evidence['chosen']=key[-1]
    return p,evidence
