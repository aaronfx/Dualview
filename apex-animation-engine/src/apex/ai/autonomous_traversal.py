"""Goal-only floor traversal. Native controllers retain execution authority."""
from dataclasses import dataclass, field
import math
import py_trees
from ..scene.schema import ActionSpec
from ..scene.structures import Block
from ..scene.route_planner import select_clearance_jump
from ..motion.acrobatics import BODY_PASS_Z, CARRY_MASS_G

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

    def tick(self, c, t):
        from ..motion.controller import Event
        if self.done or t < self.next_tick or c.mode != "grounded":
            return
        self.next_tick = t + 0.10
        if c.cur is not None or c.queue:
            # Never interrupt contact, flight, an authored interaction or recovery.
            # Only our own ordinary locomotion may be cancelled after a stall.
            if c.cur is self.active_action and c.cur.type in ("walk_to","run_to") and not c.queue and not c.carrying and not c.lying:
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
        if abs(c.s-self.goal) < 3 and not c.lying:
            self.done = True
            emit("autonomous_reached", x=c.s)
            return
        if c.lying or c.frame.owner is not None or not c._upright():
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
            if lane is not None and not hit:
                # Existing native proactive body/prop avoidance owns lane clearance.
                add("avoid",b.owner,type="run_to",target_x=end,speed=300,adaptive_avoidance=True)
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
                if verdict.feasible:
                    add("jump",b.owner,type="jump_to",target_x=landing,height=verdict.plan.apex_y)
                elif (approach-c.s)*d>10 and not c._path_blocker(c.s,approach) and all((q[1].x0-approach)>35 if d>0 else (approach-q[1].x1)>35 for q in obstacles):
                    add("approach",b.owner,type="run_to",target_x=approach,speed=300,adaptive_avoidance=True)
        selected=[]
        class Candidate(py_trees.behaviour.Behaviour):
            def __init__(self,item):
                super().__init__(name=item[0][0])
                self.item=item
            def update(self):
                selected.append(self.item)
                return py_trees.common.Status.SUCCESS
        if candidates:
            py_trees.composites.Selector(name="traversal",memory=False,children=[Candidate(q) for q in candidates]).tick_once()
            key, action=selected[0]
            self.pending=(key,c.s)
            self.active_action=action
            self.progress_x,self.progress_t=c.s,t
            c.queue.append(action)
            if key[0]=="relocate" and relocation is not None:
                c.queue.append(relocation)
            emit("autonomous_decision",skill=key[0],target=key[1])
        else:
            key=("blocked",tuple(q[1].owner for q in obstacles),hit[1].owner if hit else None)
            if self.last != key:
                emit("autonomous_blocked",reason="no verified native action")
            self.last=key
