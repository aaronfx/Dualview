from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count
from math import isfinite
@dataclass(frozen=True)
class Action:
    name:str
    requires:frozenset[str]
    adds:frozenset[str]
    removes:frozenset[str]=frozenset()
    cost:float=1
    def __post_init__(self):
        if not isfinite(self.cost) or self.cost<=0:raise ValueError('positive finite cost required')
def plan(initial,goal,actions,budget=10000):
    if budget<1:raise ValueError('budget')
    initial=frozenset(initial);goal=frozenset(goal); seq=count();q=[(0,next(seq),initial,())];best={initial:0}; expanded=0
    while q and expanded<budget:
        cost,_,state,path=heappop(q)
        if cost!=best[state]:continue
        if goal<=state:return path
        expanded+=1
        for a in sorted(actions,key=lambda a:a.name):
            if not a.requires<=state:continue
            nxt=(state-a.removes)|a.adds;nc=cost+a.cost
            if nc<best.get(nxt,float('inf')):
                best[nxt]=nc;heappush(q,(nc,next(seq),nxt,path+(a.name,)))
    return None
def native_search(project,objective):
    from apex.scene.autochoreo import search
    return search(project,objective)
