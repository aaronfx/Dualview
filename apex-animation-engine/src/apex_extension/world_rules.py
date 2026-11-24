from dataclasses import dataclass
from typing import Callable
@dataclass(frozen=True)
class Event:
    id: str
    kind: str
    tick: int
    payload: dict
class Rules:
    def __init__(self): self.handlers={}; self.seen=set(); self.last_tick=-1
    def add(self,kind: str, handler: Callable):
        if kind in self.handlers: raise ValueError('duplicate rule')
        self.handlers[kind]=handler
    def apply(self,state: dict,event: Event):
        from copy import deepcopy
        if event.id in self.seen or event.tick<self.last_tick: raise ValueError('replay or out of order')
        result=self.handlers[event.kind](deepcopy(state),event)
        self.seen.add(event.id); self.last_tick=event.tick
        return result
