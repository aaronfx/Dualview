"""Event-timed camera editor and causal story evidence; native shots only."""
from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class BeatShot:
    id:str
    kind:str
    camera:dict
    event:str|None=None
    offset:float=0.
    description:str=''


def event_shots(events,duration,shots,*,fps=24,min_seconds=.5):
    from .goals import matches
    if not shots or shots[0].event is not None:raise ValueError('first shot must begin at zero')
    if duration<=0 or min_seconds<=0:raise ValueError('invalid shot budget')
    result=[]; start=0.
    for s in shots:
        if s.event is None:
            if result:raise ValueError('later cuts need a real event')
        else:
            hit=next((e for e in sorted(events,key=lambda e:e.t) if matches(s.event,e) and e.t+s.offset>=start+min_seconds),None)
            if hit is None:raise ValueError(f'missing usable cut event {s.event}')
            end=round((hit.t+s.offset)*fps)/fps
            if end-start<min_seconds-1e-8 or duration-end<min_seconds-1e-8:raise ValueError(f'unreadable cut {s.id}')
            result[-1]['end']=end;start=end
        result.append(dict(id=s.id,kind=s.kind,start=start,end=duration,camera=s.camera,description=s.description))
    return result


def duration_for_payoff(t,fps=24,tail=1.25,maximum=60):
    if not math.isfinite(t) or t<0 or tail<.5:raise ValueError('invalid payoff')
    d=math.ceil((t+tail)*fps)/fps
    if d>maximum:raise ValueError('film budget exceeded')
    return d
