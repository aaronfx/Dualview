from dataclasses import dataclass
@dataclass(frozen=True)
class Beat:
    time:float
    importance:float
    subject:str
    kind:str
@dataclass(frozen=True)
class Shot:
    start:float
    end:float
    subject:str
    kind:str
def cut_plan(beats,duration,min_hold=1.0):
    if duration<=0 or min_hold<=0:raise ValueError('invalid duration')
    selected=[Beat(0,1,'world','wide')]
    for b in sorted(beats,key=lambda b:(b.time,-b.importance,b.subject)):
        if b.importance>=.6 and b.time-selected[-1].time>=min_hold and duration-b.time>=min_hold:selected.append(b)
    return tuple(Shot(b.time,selected[i+1].time if i+1<len(selected) else duration,b.subject,b.kind) for i,b in enumerate(selected))
def audio_cues(events, mapping):
    return sorted((float(e.t),mapping[e.type]) for e in events if e.type in mapping)
