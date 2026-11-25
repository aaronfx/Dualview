"""Sustained asymmetric contest, not a queue of authored attacks.

The hero's goal is an actual escape position. Opponents remain hostile until
that outcome; a hit is not a capture. Native controllers own all motion,
contact, ragdoll, recovery, lane clearance and obstacles.
"""
from ..motion.controller import Event
from ..scene.schema import ActionSpec
from .live_skills import issue_native

class ConflictRuntime:
    def __init__(self,ensemble):
        self.en=ensemble
        self.spec=ensemble.spec.conflict
        self.hero=self.spec.protagonist
        self.guards=sorted(set(ensemble.roles)-{self.hero})
        self.stations={cid:ensemble.ctrls[cid].s for cid in self.guards}
        self.down_since={}
        self.active=set()
        self.finished=False
        self.hero_hit_times={}
        self.event_cursor=0
        self.hero_escape_until=0.
        self.hero_attack_failures={}
        self.encounter_target=None
        self.encounter_started=0.
        self.encounter_cooldowns={}
        self.last_progress_x=ensemble.ctrls[self.hero].s
        self.last_progress_t=0.
        for cid,b in ensemble.brains.items():
            b.conflict_actor=True
            b.conflict_style=ensemble.roles[cid].combat_style
            b.hostile=True
            if cid==self.hero:
                b.ensemble_impact="knockdown"
                b.conflict_hero=True

    def _idle(self,cid,t):
        c,b=self.en.ctrls[cid],self.en.brains[cid]
        b.ensemble_target=None
        # Only interrupt our own uncommitted locomotion. Never cancel a
        # strike, a vault, a climb, a fall or an interaction.
        if c.cur is b.active_action and c.cur is not None and c.cur.type in ("walk_to","run_to") and not c.queue:
            c._next_action(t)
            b.active_action=None
            b.pending=None
        b.done=True

    def _recovery(self,cid,t):
        c,b=self.en.ctrls[cid],self.en.brains[cid]
        if c.mode=="ragdoll" or c.lying:
            self.down_since.setdefault(cid,t)
            b.done=True
            b.ensemble_target=None
            if c.mode=="grounded" and c.lying and c.knocked and c.ragdoll is None and c.cur is None and not c.queue:
                delay=.45 if cid==self.hero else self.spec.recovery_delay
                if t-self.down_since[cid]>=delay:
                    self.en.skill_tickets[cid]=issue_native(c,t,ActionSpec(character=cid,type="get_up"))
                    c.emit(Event(t,"conflict_recovery",cid,{"kind":"self_recovery"}))
            return True
        if cid in self.down_since:
            self.down_since.pop(cid)
            b.attempts.clear()
            b.pending=None
            b.active_action=None
            b.last=None
            b.done=False
        return False

    def tick(self,t,events):
        if self.finished:
            return
        en=self.en
        ctrls,brains=en.ctrls,en.brains
        h,hb=ctrls[self.hero],brains[self.hero]
        dest=en.roles[self.hero].destination_x
        for ev in events[self.event_cursor:]:
            if ev.character==self.hero and ev.type=="hit":
                self.hero_hit_times[ev.data.get("target")]=ev.t
                self.hero_escape_until=max(self.hero_escape_until,ev.t+2.0)
            elif ev.character==self.hero and ev.type in ("whiff","blocked"):
                target=ev.data.get("target") or hb.ensemble_target
                self.hero_attack_failures[target]=self.hero_attack_failures.get(target,0)+1
                if self.hero_attack_failures[target]%2==0:
                    self.hero_escape_until=max(self.hero_escape_until,ev.t+1.2)
        self.event_cursor=len(events)
        unavailable={cid for cid in ctrls if self._recovery(cid,t)}
        if self.hero not in unavailable and h.mode=="grounded" and h.frame.owner is None and abs(h.s-dest)<4 and h.cur is None and not h.queue:
            h.emit(Event(t,"conflict_escape",self.hero,{"x":h.s,"opponents":len(self.guards)}))
            for cid in self.guards:
                self._idle(cid,t)
                en._intent(cid,"mission_failed",self.hero,t)
            hb.done=True
            en._intent(self.hero,"escaped",None,t)
            self.finished=True
            en.finished=True
            return
        # Only nearby eligible opponents engage; retain an in-flight strike's
        # reservation. This limits crowding without scripting attack times.
        eligible=[cid for cid in self.guards if cid not in unavailable and abs(ctrls[cid].s-h.s)<=self.spec.activation_radius]
        committed=[cid for cid in eligible if ctrls[cid].cur is not None and ctrls[cid].cur.type=="strike"]
        ordered=sorted(eligible,key=lambda cid:(0 if cid in committed else 1,abs(ctrls[cid].s-h.s)-(45 if cid in self.active else 0),cid))
        active=set(ordered[:self.spec.attack_slots]) if self.hero not in unavailable else set()
        for cid in sorted(active-self.active):
            ctrls[cid].emit(Event(t,"conflict_engagement",cid,{"target":self.hero}))
        self.active=active
        if self.hero not in unavailable:
            viable=[cid for cid in eligible if ctrls[cid].frame is h.frame and abs(ctrls[cid].z-h.z)<28 and not h._path_blocker(h.s,ctrls[cid].s)]
            if self.spec.require_distinct_contacts:
                viable=[cid for cid in viable if t>=self.encounter_cooldowns.get(cid,0.)]
                if abs(h.s-self.last_progress_x)>=25 or h.cur is not None and h.cur.type in ("strike","dodge","guard","climb","vault","duck_slide","get_up"):
                    self.last_progress_x,self.last_progress_t=h.s,t
                if t-self.last_progress_t>1.2:
                    # Repeated failure at a temporary combat waypoint is not a
                    # reason to halt the entire movie. Release it and replan.
                    if self.encounter_target is not None:
                        self.encounter_cooldowns[self.encounter_target]=t+5.
                    self.hero_escape_until=max(self.hero_escape_until,t+2.5)
                    hb.attempts.clear()
                    hb.last=None
                    hb.blocked_since=None
                    h.emit(Event(t,"autonomous_replan",self.hero,{"reason":"conflict progress watchdog","target":self.encounter_target,"x":h.s}))
                    self.last_progress_t=t
            target=min(viable,key=lambda cid:(0 if cid not in self.hero_hit_times else 1,0 if cid in active else 1,abs(ctrls[cid].s-h.s),cid)) if viable else None
            if self.spec.require_distinct_contacts:
                if target!=self.encounter_target:
                    self.encounter_target,self.encounter_started=target,t
                if target is not None and t-self.encounter_started>3.5:
                    self.encounter_cooldowns[target]=t+6.
                    self.hero_escape_until=max(self.hero_escape_until,t+2.5)
                    self.encounter_target=None
                    target=None
            hb.conflict_travel=t<self.hero_escape_until
            hb.ensemble_target=target
            en._intent(self.hero,"fight_to_escape" if target else "escape",target,t)
            # The film mode explicitly seeks first contact with an opponent,
            # instead of sprinting past the entire cast. Keep physical route
            # authority in TraversalBrain; no teleportation or forced hits.
            goal=dest
            if self.spec.require_distinct_contacts and target is not None and target not in self.hero_hit_times and not hb.conflict_travel:
                oc=ctrls[target]
                direction=1 if oc.s>=h.s else -1
                candidate=oc.s-direction*.85*h._strike_reach("jab")
                # Never reverse a long escape merely to chase a guard who
                # has already moved behind us. Nearby threats remain valid.
                if (candidate-h.s)*(1 if dest>h.s else -1)>=-100:
                    goal=candidate
            en._waypoint(self.hero,goal)
            hb.done=False
        for cid in self.guards:
            c,b=ctrls[cid],brains[cid]
            if cid in unavailable:
                continue
            if cid in active:
                b.ensemble_target=self.hero
                en._intent(cid,"engage",self.hero,t)
                side=1 if h.s>=c.s else -1
                # Stop in striking range, rather than target the hero's body.
                gap=.88*c._strike_reach("jab")
                en._waypoint(cid,h.s-side*gap)
                b.done=False
            elif cid in eligible:
                # Reserve room for active attackers while continuing purposeful
                # positioning. The longer film opts into this new behavior.
                en._intent(cid,"cover",self.hero,t)
                if self.spec.require_distinct_contacts:
                    b.ensemble_target=None
                    side=1 if c.s>=h.s else -1
                    goal=h.s+side*(250+60*(self.guards.index(cid)%3))
                    en._waypoint(cid,goal)
                else:
                    self._idle(cid,t)
            else:
                en._intent(cid,"watch",self.hero,t)
                self._idle(cid,t)
