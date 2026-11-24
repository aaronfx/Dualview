from dataclasses import dataclass
@dataclass(frozen=True)
class SceneJob:
    id: str
    frames: int
    entry: dict
    exit: dict

def timeline(jobs: list[SceneJob]):
    cursor=0; previous=None; ids=set(); out=[]
    for j in jobs:
        if j.id in ids or j.frames<=0 or (previous is not None and previous!=j.entry): raise ValueError('continuity failure '+j.id)
        out.append((j.id,cursor,cursor+j.frames)); cursor+=j.frames; previous=j.exit; ids.add(j.id)
    return out
