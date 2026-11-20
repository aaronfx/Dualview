"""Character controller: the simulation-side state machine.

It runs inside the fixed-step physics loop and decides *what the body does* (grounded locomotion on a support
surface, actions, losing support when gravity changes, airborne control with impact prediction, landing
absorption and balance recovery). It records segments and events; the Animator later turns those into poses.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

from ..core.mathx import Vec, clamp, damped_spring, v_dot, v_rot, wrap_angle
from ..physics.gravity import GravityField, GravityTransition
from ..physics.world import ContactEvent, PhysicsWorld, capsule_moment
from ..rig.stickman import StickmanRig
from ..scene.schema import ActionSpec, EnvironmentSpec
from ..scene.targets import resolve
from .frames import GroundFrame

MASS = 70.0
CAPSULE_R = 9.0
SUPPORT_COS = math.cos(math.radians(55))  # gravity must point within 55deg of "into the surface" to stay supported
PRESS_CONTACT_T = 0.80  # contact time inside the press action
PRESS_DURATION = 1.75
PRESS_H_CONTACT_T = 1.55  # hesitant press: reach, hesitate, pull back, commit
PRESS_H_DURATION = 2.45
NOTICE_DOUBLE_TAKE = 0.55  # time of the second (snap) look inside a notice action
TURN_DURATION = 0.32
JUMP_PREP = 0.14


@dataclass
class Segment:
    kind: str  # idle | loco | turn | press | airborne | landing
    t0: float
    t1: float
    frame: str
    facing: float
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    t: float
    type: str
    character: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    t: float
    pos: Vec
    angle: float
    vel: Vec
    angvel: float
    mode: str
    frame: str
    s: float
    h: float
    facing: float
    brace: float = 0.0
    ttc: float = -1.0


class CharacterController:
    def __init__(self, cid: str, rig: StickmanRig, world: PhysicsWorld, frames: Dict[str, GroundFrame], gravity: GravityField,
                 env: EnvironmentSpec, x: float, facing: int, actions: List[ActionSpec], emit: Callable[[Event], None]):
        self.cid, self.rig, self.world, self.frames, self.gravity, self.env = cid, rig, world, frames, gravity, env
        self.emit = emit
        self.stand_h = rig.p.stand_height
        self.frame = frames["floor"]
        self.s, self.h, self.v = float(x), self.stand_h, 0.0
        self.facing = float(facing)
        self.mode = "grounded"
        self.queue: Deque[ActionSpec] = deque(actions)
        self.cur: Optional[ActionSpec] = None
        self.cur_t0 = 0.0
        self.cur_dir: Optional[float] = None
        self.segments: List[Segment] = []
        self.records: List[StepRecord] = []
        self.overlay: Optional[Dict[str, float]] = None  # landing compression carried into locomotion
        self.air: Dict[str, Any] = {}
        self.land: Dict[str, Any] = {}
        self.brace, self.ttc = 0.0, -1.0
        top = rig.p.spine + rig.p.chest + rig.p.neck + rig.p.head
        self.cap_a, self.cap_b = (0.0, -self.stand_h + CAPSULE_R), (0.0, top - CAPSULE_R)
        self.moment = capsule_moment(MASS, top + self.stand_h, CAPSULE_R)
        world.add_capsule(cid, self.frame.to_world(self.s, self.h), self.cap_a, self.cap_b, CAPSULE_R, MASS, kinematic=True)
        self._open("idle", 0.0)

    # ------------------------------------------------------------ segments
    def _open(self, kind: str, t: float, **data: Any) -> Segment:
        if self.segments and self.segments[-1].t1 < 0:
            self.segments[-1].t1 = t
            if self.segments[-1].t1 - self.segments[-1].t0 < 1e-9:
                self.segments.pop()
        seg = Segment(kind, t, -1.0, self.frame.tag, self.facing, dict(data))
        self.segments.append(seg)
        return seg

    @property
    def seg(self) -> Segment:
        return self.segments[-1]

    def close(self, t: float) -> None:
        if self.segments and self.segments[-1].t1 < 0:
            self.segments[-1].t1 = t

    # ------------------------------------------------------------ main update (before physics step)
    def update(self, t: float, dt: float) -> None:
        g = self.gravity.at(t)
        if self.mode == "grounded":
            gn = math.hypot(*g) or 1.0
            support = -v_dot((g[0] / gn, g[1] / gn), self.frame.normal)
            if support < SUPPORT_COS:
                self._lose_support(t, g)
            else:
                self._grounded(t, dt)
        elif self.mode == "airborne":
            self._airborne(t, dt, g)
        elif self.mode == "landing":
            self._landing(t, dt)

    def after_step(self, t: float, contacts: List[ContactEvent]) -> None:
        if self.mode == "airborne":
            for c in contacts:
                if c.a == self.cid and c.b in self.frames and c.normal_speed > 1.0:
                    self._touch_down(t, c)
                    break
        st = self.world.state(self.cid)
        if self.mode in ("airborne",):
            s, h = self.frame.to_frame(st.pos)
        else:
            s, h = self.s, self.h
        self.records.append(StepRecord(t, st.pos, st.angle, st.vel, st.angvel, self.mode if self.mode != "grounded" else self.seg.kind,
                                       self.frame.tag, s, h, self.facing, self.brace, self.ttc))

    # ------------------------------------------------------------ grounded behaviour
    def _place(self, t: float) -> None:
        h = self.h
        if self.overlay:
            tau = t - self.overlay["t"]
            x, _ = damped_spring(self.overlay["h0"], self.overlay["v0"], self.stand_h, 12.0, 0.6, tau)
            h = max(40.0, x)
            if tau > 0.6:
                self.overlay = None
                h = self.stand_h
        self.h = h
        tan = self.frame.tangent
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, h), self.frame.body_angle, (tan[0] * self.v, tan[1] * self.v))

    def _next_action(self, t: float) -> None:
        self.cur = self.queue.popleft() if self.queue else None
        self.cur_t0 = t
        self.cur_dir = None
        a = self.cur
        if a is None:
            if self.seg.kind != "idle":
                self._open("idle", t)
            return
        if a.type in ("walk_to", "run_to"):
            direction = 1.0 if a.target_x - self.s >= 0 else -1.0
            if direction != self.facing and abs(a.target_x - self.s) > 1.0 and abs(self.v) < 5:
                self.queue.appendleft(a)
                self.cur = ActionSpec(type="turn", character=self.cid, face=int(direction))
                a = self.cur
        if a.type == "point":
            tw = resolve(self.env, a.target)
            ts, _ = self.frame.to_frame(tw)
            if (ts - self.s) * self.facing < -20.0:  # target behind: turn toward it first
                self.queue.appendleft(a)
                self.cur = ActionSpec(type="turn", character=self.cid, face=int(-self.facing))
                a = self.cur
        gaze = resolve(self.env, a.target) if a.target else None
        if a.type in ("idle", "look_around", "wait_grounded"):
            self._open("idle", t, look=(a.type == "look_around"))
        elif a.type in ("look_at", "notice"):
            self._open("idle", t, gaze=gaze, gaze_mode=a.type, gaze_target=a.target)
            if a.type == "notice":
                self.emit(Event(t + NOTICE_DOUBLE_TAKE, "notice", self.cid, {"target": a.target}))
        elif a.type == "point":
            self._open("point", t, gaze=gaze, gaze_target=a.target)
            self.emit(Event(t + 0.25, "point", self.cid, {"target": a.target}))
        elif a.type in ("walk_to", "run_to"):
            if self.seg.kind != "loco":
                self._open("loco", t, run=(a.type == "run_to"), style=a.style, gaze=gaze)
        elif a.type == "turn":
            self._open("turn", t, face_from=self.facing, face_to=float(a.face))
            self.emit(Event(t, "turn", self.cid, {"to": a.face}))
        elif a.type == "press":
            sw = next(s for s in self.env.switches if s.id == a.switch)
            self._open("press", t, switch=sw.id, button=(sw.x, sw.height), pressed=False, hesitate=a.hesitate,
                       gaze=(sw.x, sw.height))
        elif a.type == "jump":
            if abs(self.v) < 40:
                raise ValueError("jump requires the character to be moving (run-up)")
            self.seg.data["prep"] = (t, t + JUMP_PREP)

    def _grounded(self, t: float, dt: float) -> None:
        if self.cur is None and self.queue:
            self._next_action(t)
        a = self.cur
        tau = t - self.cur_t0
        if a is None:
            pass
        elif a.type in ("idle", "look_around", "look_at", "notice", "point"):
            if tau >= (a.duration or (1.3 if a.type == "point" else 1.0)):
                self._next_action(t)
        elif a.type == "wait_grounded":
            # holds while a gravity change is still pending/in progress (the character waits, tense) and completes
            # once grounded with gravity settled
            pending = any(t < tr.t_start + tr.duration for tr in self.gravity.transitions)
            if not pending:
                self._next_action(t)
        elif a.type == "turn":
            if tau >= TURN_DURATION * 0.5:
                self.facing = float(a.face)
            if tau >= TURN_DURATION:
                self.seg.facing = self.facing
                self._next_action(t)
        elif a.type == "press":
            contact, dur = (PRESS_H_CONTACT_T, PRESS_H_DURATION) if a.hesitate else (PRESS_CONTACT_T, PRESS_DURATION)
            if not self.seg.data["pressed"] and tau >= contact:
                self.seg.data["pressed"] = True
                self._trigger_switch(t, a.switch)
            if tau >= dur:
                self._next_action(t)
        elif a.type in ("walk_to", "run_to"):
            self._locomote(t, dt, a)
        elif a.type == "jump":
            self.s += self.v * dt
            if tau >= JUMP_PREP:
                self._takeoff(t, a)
                return
        self._place(t)

    def _locomote(self, t: float, dt: float, a: ActionSpec) -> None:
        run = a.type == "run_to"
        cautious = a.style == "cautious"
        speed = a.speed or (430.0 if run else (90.0 if cautious else 140.0))
        acc, dec = (950.0, 1150.0) if run else ((300.0, 420.0) if cautious else (520.0, 650.0))
        if self.cur_dir is None:
            self.cur_dir = 1.0 if a.target_x - self.s >= 0 else -1.0
        direction = self.cur_dir  # fixed for the whole action (never re-decided mid-move)
        remaining = (a.target_x - self.s) * direction
        nxt = self.queue[0] if self.queue else None
        carry = nxt is not None and (nxt.type == "jump" or (nxt.type in ("walk_to", "run_to") and (nxt.target_x - a.target_x) * direction > 0))
        v_des = speed if carry else min(speed, math.sqrt(2 * dec * max(remaining, 0.0)))
        cur = self.v * direction
        cur = min(cur + acc * dt, v_des) if cur < v_des else max(cur - dec * dt, v_des)
        self.v = cur * direction
        self.s += self.v * dt
        self.seg.data["run"] = run or self.seg.data.get("run", False)
        if carry and remaining <= 0:
            self._next_action(t)
        elif not carry and remaining < 0.4:
            self.s, self.v = a.target_x, 0.0
            self._next_action(t)

    def _trigger_switch(self, t: float, switch_id: str) -> None:
        sw = next(s for s in self.env.switches if s.id == switch_id)
        g_now = self.gravity.at(t)
        mag = sw.effect.magnitude or math.hypot(*g_now)
        d = sw.effect.to
        n = math.hypot(*d) or 1.0
        to = (d[0] / n * mag, d[1] / n * mag)
        start = t + sw.effect.delay
        self.gravity.schedule(GravityTransition(start, sw.effect.duration, to, cause=switch_id))
        self.emit(Event(t, "press_contact", self.cid, {"switch": switch_id, "point": (sw.x, sw.height)}))
        self.emit(Event(t, "switch_activated", self.cid, {"switch": switch_id}))
        self.emit(Event(start, "gravity_shift", self.cid, {"from": g_now, "to": to, "duration": sw.effect.duration}))

    def _takeoff(self, t: float, a: ActionSpec) -> None:
        g = self.gravity.at(t)
        gm = math.hypot(*g)
        vn = math.sqrt(2 * gm * (a.height or 60.0))
        tan, nrm = self.frame.tangent, self.frame.normal
        vel = (tan[0] * self.v + nrm[0] * vn, tan[1] * self.v + nrm[1] * vn)
        self.world.set_dynamic(self.cid, vel, 0.0, MASS, self.moment)
        self.mode = "airborne"
        self.air = {"intent": "jump", "t0": t}
        self._open("airborne", t, intent="jump")
        self.cur = None
        self.emit(Event(t, "takeoff", self.cid, {"surface": self.frame.tag, "speed": self.v}))

    def _lose_support(self, t: float, g: Vec) -> None:
        tan, nrm = self.frame.tangent, self.frame.normal
        g_t = v_dot(g, tan)
        tip = -math.copysign(2.6, g_t) if abs(g_t) > 1 else 0.0
        vel = (tan[0] * self.v + nrm[0] * 95.0, tan[1] * self.v + nrm[1] * 95.0)
        self.world.set_dynamic(self.cid, vel, tip, MASS, self.moment)
        self.mode = "airborne"
        self.air = {"intent": "fall", "t0": t}
        self.overlay = None
        self._open("airborne", t, intent="fall")
        keep = self.cur is not None and self.cur.type not in ("idle", "look_around", "press", "look_at", "notice", "point")
        if keep:
            self.queue.appendleft(self.cur)
        self.cur = None
        self.emit(Event(t, "lost_support", self.cid, {"surface": self.frame.tag}))

    # ------------------------------------------------------------ airborne behaviour
    def _airborne(self, t: float, dt: float, g: Vec) -> None:
        st = self.world.state(self.cid)
        intent = self.air["intent"]
        look = 0.7
        hit = None
        speed = math.hypot(*st.vel)
        if speed > 1:
            end = (st.pos[0] + st.vel[0] * look, st.pos[1] + st.vel[1] * look)
            hit = self.world.raycast(st.pos, end, radius=4.0)
        self.ttc = hit.fraction * look if hit else -1.0
        if intent == "jump":
            self.world.set_angular_velocity(self.cid, clamp(10.0 * wrap_angle(self.frame.body_angle - st.angle), -12, 12))
            self.brace = clamp(1 - self.ttc / 0.3, 0, 1) if hit else 0.0
            return
        if hit and hit.tag in self.frames and self.ttc < 0.65:
            target = self.frames[hit.tag].body_angle
            if not self.air.get("brace_t"):
                self.air["brace_t"] = t
                self.seg.data["brace_t"] = t
                self.seg.data["brace_surface"] = hit.tag
                self.seg.data["brace_point"] = hit.point
                self.emit(Event(t, "brace", self.cid, {"surface": hit.tag, "ttc": self.ttc}))
            self.brace = clamp(1 - self.ttc / 0.65, 0, 1)
            err = wrap_angle(target - st.angle)
            self.world.set_angular_velocity(self.cid, clamp(14.0 * err, -14, 14))
        else:
            self.brace = 0.0

    def _touch_down(self, t: float, c: ContactEvent) -> None:
        st = self.world.state(self.cid)
        fr = self.frames[c.b]
        s, h = fr.to_frame(st.pos)
        vt, vn = fr.vec_to_frame(st.vel)
        approach = max(0.0, -vn, c.normal_speed)
        fwd = v_rot((self.facing, 0.0), st.angle)
        facing = 1.0 if v_dot(fwd, fr.tangent) >= 0 else -1.0
        ang_err = wrap_angle(st.angle - fr.body_angle)
        self.frame, self.facing = fr, facing
        self.brace, self.ttc = 0.0, -1.0
        self.emit(Event(t, "impact", self.cid, {"surface": fr.tag, "normal_speed": approach, "point": c.point, "tangent_speed": vt}))
        intent = self.air.get("intent")
        nxt = self.queue[0] if self.queue else None
        if intent == "jump" and nxt is not None and nxt.type in ("walk_to", "run_to") and abs(vt) > 60:
            self.mode = "grounded"
            self.s, self.h, self.v = s, min(h, self.stand_h), vt
            self.overlay = {"t": t, "h0": self.h, "v0": -approach * 0.55}
            self._open("loco", t, run=True, landing=(t, approach))
            self.cur = None
            self._next_action(t)
            self._place(t)
            return
        self.mode = "landing"
        self.s, self.h, self.v = s, h, 0.0
        self.land = {"t_contact": t, "s0": s, "h0": min(h, self.stand_h), "approach": approach, "vt": vt, "ang0": ang_err,
                     "w0": -vt * 0.0035 + st.angvel * 0.15}
        self._open("landing", t, **self.land)
        self.world.set_kinematic(self.cid, st.pos, st.angle)

    def _landing(self, t: float, dt: float) -> None:
        L = self.land
        tau = t - L["t_contact"]
        h, hv = damped_spring(L["h0"], -L["approach"] * 0.9, self.stand_h, 11.0, 0.55, tau)
        h = min(max(42.0, h), self.stand_h + 1.0)  # never rebound above leg reach (feet stay planted)
        s = L["s0"] + L["vt"] * (1 - math.exp(-12 * tau)) / 12.0
        a, av = damped_spring(L["ang0"], L["w0"], 0.0, 8.0, 0.3, tau)
        self.s, self.h = s, h
        self.world.set_kinematic(self.cid, self.frame.to_world(s, h), self.frame.body_angle + a)
        if tau > 0.45 and abs(h - self.stand_h) < 1.5 and abs(hv) < 15 and abs(a) < 0.02 and abs(av) < 0.15:
            self.mode = "grounded"
            self.h = self.stand_h
            self.emit(Event(t, "recovered", self.cid, {"surface": self.frame.tag}))
            self.cur = None
            self._open("idle", t, settle=True)
            if self.queue and self.queue[0].type == "wait_grounded":
                self.queue.popleft()
            self._place(t)

    def finish(self, t_end: float) -> None:
        self.close(t_end)
