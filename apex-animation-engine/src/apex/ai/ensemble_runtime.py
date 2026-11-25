"""Live ensemble coordination over one shared native simulation.

A coordinator assigns objectives, never scripted action queues. Each actor owns
a native traversal/skill executor. All team decisions use the same immutable
snapshot before native physics advances; outcomes come from native events.
"""
from dataclasses import dataclass,field
from .autonomous_traversal import TraversalBrain
from ..motion.controller import Event

@dataclass(frozen=True)
class Observation:
    x: float
    z: float
    v: float
    frame: str
    available: bool

@dataclass
class ActorState:
    target: str|None=None
    complete: bool=False
    intent: str=""
    last_outcome: str=""
    memory: list=field(default_factory=list)

class EnsembleRuntime:
    def __init__(self,spec,controllers,half_width):
        self.spec=spec
        self.ctrls=controllers
        self.hw=half_width
        self.roles={a.character:a for a in spec.actors}
        self.hostility={frozenset(p) for p in spec.hostile_teams}
        self.state={cid:ActorState() for cid in self.roles}
        self.brains={cid:TraversalBrain(a.destination_x if a.destination_x is not None else controllers[cid].s,fast=True)
                     for cid,a in self.roles.items()}
        for cid,b in self.brains.items():
            b.ensemble_actor=True
            b.ensemble_target=None
            b.hostile=self.roles[cid].objective=="intercept"
        self.next_tick=0.
        self.event_cursor=0
        self.finished=False

    def hostile(self,a,b):
        return frozenset((self.roles[a].team,self.roles[b].team)) in self.hostility

    def snapshot(self):
        return {cid:Observation(c.s,c.z,c.v,c.frame.tag,not c._gone()) for cid,c in self.ctrls.items()}

    def assignments(self,obs):
        # Stable reservations avoid multiple attackers converging on a single
        # target when alternatives exist. Priority resolves competing claims.
        load={}
        out={}
        for cid,a in sorted(self.roles.items(),key=lambda q:(-q[1].priority,q[0])):
            if a.objective!="intercept" or self.state[cid].complete:
                continue
            candidates=[k for k,o in obs.items() if k!=cid and o.available and self.hostile(cid,k)
                        and (a.target is None or a.target==k)]
            if not candidates:
                continue
            old=self.state[cid].target
            def cost(k):
                distance=abs(obs[k].x-obs[cid].x)+2*abs(obs[k].z-obs[cid].z)
                return (load.get(k,0),distance-(80 if k==old else 0),k)
            target=min(candidates,key=cost)
            out[cid]=target
            load[target]=load.get(target,0)+1
        return out

    def _remember(self,events):
        for e in events[self.event_cursor:]:
            st=self.state.get(e.character)
            if st is None or e.type not in ("hit","hurt","whiff","blocked","autonomous_blocked","autonomous_reached","stood_up"):
                continue
            st.last_outcome=e.type
            st.memory=(st.memory+[(e.t,e.type,dict(e.data))])[-32:]
            if self.roles[e.character].objective=="intercept" and e.type=="hit" and e.data.get("target")==st.target:
                st.complete=True
        self.event_cursor=len(events)

    def _intent(self,cid,intent,target,t):
        st=self.state[cid]
        if (st.intent,st.target)!=(intent,target):
            st.intent,st.target=intent,target
            self.ctrls[cid].emit(Event(t,"ensemble_intent",cid,{"intent":intent,"target":target,"team":self.roles[cid].team}))

    def _waypoint(self,cid,x):
        b,c=self.brains[cid],self.ctrls[cid]
        x=max(-self.hw+40,min(self.hw-40,x))
        if abs(x-b.goal)>12 or (b.done and abs(x-c.s)>15):
            if abs(x-b.goal)>55:
                b.attempts.clear()
                b.last=None
            b.goal=x
            b.done=False
        # Do not interrupt native acrobatics, attacks, or other contact skills.
        # The current leg completes, then the executor adopts the new waypoint.

    def tick(self,t,events):
        if self.finished or t+1e-9<self.next_tick:
            return
        self.next_tick=t+1/self.spec.coordination_hz
        self._remember(events)
        obs=self.snapshot()
        assigned=self.assignments(obs)
        for cid,a in sorted(self.roles.items()):
            st,b,c=self.state[cid],self.brains[cid],self.ctrls[cid]
            if not st.complete:
                if a.objective=="reach":
                    self._intent(cid,"reach",None,t)
                    self._waypoint(cid,a.destination_x)
                    st.complete=b.done and abs(c.s-a.destination_x)<4
                elif a.objective=="escort":
                    leader=obs[a.target]
                    self._intent(cid,"escort",a.target,t)
                    self._waypoint(cid,leader.x+a.offset)
                    st.complete=self.state[a.target].complete and abs(c.s-(leader.x+a.offset))<18 and c.cur is None and not c.queue
                else:
                    target=assigned.get(cid)
                    self._intent(cid,"intercept" if target else "search",target,t)
                    b.ensemble_target=target
                    if target is not None:
                        o=obs[target]
                        direction=1 if o.x>=c.s else -1
                        gap=.85*c._strike_reach("jab")
                        # Maintain fighting range, not the opponent's exit.
                        self._waypoint(cid,o.x-direction*gap)
                        if b.done and abs(c.s-o.x)<=1.3*c._strike_reach("jab"):
                            b.done=False
            if st.complete:
                if st.intent!="complete":
                    self._intent(cid,"complete",st.target,t)
                    c.emit(Event(t,"ensemble_objective",cid,{"objective":a.objective,"target":st.target,"team":a.team,"witness":st.last_outcome or "native_position"}))
                b.done=True
                b.ensemble_target=None
        if all(st.complete for st in self.state.values()):
            self.finished=True
            next(iter(self.ctrls.values())).emit(Event(t,"ensemble_completed",None,{"actors":len(self.state)}))
