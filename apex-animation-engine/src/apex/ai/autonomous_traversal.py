"""Goal-only floor traversal. Native controllers retain execution authority."""
from dataclasses import dataclass, field
import math
import py_trees
from ..scene.schema import ActionSpec
from ..scene.structures import Block
from ..scene.route_planner import select_clearance_jump
from ..motion.acrobatics import BODY_PASS_Z, CARRY_MASS_G, VAULT_MAX

@dataclass
class TraversalBrain:
    goal: float
    done: bool = False
    next_tick: float = 0.0
    last: tuple | None = None
    attempts: dict = field(default_factory=dict)
    pending: tuple | None = None
    progress_x: float | None = None
    progress_t: float = 0.0
    active_action: object = None
    route_signature: tuple | None = None
    pursuit: str | None = None
    fast: bool = False
    chase_ceiling: float | None = None
    pursuit_last: float | None = None
    hostile: bool = False
    last_attack: float = -10.0
    last_threat: float = -10.0
    combat_moves: list = field(default_factory=list)
    countered_at: float = -10.0

    def invalidate_after_hit(self,c,t,by):
        """Combat supersedes speculative traversal, never replay a stale queue."""
        from ..motion.controller import Event
        c.queue.clear()
        self.pending=None
        self.active_action=None
        self.route_signature=None
        self.progress_x=None
        self.attempts.clear()
        self.done=False
        self.next_tick=t
        c.emit(Event(t,"autonomous_replan",c.cid,{"reason":"combat interruption","by":by}))

    def _hazards(self,c):
        """Observe approaching same-lane solids using a short swept horizon."""
        d=1 if self.goal>c.s else -1
        hazards=[]
        for o in c.others.values():
            if o is c or o._gone() or o.frame is not c.frame:
                continue
            gap=(o.s-c.s)*d
            closing=max(0,abs(c.v)-o.v*d)
            if abs(o.z-c.z)<BODY_PASS_Z and 0<gap<max(160,closing*.65+50):
                hazards.append(("char:"+o.cid, bool(o.lying)))
        for pid,sp in c.props.items():
            if pid in c.world.inactive or not sp.solid or not sp.collide_characters:
                continue
            z,ph=c.world.depth.get(pid,(0,30))
            if abs(z-c.z)>=ph+14:
                continue
            st=c.world.state(pid)
            x0,x1,y0,y1=c._target_bounds("prop:"+pid)
            near=x0 if d>0 else x1
            gap=(near-c.s)*d
            closing=max(0,abs(c.v)-st.vel[0]*d)
            if y1>12 and y0<2.1*c.stand_h and -35<gap<max(160,closing*.65+70):
                hazards.append(("prop:"+pid, math.hypot(*st.vel)>20))
        return tuple(sorted(hazards))

    def tick(self, c, t):
        from ..motion.controller import Event
        if self.done or t < self.next_tick or c.mode != "grounded":
            return
        self.next_tick = t + (.035 if self.fast else .10)
        if self.pursuit is not None:
            target=c.others[self.pursuit]
            if self.chase_ceiling is None:
                self.chase_ceiling=self.goal
            d=1 if self.chase_ceiling>c.s else -1
            # Intercept the predicted route, not a hardcoded copy of its actions.
            # Long enough horizon to reason about the entire next obstacle.
            prediction=target.s+d*max(480,abs(target.v)*1.2)
            self.goal=min(self.chase_ceiling,prediction) if d>0 else max(self.chase_ceiling,prediction)
            if self.pursuit_last is None or abs(target.s-self.pursuit_last)>180:
                c.emit(Event(t,'autonomous_decision',c.cid,{'skill':'pursue','target':self.pursuit,'observed_x':target.s,'predicted_x':self.goal}))
                self.pursuit_last=target.s
        from .combat_performance import choose_combat_action
        decision=choose_combat_action(self,c,t)
        if decision is not None:
            skill,action,other=decision
            c.queue.clear()
            self.pending=None
            self.active_action=action
            c.queue.append(action)
            if c.cur is not None:
                c._next_action(t)
            if skill in ("attack","counterattack"):
                self.last_attack=t
            else:
                self.last_threat=t
            c.emit(Event(t,"autonomous_decision",c.cid,{"skill":skill,"target":other,"move":action.move,"defense":action.dodge}))
            return
        if c.cur is not None or c.queue:
            # Never interrupt contact, flight, an authored interaction or recovery.
            # Only our own ordinary locomotion may be cancelled after a stall.
            if c.cur is self.active_action and c.cur.type in ("walk_to","run_to") and not c.queue and not c.carrying and not c.lying:
                now=self._hazards(c)
                # Standing actors and ordinary props are already handled by
                # native lane avoidance. Newly prone bodies require a new plan.
                unexpected=any(k.startswith("char:") and flag and (k,flag) not in (self.route_signature or ()) for k,flag in now)
                if unexpected:
                    self.pending=None
                    self.active_action=None
                    c.v=0.0
                    c._next_action(t)
                    c.emit(Event(t,"autonomous_blocked",c.cid,{"reason":"new prone obstacle; replanning"}))
                    return
                self.route_signature=now
                if self.progress_x is None or abs(c.s-self.progress_x) >= 8:
                    self.progress_x, self.progress_t = c.s, t
                elif t-self.progress_t >= 1.5:
                    key = self.pending[0] if self.pending else ("travel","goal")
                    self.attempts[key] = self.attempts.get(key,0)+1
                    self.pending = None
                    self.active_action = None
                    c.v = 0.0
                    c._next_action(t)
                    c.emit(Event(t,"autonomous_blocked",c.cid,{"reason":"stalled locomotion; replanning","skill":key[0]}))
            return
        if self.pending is not None:
            key, origin = self.pending
            if abs(c.s-origin) < 8:
                self.attempts[key] = self.attempts.get(key, 0) + 1
            self.pending = None
        def emit(kind, **data):
            c.emit(Event(t, kind, c.cid, data))
        if abs(c.s-self.goal) < 3 and not c.lying and c.frame.owner is None:
            if self.pursuit is not None and abs(self.goal-self.chase_ceiling)>3:
                return
            self.done = True
            emit("autonomous_reached", x=c.s)
            return
        if c.lying or not c._upright():
            return
        if c.frame.owner is not None:
            # Isolated platform descent: native ballistic jump to clear floor.
            d=1 if self.goal>c.s else -1
            edge=c.frame.hi if d>0 else c.frame.lo
            landing=edge+d*100
            if (self.goal-landing)*d<0 or c.props or any(o is not c and not o._gone() and abs(o.z-c.z)<BODY_PASS_Z and min(c.s,landing)-100<o.s<max(c.s,landing)+100 for o in c.others.values()):
                return
            if any(b.owner!=c.frame.owner and b.y1>0 and b.x0<max(c.s,landing)+35 and b.x1>min(c.s,landing)-35 for b in c.blocks):
                return
            if not c.frame.lo+10<=c.s<=c.frame.hi-10:
                return
            if c.frame.origin[1]+2.1*c.stand_h+55>c.env.room.height:
                return
            key=("descend",c.frame.owner)
            if self.attempts.get(key,0)>=2:
                return
            # Advance to a stable launch position before descending. A jump
            # from the entry edge can land back on the same platform.
            launch=edge-d*60
            if (launch-c.s)*d>5:
                key=("platform_traverse",c.frame.owner)
                action=ActionSpec(character=c.cid,type="walk_to",target_x=launch,speed=120)
            else:
                action=ActionSpec(character=c.cid,type="jump_to",target_x=landing,height=45)
            self.pending=(key,c.s)
            self.active_action=action
            c.queue.append(action)
            emit("autonomous_decision",skill=key[0],target=key[1])
            return
        d = 1 if self.goal > c.s else -1
        end = self.goal
        obstacles = []
        for o in c.others.values():
            if o is c or o._gone() or o.frame is not c.frame or abs(o.z-c.z) >= BODY_PASS_Z:
                continue
            if not 0 < (o.s-c.s)*d < (end-c.s)*d:
                continue
            radius = 1.65*o.stand_h+20 if o.lying else 35
            height = .75*o.stand_h+20 if o.lying else 2.1*o.stand_h
            obstacles.append((o.s, Block("char:"+o.cid,o.s-radius,o.s+radius,0,height), o))
        for pid, sp in c.props.items():
            if pid in c.world.inactive or not sp.collide_characters or not sp.solid:
                continue
            z, ph = c.world.depth.get(pid,(0,30))
            if abs(z-c.z) >= ph+14:
                continue
            x0,x1,y0,y1 = c._target_bounds("prop:"+pid)
            lo, hi = sorted((c.s,end))
            if y1 > 12 and y0 < 2.1*c.stand_h and x1 > lo and x0 < hi:
                obstacles.append(((x0+x1)/2,Block("prop:"+pid,x0,x1,y0,y1),None))
        obstacles.sort(key=lambda q: (abs(q[0]-c.s),q[1].owner))
        hit = c._path_blocker(c.s,end)
        candidates = []
        def add(name, target_id, **kw):
            key=(name,target_id)
            if self.attempts.get(key,0)<2:
                if self.fast and kw.get("type")=="run_to":
                    kw["speed"]=min(480 if self.hostile else 430,kw.get("speed",300)*(1.28 if self.hostile else 1.15))
                candidates.append((key,ActionSpec(character=c.cid,**kw)))
        if not hit and not obstacles:
            add("travel","goal",type="run_to",target_x=end,speed=360,adaptive_avoidance=True)
        elif obstacles:
            _, b, actor = obstacles[0]
            bands = []
            for _, ob, other in obstacles:
                if other is not None:
                    bands.append((ob.owner,other.z, BODY_PASS_Z/2))
                else:
                    bands.append((ob.owner,*c.world.depth.get(ob.owner.split(":",1)[1],(0,30))))
            lane = c._free_lane(bands)
            if lane is not None and not hit and not any(other is not None and other.lying for _,_,other in obstacles):
                # Existing native proactive body/prop avoidance owns lane clearance.
                add("avoid",b.owner,type="run_to",target_x=end,speed=300,adaptive_avoidance=True)
        if len(obstacles)>1 and not hit:
            _, first, actor=obstacles[0]
            _, second, _=obstacles[1]
            if actor is None or not actor.lying:
                mid=first.x1+140 if d>0 else first.x0-140
                gap=(second.x0-mid) if d>0 else (mid-second.x1)
                band=(first.owner,actor.z,BODY_PASS_Z/2) if actor is not None else (first.owner,*c.world.depth.get(first.owner.split(":",1)[1],(0,30)))
                if gap>150 and c._free_lane([band]) is not None:
                    add("avoid_segment",first.owner,type="run_to",target_x=mid,speed=300,adaptive_avoidance=True)
        # Native static obstacle acrobatics with conservative geometry bands.
        if hit and not obstacles:
            from ..motion.controller import SLIDE_DROP, SLIDE_H
            face,b=hit
            near=b.x0 if d>0 else b.x1
            far=b.x1 if d>0 else b.x0
            spec=next((o for o in c.env.obstacles if o.id==b.owner),None)
            if spec is not None and spec.kind in ("beam","platform"):
                if b.y0>SLIDE_H+.72*c.stand_h+10 and b.y0<c.stand_h+40:
                    start=near-d*(430*SLIDE_DROP+45)
                    stop=far+d*80
                    if (end-stop)*d>=0 and not c._path_blocker(c.s,start) and not c._path_blocker(start,stop,top=SLIDE_H+.72*c.stand_h+5):
                        if (start-c.s)*d>5:
                            add("slide_approach",b.owner,type="run_to",target_x=start,speed=300,adaptive_avoidance=True)
                        elif (near-c.s)*d>=430*SLIDE_DROP+15:
                            add("slide",b.owner,type="duck_slide",target_x=stop,speed=430)
                elif b.y0<=0 and b.y1<=VAULT_MAX*c.stand_h and (end-far)*d>100 and (near-c.s)*d>.5*c.stand_h:
                    add("vault",b.owner,type="vault",target="obstacle:"+b.owner,speed=300)
                elif b.y0<=0 and .45*c.stand_h<=b.y1<=c.stand_h+c.shoulder_up+c.arm_reach+120 and (end-far)*d>120 and b.x1-b.x0>100 and b.y1+2.1*c.stand_h+55<c.env.room.height:
                    add("climb",b.owner,type="climb",target="obstacle:"+b.owner,tempo=1.2)
        relocation = None
        # Small floor props only: native pickup and placement, not teleportation.
        if obstacles and not hit and not c.carrying:
            _, b, actor = obstacles[0]
            if actor is None:
                pid = b.owner.split(":",1)[1]
                sp = c.props[pid]
                g = math.hypot(*c.gravity.at(t))
                rest = c.s-d*180
                tied = any(r.a == b.owner or r.b == b.owner for r in c.env.ropes)
                held = any(o.carrying == pid for o in c.others.values())
                clear_back = not c._path_blocker(c.s,rest)
                for oid, other in c.props.items():
                    if oid == pid or oid in c.world.inactive or not other.solid:
                        continue
                    l,r,_,_ = c._target_bounds("prop:"+oid)
                    if l < max(c.s,rest)+100 and r > min(c.s,rest)-100:
                        clear_back = False
                if any(o is not c and abs(o.z-c.z)<BODY_PASS_Z and min(c.s,rest)-100<o.s<max(c.s,rest)+100 for o in c.others.values()):
                    clear_back = False
                if (not tied and not held and clear_back and lane is None
                        and sp.mass*g <= CARRY_MASS_G*c.strength
                        and max(sp.size) <= .7*c.stand_h and b.y0 < 8
                        and math.hypot(*c.world.state(pid).vel)<10
                        and c.frame.lo+100 < rest < c.frame.hi-100
                        and (b.x0-c.s if d>0 else c.s-b.x1)>60):
                    add("relocate",b.owner,type="pick_up",target=b.owner)
                    if candidates and candidates[-1][0]==("relocate",b.owner):
                        relocation = ActionSpec(character=c.cid,type="place",target=f"point:{rest},0")
        if obstacles or hit:
            b = hit[1] if hit and (not obstacles or abs(hit[0]-c.s)<abs(obstacles[0][0]-c.s)) else obstacles[0][1]
            near = b.x0 if d>0 else b.x1
            far = b.x1 if d>0 else b.x0
            landing = far+d*110
            approach = near-d*130
            if (landing-end)*d <= 0 and c.frame.lo+40 <= landing <= c.frame.hi-40:
                live=tuple(q[1] for q in obstacles)
                verdict=select_clearance_jump(c.env,(c.s,0),(landing,0),live_bounds=live,body_height=2.1*c.stand_h,body_half_width=35,max_rise=260)
                can_approach=(approach-c.s)*d>10 and not c._path_blocker(c.s,approach) and all((q[1].x0-approach)>35 if d>0 else (approach-q[1].x1)>35 for q in obstacles)
                # Do not launch a long, high arc just because it is feasible.
                # Compare a closer takeoff using identical clearance budgets.
                closer=select_clearance_jump(c.env,(approach,0),(landing,0),live_bounds=live,body_height=2.1*c.stand_h,body_half_width=35,max_rise=260) if can_approach else None
                if can_approach and (not verdict.feasible or (closer.feasible and closer.plan.apex_y+15<verdict.plan.apex_y)):
                    add("approach",b.owner,type="run_to",target_x=approach,speed=300,adaptive_avoidance=True)
                if verdict.feasible:
                    add("jump",b.owner,type="jump_to",target_x=landing,height=verdict.plan.apex_y)
        selected=[]
        class Candidate(py_trees.behaviour.Behaviour):
            def __init__(self,item):
                super().__init__(name=item[0][0])
                self.item=item
            def update(self):
                selected.append(self.item)
                return py_trees.common.Status.SUCCESS
        if candidates:
            from .strategic_planning import select_native_contract
            contract=select_native_contract(candidates,relocation)
            if contract is None:
                emit("autonomous_blocked",reason="symbolic subgoal infeasible")
                return
            key, action, proof=contract
            py_trees.composites.Selector(name="traversal",memory=False,children=[Candidate((key,action))]).tick_once()
            key, action=selected[0]
            self.pending=(key,c.s)
            self.active_action=action
            self.progress_x,self.progress_t=c.s,t
            self.route_signature=self._hazards(c)
            c.queue.append(action)
            if key[0]=="slide_approach" and self.fast:
                # Native run->slide chaining preserves velocity and avoids a
                # decision-frame idle; the approach already proved clearance.
                d=1 if action.target_x>c.s else -1
                b=hit[1]
                stop=(b.x1 if d>0 else b.x0)+d*80
                c.queue.append(ActionSpec(character=c.cid,type="duck_slide",target_x=stop,speed=430))
                recovery=stop+d*140
                if (self.goal-recovery)*d>=0 and not c._path_blocker(stop,recovery) and not obstacles:
                    c.queue.append(ActionSpec(character=c.cid,type="run_to",target_x=recovery,speed=320,adaptive_avoidance=True))
            if key[0]=="climb":
                top=c._top_of(action.target,c.s)
                d=1 if self.goal>c.s else -1
                edge=top.hi if d>0 else top.lo
                launch=edge-d*60
                entry=(top.lo if d>0 else top.hi)+d*.42*c.stand_h
                if (launch-entry)*d>10 and top.lo+35<launch<top.hi-35:
                    c.queue.append(ActionSpec(character=c.cid,type="walk_to",target_x=launch,speed=120))
            if key[0]=="slide":
                # Continue directly into a short clear-floor recovery run, not
                # a one-tick idle which resets the pose history. Reassess after it.
                d=1 if action.target_x>c.s else -1
                recovery=action.target_x+d*min(140,abs(self.goal-action.target_x))
                if (recovery-action.target_x)*d>5 and not c._path_blocker(action.target_x,recovery) and not obstacles:
                    c.queue.append(ActionSpec(character=c.cid,type="run_to",target_x=recovery,speed=280,adaptive_avoidance=True))
            if key[0]=="relocate" and relocation is not None:
                c.queue.append(relocation)
            emit("autonomous_decision",skill=key[0],target=key[1],symbolic_plan=list(proof))
        else:
            key=("blocked",tuple(q[1].owner for q in obstacles),hit[1].owner if hit else None)
            if self.last != key:
                emit("autonomous_blocked",reason="no verified native action")
            self.last=key
