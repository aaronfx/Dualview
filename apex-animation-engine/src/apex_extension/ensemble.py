from dataclasses import dataclass
@dataclass(frozen=True)
class Reservation:
    actor:str
    resource:str
    start:float
    end:float
    def __post_init__(self):
        if not 0<=self.start<self.end:raise ValueError('invalid interval')
class Coordinator:
    def __init__(self):self.reservations=[]
    def reserve(self,r):
        if any((p.resource==r.resource or p.actor==r.actor) and max(p.start,r.start)<min(p.end,r.end) for p in self.reservations):return False
        self.reservations.append(r);return True
    def release(self,actor):self.reservations=[r for r in self.reservations if r.actor!=actor]
    def prune(self,t):self.reservations=[r for r in self.reservations if r.end>t]
def assign(actors,tasks,cost):
    # Exact bounded assignment, deterministic; no claim of physical feasibility.
    from itertools import permutations
    if len(tasks)>len(actors) or len(actors)>8:raise ValueError('assignment budget')
    actors=sorted(actors);tasks=sorted(tasks)
    return dict(zip(tasks,min(permutations(actors,len(tasks)),key=lambda p:(sum(cost(a,t) for a,t in zip(p,tasks)),p))))
