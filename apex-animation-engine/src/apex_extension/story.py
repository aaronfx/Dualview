from dataclasses import dataclass
@dataclass(frozen=True)
class Beat:
    id: str
    goal: str
    requires: tuple[str,...]=()
    effects: tuple[str,...]=()
def validate(beats: list[Beat], initial=()):
    facts=set(initial); ids=set()
    for b in beats:
        if b.id in ids or not b.goal or not set(b.requires)<=facts: raise ValueError('invalid causal beat: '+b.id)
        ids.add(b.id); facts.update(b.effects)
    return facts
