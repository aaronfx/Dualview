"""Live ensemble coordination over one shared native simulation.

A coordinator assigns objectives, never scripted action queues. Each actor owns
a native traversal/skill executor. All team decisions use the same immutable
snapshot before native physics advances; outcomes come from native events.
"""
from dataclasses import dataclass,field
from .autonomous_traversal import TraversalBrain
from ..motion.controller import Event
from ..scene.schema import ActionSpec
import math
from .live_skills import issue_native, observe_skill_outcome
from .actor_emotion import affect_after_event, completion_performance

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
    witness: dict|None=None
    memory: list=field(default_factory=list)
    fear: float=0.
    tension: float=0.
    relief: float=0.
    performed: bool=False
    announced: bool=False

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
            b.ensemble_aggression=self.roles[cid].aggression
            b.ensemble_impact=self.roles[cid].impact
            b.hostile=self.roles[cid].objective=="intercept"
        self.next_tick=0.
        self.event_cursor=0
        self.finished=False
        self.relationships={}
        self.reservations={}
        self.pickup_failures={}
        self.pickup_started={}
        self.resource_owners={}
        self.pickup_witnesses={}
        self.team_alerts={}
        self.alert_cursor=0
        self.assistance={}
        self.grips=set()
        self.skill_tickets={}
        self.rescue_attempts={}
        self.role_by_ally={a.target:a.character for a in spec.actors if a.objective=="assist"}
        self.conflict=None
        if spec.conflict is not None:
            from .live_conflict import ConflictRuntime
            self.conflict=ConflictRuntime(self)


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
            ctrl=self.ctrls[cid]
            if old in candidates and getattr(getattr(ctrl,"cur",None),"type",None)=="strike":
                out[cid]=old
                load[old]=load.get(old,0)+1
                continue
            def cost(k):
                distance=abs(obs[k].x-obs[cid].x)+2*abs(obs[k].z-obs[cid].z)-40*self.relationships.get((cid,k),{}).get("threat",0)
                if (a.team,k) in self.team_alerts:
                    distance-=60*a.empathy
                return (load.get(k,0),distance-(80 if k==old else 0),k)
            target=min(candidates,key=cost)
            out[cid]=target
            load[target]=load.get(target,0)+1
        return out

    def _remember(self,events):
        for e in events[self.event_cursor:]:
            for cid,ticket in list(self.skill_tickets.items()):
                outcome=observe_skill_outcome(ticket,e)
                if outcome is not None:
                    self.ctrls[cid].emit(Event(e.t,"ensemble_skill_outcome",cid,{"skill":ticket.action.type,"result":outcome,"native_event":e.type}))
                    self.skill_tickets.pop(cid,None)
            if e.character in self.roles:
                affect_after_event(self.state[e.character],self.roles[e.character],e)
            if e.type=="hand_grab":
                other=e.data.get("with")
                if other in self.roles and e.character in self.roles:
                    self.grips.add((e.character,other))
                    self.grips.add((other,e.character))
            if e.type=="stood_up":
                helper=e.data.get("helper")
                if helper in self.roles and self.roles[helper].objective=="assist" and self.roles[helper].target==e.character and (e.character,helper) in self.grips:
                    st=self.state[helper]
                    st.complete=True
                    st.witness={"event":"stood_up","t":e.t,"ally":e.character,"helper":helper}
                    # Recovered actor resumes its mission with a fresh native route.
                    b=self.brains[e.character]
                    b.done=False
                    b.pending=None
                    b.active_action=None
                    b.route_signature=None
                    b.progress_x=None
                    b.attempts.clear()
                    b.last=None
                    b.blocked_since=None
                    b.next_tick=e.t
                    self.assistance.pop(e.character,None)
                    self.ctrls[e.character].emit(Event(e.t,"autonomous_replan",e.character,{"reason":"assisted recovery; resume objective","helper":helper}))
            if e.type=="pick_up" and e.character in self.roles:
                pid=e.data.get("prop")
                self.resource_owners[pid]=e.character
                self.pickup_witnesses[(e.character,pid)]=e.t
            if e.type in ("place","throw") and self.resource_owners.get(e.data.get("prop"))==e.character:
                self.resource_owners.pop(e.data["prop"],None)
            if e.type=="hurt" and e.character in self.roles and e.data.get("by") in self.roles and self.hostile(e.character,e.data["by"]):
                team=self.roles[e.character].team
                self.team_alerts[(team,e.data["by"])]=(e.t,e.character)
            if e.type in ("hurt","block_hit","evaded","hand_grab"):
                other=e.data.get("by") or e.data.get("with")
                if e.character in self.roles and other in self.roles and other!=e.character:
                    rel=self.relationships.setdefault((e.character,other),{"threat":0.0,"trust":0.0})
                    if e.type=="hand_grab":
                        rel["trust"]=min(1.,rel["trust"]+.2)
                    else:
                        rel["threat"]=min(1.,rel["threat"]+.2)
            st=self.state.get(e.character)
            if st is None or e.type not in ("hit","hurt","whiff","blocked","autonomous_blocked","autonomous_reached","stood_up","pick_up","place","action_impossible"):
                continue
            st.last_outcome=e.type
            st.memory=(st.memory+[(e.t,e.type,dict(e.data))])[-32:]
            if self.conflict is None and self.roles[e.character].objective=="intercept" and e.type=="hit" and e.data.get("target")==st.target and st.target is not None and self.hostile(e.character,st.target):
                st.complete=True
                st.witness={"event":"hit","t":e.t,"target":st.target,"move":e.data.get("move")}
        self.event_cursor=len(events)

    def _intent(self,cid,intent,target,t):
        st=self.state[cid]
        if (st.intent,st.target)!=(intent,target):
            st.intent,st.target=intent,target
            self.ctrls[cid].emit(Event(t,"ensemble_intent",cid,{"intent":intent,"target":target,"team":self.roles[cid].team}))

    def _waypoint(self,cid,x):
        b,c=self.brains[cid],self.ctrls[cid]
        x=max(-self.hw+40,min(self.hw-40,x))
        if abs(x-b.goal)>12 or (b.done and abs(x-c.s)>3):
            if abs(x-b.goal)>55:
                b.attempts.clear()
                b.last=None
            b.goal=x
            b.done=False
        # Do not interrupt native acrobatics, attacks, or other contact skills.
        # The current leg completes, then the executor adopts the new waypoint.

    def _resources(self,t):
        """Allocate available resources exclusively, preserving active reservations."""
        active={}
        used=set(self.resource_owners)
        for cid,a in sorted(self.roles.items(),key=lambda q:(-q[1].priority,q[0])):
            if a.objective!="acquire" or self.state[cid].complete:
                continue
            c=self.ctrls[cid]
            if c.carrying in a.resources:
                continue
            old=self.reservations.get(cid)
            def eligible(pid):
                if pid in used or pid in c.world.inactive or pid not in c.props or self.pickup_failures.get((cid,pid),0)>=2:
                    return False
                if c.props[pid].mass*math.hypot(*c.gravity.at(t))>.9*c.strength:
                    return False
                return not any(r.a=="prop:"+pid or r.b=="prop:"+pid for r in c.env.ropes)
            options=[pid for pid in a.resources if eligible(pid)]
            if not options:
                continue
            pid=old if old in options else min(options,key=lambda k:(abs(c.world.state(k).pos[0]-c.s),k))
            active[cid]=pid
            used.add(pid)
        self.reservations=active
        return active

    def _acquire(self,cid,pid,t):
        st,b,c=self.state[cid],self.brains[cid],self.ctrls[cid]
        if c.carrying in self.roles[cid].resources and (cid,c.carrying) in self.pickup_witnesses:
            st.complete=True
            st.witness={"event":"pick_up","t":self.pickup_witnesses[(cid,c.carrying)],"prop":c.carrying}
            return
        self._intent(cid,"acquire" if pid else "await_resource",pid,t)
        if cid in self.pickup_started:
            old=self.pickup_started[cid]
            if c.cur is not None or c.queue:
                return
            self.pickup_failures[(cid,old)]=self.pickup_failures.get((cid,old),0)+1
            self.pickup_started.pop(cid)
        if pid is None:
            b.done=True
            return
        ps,ph=c.frame.to_frame(c.world.state(pid).pos)
        side=1 if c.s>=ps else -1
        stand=ps+side*(.74 if ph>.45*c.stand_h else .42)*c.stand_h
        if c.cur is None and not c.queue and c.mode=="grounded" and c._upright() and abs(c.s-stand)<8 and not c.carrying:
            b.done=True
            self.skill_tickets[cid]=issue_native(c,t,ActionSpec(character=cid,type="pick_up",target="prop:"+pid))
            self.pickup_started[cid]=pid
        else:
            # Native traversal handles obstacles on the way to the resource.
            self._waypoint(cid,stand)

    def _assist(self,cid,t):
        a=self.roles[cid]
        ally=a.target
        c,oc=self.ctrls[cid],self.ctrls[ally]
        b,ob=self.brains[cid],self.brains[ally]
        # Wait for a real, settled fall; never fabricate incapacity.
        if not oc.lying or oc.mode!="grounded" or oc.ragdoll is not None:
            b.done=True
            self._intent(cid,"watch_ally",ally,t)
            return
        self._intent(cid,"assist",ally,t)
        ob.done=True
        if c.cur is not None or c.queue or c.lying or c.mode!="grounded":
            return
        if oc.cur is not None or oc.queue:
            return
        if self.rescue_attempts.get(cid,0)>=2:
            return
        if c.frame is not oc.frame or abs(c.z-oc.z)>=28:
            return
        side=1 if c.s>=oc.s else -1
        dest=oc.s+side*.95*c.stand_h*.85
        if oc.posture=="supine":
            side=oc.facing
            dest=oc.s+side*(.95*c.stand_h*.85+.53*oc.p_leg)
        if c._path_blocker(c.s,dest):
            self._waypoint(cid,dest)
            return
        if abs(c.s-dest)>8:
            # Approach the required native contact pose before starting the
            # paired action, so the injured actor never waits for a distant hand.
            self._waypoint(cid,dest)
            return
        b.done=True
        self.skill_tickets[cid]=issue_native(c,t,ActionSpec(character=cid,type="offer_hand",target="char:"+ally))
        self.skill_tickets[ally]=issue_native(oc,t,ActionSpec(character=ally,type="get_up",target="char:"+cid))
        self.rescue_attempts[cid]=self.rescue_attempts.get(cid,0)+1
        self.assistance[ally]=cid

    def _perform(self,cid,t):
        st,c=self.state[cid],self.ctrls[cid]
        if not self.spec.perform_emotions:
            return True
        if st.performed:
            return c.cur is None and not c.queue
        if c.cur is not None or c.queue or c.mode!="grounded" or c.lying:
            return False
        if c.carrying or c.hang:
            st.performed=True
            return True
        action=completion_performance(cid,st,self.roles[cid])
        self.skill_tickets[cid]=issue_native(c,t,action)
        st.performed=True
        return False

    def tick(self,t,events):
        if self.finished or t+1e-9<self.next_tick:
            return
        self.next_tick=t+1/self.spec.coordination_hz
        self._remember(events)
        if self.conflict is not None:
            self.conflict.tick(t,events)
            return
        obs=self.snapshot()
        self.team_alerts={k:v for k,v in self.team_alerts.items() if t-v[0]<=3.0}
        assigned=self.assignments(obs)
        resources=self._resources(t)
        for cid,a in sorted(self.roles.items()):
            st,b,c=self.state[cid],self.brains[cid],self.ctrls[cid]
            if not st.complete:
                if a.objective=="reach":
                    self._intent(cid,"reach",None,t)
                    helper=self.role_by_ally.get(cid)
                    if helper and (c.lying or c.mode=="ragdoll" or (cid in self.assistance and not self.state[helper].complete)):
                        b.done=True
                    elif c.lying and c.knocked and c.mode=="grounded" and c.cur is None and not c.queue:
                        self.skill_tickets[cid]=issue_native(c,t,ActionSpec(character=cid,type="get_up"))
                        b.done=True
                    else:
                        self._waypoint(cid,a.destination_x)
                        st.complete=b.done and abs(c.s-a.destination_x)<4 and not c.lying and c.mode=="grounded" and c.frame.owner is None and c.cur is None and not c.queue
                elif a.objective=="escort":
                    leader=obs[a.target]
                    self._intent(cid,"escort",a.target,t)
                    self._waypoint(cid,leader.x+a.offset)
                    st.complete=self.state[a.target].complete and abs(c.s-(leader.x+a.offset))<18 and c.cur is None and not c.queue
                elif a.objective=="acquire":
                    self._acquire(cid,resources.get(cid),t)
                elif a.objective=="assist":
                    self._assist(cid,t)
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
                if not st.announced:
                    st.announced=True
                    self._intent(cid,"complete",st.target,t)
                    c.emit(Event(t,"ensemble_objective",cid,{"objective":a.objective,"target":st.target,"team":a.team,"witness":st.witness or st.last_outcome or "native_position"}))
                b.done=True
                b.ensemble_target=None
        # A completed actor can express relief immediately; do not require
        # unrelated actors to finish their own objectives first.
        performance_done=[self._perform(cid,t) for cid,st in sorted(self.state.items()) if st.complete]
        if all(st.complete for st in self.state.values()) and all(performance_done):
            self.finished=True
            next(iter(self.ctrls.values())).emit(Event(t,"ensemble_completed",None,{"actors":len(self.state)}))
