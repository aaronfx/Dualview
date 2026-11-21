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
from ..scene.targets import bar_world, exit_world, resolve, switch_world
from .frames import GroundFrame
from .acrobatics import ACRO, AcroMixin
from .arcade import ArcadeMixin
from .combat import COMBAT, CombatMixin
from .interaction import INTERACTIONS, LIE_H, InteractionMixin
from .library import get_clip, landing_clip

MASS = 70.0
CAPSULE_R = 9.0
BODY_R = 11.0  # radius of the physical body props collide with
BODY_CONTACT_MASS = 8.0  # effective mass a body brings into a contact (a compliant body, not a 70 kg rigid block); the
# force it can apply is bounded separately, by the character's strength
KNEE_UP = 0.42  # its lower end, as a fraction of standing height (things lower than this are stepped over)
LANE_RATE = 110.0  # depth-lane change speed (units/s): a quick side-step
SUPPORT_COS = math.cos(math.radians(55))  # gravity must point within 55deg of "into the surface" to stay supported
PRESS_CONTACT_T = 0.80  # contact time inside the press action
PRESS_DURATION = 1.75
PRESS_H_CONTACT_T = 1.55  # hesitant press: reach, hesitate, pull back, commit
PRESS_H_DURATION = 2.45
NOTICE_DOUBLE_TAKE = 0.55  # time of the second (snap) look inside a notice action
TURN_DURATION = 0.32
JUMP_PREP = 0.14
JUMP_TO_PREP = 0.26  # standing jump: deeper anticipation crouch
SLIDE_DROP = 0.14  # run -> slide: hips drop
SLIDE_H = 30.0  # pelvis height while sliding
SLIDE_DECEL = 170.0  # sliding friction deceleration (u/s^2)
SLIDE_VMIN = 210.0
GRAB_REACH = 0.94
CATCH_KEEP = 0.55
PUMP_ACC = 1100.0  # tangential acceleration of a pumping kick (u/s^2, per unit mass)
RECOVER_T = get_clip("recover_relief").length()  # relief beat after a hard landing (the clip's own length)
RECOVER_MIN_APPROACH = 900.0  # grab when the bar is within this fraction of shoulder->wrist reach


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
    z: float = 0.0  # depth lane (negative = nearer the camera)


class CharacterController(InteractionMixin, CombatMixin, AcroMixin, ArcadeMixin):
    def __init__(self, cid: str, rig: StickmanRig, world: PhysicsWorld, frames: Dict[str, GroundFrame], gravity: GravityField,
                 env: EnvironmentSpec, x: float, facing: int, actions: List[ActionSpec], emit: Callable[[Event], None],
                 doors: Optional[Dict[str, Dict[str, Any]]] = None):
        self.cid, self.rig, self.world, self.frames, self.gravity, self.env = cid, rig, world, frames, gravity, env
        self.emit = emit
        self.doors = doors if doors is not None else {}
        self.shoulder_up = rig.p.spine + 0.86 * rig.p.chest  # shoulder above the pelvis along the body axis
        self.arm_reach = rig.p.upper_arm + rig.p.forearm  # shoulder -> wrist
        self.swing: Dict[str, Any] = {}
        self.exit: Dict[str, Any] = {}
        self.cur_prep = JUMP_PREP
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
        # physical interaction state (see interaction.py)
        self.posture = "stand"  # stand | prone
        self.body_tilt = 0.0  # rotation of the body toward the facing direction (pi/2 = lying prone)
        self.p_leg = rig.p.thigh + rig.p.shin
        self.strength = 45000.0
        self.others: Dict[str, "CharacterController"] = {}
        self.all_events: List[Event] = []
        self.props = {p.id: p for p in env.props}
        self.inter: Dict[str, Any] = {}
        self.strict = True  # False (setup solver): impossible actions are recorded in `violation` instead of raising
        self.violation: Optional[str] = None
        self.inter_action: Optional[ActionSpec] = None
        self.pinned_by: Optional[str] = None
        self.free_t: Optional[float] = None
        self.unpinned_t: Optional[float] = None
        self.carrying: Optional[str] = None
        # combat state (see combat.py)
        self.fight_mode = False
        self.dodging: Optional[Dict[str, Any]] = None
        self.knocked = False
        self.ragdoll = None
        self.z, self.z_target = 0.0, None
        self._acro_init()
        self._arcade_init()
        world.add_capsule(cid, self.frame.to_world(self.s, self.h), self.cap_a, self.cap_b, CAPSULE_R, MASS, kinematic=True)
        # the bounded-force physical body (props collide with it from knee height up; low things are stepped over)
        world.add_proxy(cid, (0.0, -self.stand_h + KNEE_UP * self.stand_h), self.cap_b, BODY_R, BODY_CONTACT_MASS, self.strength)
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
        self._now, self._dt = t, dt
        g = self.gravity.at(t)
        s_prev = self.s if self.mode in ("grounded", "landing") else None
        self._update(t, dt, g)
        self._step_from = s_prev
        if self.z_target is not None:  # changing depth lane (e.g. rolling past in front of someone)
            step = LANE_RATE * dt
            self.z += max(-step, min(step, self.z_target - self.z))
            if abs(self.z - self.z_target) < 1e-6:
                self.z_target = None
        if s_prev is not None and self.mode == "grounded":
            self._hold_for_lane(s_prev)  # side-stepping around a prop: do not reach it before the step is done
        if s_prev is not None and self.mode in ("grounded", "landing"):
            self._enforce_solid(t, s_prev)  # no motion of any kind carries the body through a structure
            self._enforce_bodies(t, s_prev)  # ... or through another standing body in the same depth lane
            self._enforce_props(t, s_prev)  # ... or into a prop it cannot push (directly placed moves)
        if self.mode == "grounded":
            self._edge_check(t)  # any motion past the end of a top steps off it (walks, lunges, dodges, knockbacks)
        self._proxy_sync(t)

    def _update(self, t: float, dt: float, g) -> None:
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
        elif self.mode == "swing":
            self._swing(t, dt, g)
        elif self.mode == "falling":
            self._falling(t, dt)
        # "ragdoll": the bodies are stepped by the physics world; see after_step

    def after_step(self, t: float, contacts: List[ContactEvent]) -> None:
        self._proxy_react(t)
        if self.mode == "airborne":
            g = self.gravity.direction(t)
            for c in contacts:
                if c.a == self.cid and c.b in self.frames and c.normal_speed > 1.0:
                    # only a surface that can hold the body under the current gravity is a landing; anything else
                    # (e.g. grazing the ceiling while gravity points at a wall) is a glancing contact. A structure top
                    # only counts from above and within its ends; a flip only lands once it has come round.
                    fr = self.frames[c.b]
                    top_ok = not fr.bounded or (v_dot(c.normal, fr.normal) > 0.6 and fr.lo - 8.0 <= fr.to_frame(c.point)[0] <= fr.hi + 8.0)
                    st_ = self.world.state(self.cid)
                    flip_ok = not self.air.get("flip") or abs(wrap_angle(st_.angle - fr.body_angle)) < 1.1
                    if -v_dot(g, fr.normal) >= SUPPORT_COS and top_ok and flip_ok:
                        self._touch_down(t, c)
                        break
                    self.emit(Event(t, "graze", self.cid, {"surface": c.b, "normal_speed": c.normal_speed, "point": c.point}))
        if self.mode == "ragdoll":
            self._ragdoll_after_step(t, contacts)
        if self.thrown is not None:
            self._thrown_tick(t)
        if self.posture == "prone":
            self._check_pinned(t)
        self._arcade_tick(t)  # orbs change the body's velocity; portals move it (Milestone 4)
        st = self.world.state(self.cid)
        if self.mode in ("airborne", "swing"):
            s, h = self.frame.to_frame(st.pos)
        else:
            s, h = self.s, self.h
        self.records.append(StepRecord(t, st.pos, st.angle, st.vel, st.angvel, self.mode if self.mode != "grounded" else self.seg.kind,
                                       self.frame.tag, s, h, self.facing, self.brace, self.ttc, self.z))

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
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, h), self.frame.body_angle - self.facing * self.body_tilt,
                                 (tan[0] * self.v, tan[1] * self.v))

    def _next_action(self, t: float) -> None:
        self.cur = self.queue.popleft() if self.queue else None
        self.cur_t0 = t
        self.cur_dir = None
        a = self.cur
        if a is not None and a.lane is not None:
            self.z_target = float(a.lane)
        if a is None:
            if self.lying:
                if self.seg.kind != self.posture:
                    self._open(self.posture, t, rest=True)
            elif self.seg.kind != "idle":
                self._open("idle", t, fight=self.fight_mode)
            return
        if self.lying and self.knocked and a.type not in ("get_up", "wait_for", "look_at", "notice", "idle", "struggle", "crawl_out"):
            # knocked down: get up before anything that needs standing
            self.queue.appendleft(a)
            a = self.cur = ActionSpec(type="get_up", character=self.cid)
        if a.type in COMBAT:
            self._start_combat(t, a)
            return
        if a.type in ACRO:
            self._start_acro(t, a)
            return
        if a.type in ("gesture", "offer_hand"):
            self.fight_mode = False
        if a.type in ("walk_to", "run_to") and a.target_x is None:  # walk to a character / prop
            ts = self._target_s(a.target)
            d0 = 1.0 if ts >= self.s else -1.0
            stop = 0.75 * self.stand_h if a.target.startswith("char:") else 0.35 * self.stand_h
            if a.target.startswith("prop:"):
                lo, hi = self._prop_extent_s(self._pid(a.target))
                ts = lo if d0 > 0 else hi
            a = self.cur = a.model_copy(update={"target_x": ts - d0 * stop})
        if a.type in ("walk_to", "run_to") and not self.lying:
            a = self.cur = self._check_walk(t, a)
            self._plan_around_props(t, a)
        if a.type in INTERACTIONS:
            if not (self.inter_action is a and a.type == "use_lever"):
                self.inter_action = a
            self._start_or_resume(t, a)
            return
        if self.lying:  # looking / waiting while lying down
            dyn = a.target if a.target and a.target.split(":", 1)[0] in ("prop", "char") else None
            self._open(self.posture, t, gaze_ref=dyn, gaze=None if dyn or not a.target else resolve(self.env, a.target),
                       gaze_mode=a.type, rest=True)
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
        dyn = a.target if a.target and a.target.split(":", 1)[0] in ("prop", "char") else None
        gaze = None if dyn or not a.target else resolve(self.env, a.target)
        if a.type == "wait_beat":
            clock = getattr(self, "beat_clock", None)
            if clock is None:
                self._fail(f"{self.cid}: wait_beat needs the scene's music (a beat grid)")
                self.beat_end = (t, -1)
            else:
                k, tb = clock.next(t, a.beats)
                self.beat_end = (tb, k)
            if self.seg.kind != "idle":
                self._open("idle", t, fight=self.fight_mode)
        elif a.type in ("idle", "look_around", "wait_grounded"):
            self._open("idle", t, look=(a.type == "look_around"), fight=self.fight_mode and a.type == "idle")
        elif a.type in ("look_at", "notice"):
            self._open("idle", t, gaze=gaze, gaze_mode=a.type, gaze_target=a.target, gaze_ref=dyn)
            if a.type == "notice":
                self.emit(Event(t + NOTICE_DOUBLE_TAKE, "notice", self.cid, {"target": a.target}))
        elif a.type == "point":
            self._open("point", t, gaze=gaze, gaze_target=a.target)
            self.emit(Event(t + 0.25, "point", self.cid, {"target": a.target}))
        elif a.type in ("walk_to", "run_to"):
            if self.seg.kind != "loco":
                self._open("loco", t, run=(a.type == "run_to"), style=a.style, gaze=gaze, gaze_ref=dyn, carry=self.carrying)
        elif a.type == "turn":
            self._open("turn", t, face_from=self.facing, face_to=float(a.face))
            self.emit(Event(t, "turn", self.cid, {"to": a.face}))
        elif a.type == "press":
            sw = next(s for s in self.env.switches if s.id == a.switch)
            bw = switch_world(self.env, sw)
            self._open("press", t, switch=sw.id, button=self.frame.to_frame(bw), pressed=False, hesitate=a.hesitate, gaze=bw)
        elif a.type == "duck_slide":
            d = 1.0 if a.target_x - self.s >= 0 else -1.0
            if self.v * d < 150.0:
                self.v = d * (a.speed or 430.0)
            self._open("slide", t, dir=d, s0=self.s, h0=self.h, target=a.target_x, v0=self.v)
            self.emit(Event(t, "slide_start", self.cid, {"surface": self.frame.tag, "speed": abs(self.v)}))
        elif a.type == "jump_to":
            sw = next((x for x in self.env.switches if x.id == a.switch), None) if a.switch else None
            gaze = switch_world(self.env, sw) if sw else None
            if abs(self.v) > 40:
                self.seg.data["prep"] = (t, t + JUMP_PREP)
                self.cur_prep = JUMP_PREP
            else:
                self._open("crouch", t, dur=JUMP_TO_PREP, gaze=gaze)
                self.cur_prep = JUMP_TO_PREP
        elif a.type == "grab_swing":
            # armed: waits (tense, eyes on the bar) until the body is airborne and the bar comes within reach
            self._open("idle", t, gaze=resolve(self.env, a.target), tense=True)
        elif a.type == "reach_exit":
            ex_id = a.target.split(":", 1)[1]
            plane, _ = self.frame.to_frame(exit_world(self.env, ex_id))
            d = 1.0 if plane - self.s >= 0 else -1.0
            if d != self.facing and abs(self.v) < 5:
                self.queue.appendleft(a)
                self.cur = ActionSpec(type="turn", character=self.cid, face=int(d))
                self._open("turn", t, face_from=self.facing, face_to=d)
                self.emit(Event(t, "turn", self.cid, {"to": int(d)}))
                return
            self.exit = {"id": ex_id, "plane": plane, "dir": d, "beyond": plane + d * 300.0, "crossed": False}
            self._open("loco", t, run=False, style="normal", gaze=exit_world(self.env, ex_id), exit=ex_id)
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
        elif a.type == "wait_beat":
            if t >= self.beat_end[0] - 1e-9:  # the next action starts on the beat (to the 240 Hz step)
                self.emit(Event(t, "beat_wait_end", self.cid, {"beat": self.beat_end[1], "target": self.beat_end[0]}))
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
        elif a.type in COMBAT:
            self._tick_combat(t, dt, a)
            if self.cur is not a:
                if self.mode == "grounded":
                    self._place(t)
                return
        elif a.type in ACRO:
            self._tick_acro(t, dt, a)
            if self.cur is not a:
                if self.mode == "grounded":
                    self._carry_tick()
                    self._place(t)
                return
        elif a.type in INTERACTIONS:
            self._tick_interaction(t, dt, a)
            if self.cur is not a:  # the interaction finished or handed over (placement already done)
                self._carry_tick()
                if self.mode == "grounded":
                    self._place(t)
                return
        elif a.type == "jump":
            self.s += self.v * dt
            if tau >= JUMP_PREP:
                self._takeoff(t, a)
                return
        elif a.type == "jump_to":
            self.s += self.v * dt
            if tau >= self.cur_prep:
                self._takeoff_to(t, a)
                return
        elif a.type == "duck_slide":
            self._slide(t, dt, a)
        elif a.type == "grab_swing":
            pass  # armed; holds until support is lost
        elif a.type == "reach_exit":
            self._reach_exit(t, dt, a)
        if self._edge_check(t):
            return
        self._carry_tick()
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
        carry = nxt is not None and (nxt.type in ("jump", "duck_slide") or (nxt.type in ("walk_to", "run_to") and (nxt.target_x - a.target_x) * direction > 0))
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

    def _slide(self, t: float, dt: float, a: ActionSpec) -> None:
        """Feet-first slide: hips drop, friction slows the body (never below SLIDE_VMIN until the end mark), then the
        character rises straight into the next action (a run) carrying its speed."""
        seg = self.seg
        d = seg.data["dir"]
        tau = t - seg.t0
        u = clamp(tau / SLIDE_DROP, 0.0, 1.0)
        e = u * u * (3 - 2 * u)
        self.h = seg.data["h0"] + (SLIDE_H - seg.data["h0"]) * e
        sp = abs(self.v)
        if tau > SLIDE_DROP:
            sp = max(SLIDE_VMIN, sp - SLIDE_DECEL * dt)
        self.v = d * sp
        self.s += self.v * dt
        if (self.s - a.target_x) * d >= 0:
            self.emit(Event(t, "slide_end", self.cid, {"surface": self.frame.tag, "speed": sp}))
            self.overlay = {"t": t, "h0": self.h, "v0": 260.0}  # spring back up to standing height while running on
            self._next_action(t)
            if self.seg.kind == "loco":
                self.seg.data["from_slide"] = True

    def _reach_exit(self, t: float, dt: float, a: ActionSpec) -> None:
        ex = self.exit
        door = self.doors.get(ex["id"], {})
        is_open = door.get("open_t") is not None and t >= door["open_t"] + 0.45
        d = ex["dir"]
        pause = a.duration or 0.0  # reach_exit.duration: stop at the threshold and look back at the room first
        if ex.get("paused") is not None:
            if t - ex["paused"] < pause:  # standing in the doorway, looking back
                self.v = 0.0
                return
            if self.seg.kind == "idle":
                self._open("loco", t, run=False, style="normal", gaze=exit_world(self.env, ex["id"]), exit=ex["id"])
        if pause > 0 and ex.get("paused") is None:
            target = ex["plane"] - d * 34.0
        else:
            target = ex["beyond"] if is_open else ex["plane"] - d * 45.0  # wait at the threshold until the door is open
        speed = a.speed or 150.0
        remaining = (target - self.s) * d
        v_des = min(speed, math.sqrt(2 * 600.0 * max(remaining, 0.0)))
        cur = self.v * d
        cur = min(cur + 500.0 * dt, v_des) if cur < v_des else max(cur - 650.0 * dt, v_des)
        self.v = cur * d
        self.s += self.v * dt
        if not ex["crossed"] and (self.s - ex["plane"]) * d > 0:
            ex["crossed"] = True
            self.emit(Event(t, "exit_reached", self.cid, {"exit": ex["id"]}))
        if pause > 0 and is_open and ex.get("paused") is None and remaining < 0.4:
            ex["paused"] = t
            self.v = 0.0
            hw, rh = self.env.room.width / 2, self.env.room.height
            back = next(((o.center[0], o.center[1]) for o in self.env.obstacles if o.kind == "bar"), (0.0, rh / 2))
            self._open("idle", t, look_back=True, gaze=back, pause=pause)
            self.emit(Event(t, "look_back", self.cid, {"exit": ex["id"]}))
        elif is_open and remaining < 0.4 and (pause == 0 or ex.get("paused") is not None):
            self.s, self.v = ex["beyond"], 0.0
            self._next_action(t)

    def _shoulder_world(self) -> Vec:
        st = self.world.state(self.cid)
        up = v_rot((0.0, self.shoulder_up), st.angle)
        return (st.pos[0] + up[0], st.pos[1] + up[1])

    def _takeoff_to(self, t: float, a: ActionSpec) -> None:
        """Ballistic jump aimed at a landing point `target_x` on the current surface with apex height `height`."""
        g = self.gravity.at(t)
        gm = math.hypot(*g)
        vn = math.sqrt(2 * gm * a.height)
        # landing surface: `onto` a structure top, else the floor when jumping off a structure, else this surface
        dest = self._top_of(a.onto, a.target_x) if a.onto else (self.frames["floor"] if self.frame.owner is not None else self.frame)
        dh = (dest.origin[1] - self.frame.origin[1]) if dest is not self.frame else 0.0
        if dest is not self.frame and not (dest.lo - 1.0 <= a.target_x <= dest.hi + 1.0):
            self._fail(f"{self.cid}: jump_to target_x {a.target_x:.0f} is off '{dest.tag}' (x {dest.lo:.0f}..{dest.hi:.0f})")
        if dh > a.height - 12.0:
            self._fail(f"{self.cid}: jump_to apex {a.height:.0f} cannot clear the {dh:.0f} rise onto '{dest.tag}' (use height > {dh + 12:.0f})")
            dh = a.height - 12.0
        T = (vn + math.sqrt(max(0.0, vn * vn - 2 * gm * dh))) / gm
        vt = (a.target_x - self.s) / T
        tan, nrm = self.frame.tangent, self.frame.normal
        vel = (tan[0] * vt + nrm[0] * vn, tan[1] * vt + nrm[1] * vn)
        self.world.set_dynamic(self.cid, vel, 0.0, MASS, self.moment)
        self.mode = "airborne"
        sw = next((x for x in self.env.switches if x.id == a.switch), None) if a.switch else None
        st = self.world.state(self.cid)
        sgn = 0.0 if not a.flip else (-self.facing if a.flip == "front" else self.facing)
        self.air = {"intent": "jump", "t0": t, "switch": sw.id if sw else None, "button": switch_world(self.env, sw) if sw else None,
                    "T": T, "flip": a.flip, "sgn": sgn, "ang0": st.angle}
        self._open("airborne", t, intent="jump", button=self.air["button"], target_x=a.target_x, flip=a.flip, T=T, onto=dest.tag)
        self.cur = None
        self.emit(Event(t, "takeoff", self.cid, {"surface": self.frame.tag, "speed": vt, "apex": a.height, "onto": dest.tag}))
        if a.flip:
            self.emit(Event(t, "flip", self.cid, {"dir": a.flip}))

    def _try_grab(self, t: float) -> bool:
        if not self.queue or self.queue[0].type != "grab_swing":
            return False
        a = self.queue[0]
        B = bar_world(self.env, a.target.split(":", 1)[1])
        sh = self._shoulder_world()
        dist = math.dist(sh, B)
        prev = self.air.get("bar_dist")
        self.air["bar_dist"] = dist
        st = self.world.state(self.cid)
        loc = v_rot((B[0] - st.pos[0], B[1] - st.pos[1]), -st.angle)  # bar in the body frame (+y = toward the head)
        # tumble feet-first (upright for the new gravity, the same cartoon air control as the landing brace) with the
        # arms reaching overhead: the hands close on the bar as it passes above the shoulders
        # orient for the gravity being rotated TO (an in-progress transition's end state), not the passing direction
        t_end = next((tr.t_start + tr.duration for tr in self.gravity.transitions if tr.t_start <= t < tr.t_start + tr.duration), t)
        g = self.gravity.direction(t_end)
        want = math.atan2(-g[1], -g[0]) - math.pi / 2
        err = wrap_angle(want - st.angle)
        hw_, rh_ = self.env.room.width / 2, self.env.room.height
        clearance = min(st.pos[0] + hw_, hw_ - st.pos[0], st.pos[1], rh_ - st.pos[1])
        if clearance < 125.0:  # not enough room to turn over yet: fall clear of the surfaces first
            err = 0.0
            self.world.set_angular_velocity(self.cid, st.angvel)
        if err != 0.0 and abs(abs(err) - math.pi) < 0.35:  # half a turn away: tumble the way with more free space for the head
            hw, rh = self.env.room.width / 2, self.env.room.height
            top = self.cap_b[1] + CAPSULE_R
            room = []
            for sgn in (1.0, -1.0):
                hx, hy = v_rot((0.0, top), st.angle + sgn * math.pi / 2)
                x, y = st.pos[0] + hx, st.pos[1] + hy
                room.append(min(x + hw, hw - x, y, rh - y))
            err = abs(err) if room[0] >= room[1] else -abs(err)
        if clearance >= 125.0:
            self.world.set_angular_velocity(self.cid, clamp(9.0 * err, -11, 11))
        if dist <= GRAB_REACH * self.arm_reach and loc[1] >= self.shoulder_up + 0.6 * self.arm_reach:  # overhead, near-straight arms
            self.queue.popleft()
            self._grab(t, a, B)
            return True
        if prev is not None and dist > prev and dist > 3 * self.arm_reach and t - self.air["t0"] > 0.3:
            self.queue.popleft()  # passed the bar without reaching it: give up, fall and brace
            self.emit(Event(t, "grab_missed", self.cid, {"bar": a.target}))
        return False

    def _grab(self, t: float, a: ActionSpec, B: Vec) -> None:
        st = self.world.state(self.cid)
        local = self.world.add_pin(self.cid, B)
        # inelastic catch: bent arms and shoulders absorb part of the impact (the body keeps CATCH_KEEP of its velocity)
        self.world.set_dynamic(self.cid, (st.vel[0] * CATCH_KEEP, st.vel[1] * CATCH_KEEP), st.angvel * CATCH_KEEP, MASS, self.moment)
        g = self.gravity.direction(t)
        self.mode = "swing"
        self.brace, self.ttc = 0.0, -1.0
        th = self._swing_angle(B, g)
        self.swing = {"bar": a.target, "B": B, "t0": t, "a": a, "theta": th, "passes": 0, "local": local,
                      "half_amp": abs(th), "last_amp": 0.0, "work": 0.0}
        look_to = exit_world(self.env, self.env.exits[0].id) if self.env.exits else None
        self._open("swing", t, bar=a.target, anchor=B, grip_local=local, pumps=[], work=[(t, 0.0)], hang=a.duration or 0.0,
                   look_to=look_to)
        self.cur = None
        self.emit(Event(t, "grab", self.cid, {"bar": a.target, "point": B, "speed": math.hypot(*st.vel),
                                              "speed_after": math.hypot(*st.vel) * CATCH_KEEP}))

    def _swing_angle(self, B: Vec, gdir: Vec) -> float:
        st = self.world.state(self.cid)
        r = (st.pos[0] - B[0], st.pos[1] - B[1])
        return math.atan2(gdir[0] * r[1] - gdir[1] * r[0], gdir[0] * r[0] + gdir[1] * r[1])  # + = CCW of hanging

    def _swing(self, t: float, dt: float, g: Vec) -> None:
        S = self.swing
        a = S["a"]
        gm = math.hypot(*g) or 1.0
        th = self._swing_angle(S["B"], (g[0] / gm, g[1] / gm))
        side = float(a.face or 1)
        dth = th - S["theta"]
        if S["theta"] * side < 0 <= th * side:
            S["passes"] += 1  # passed the bottom moving toward the release side
        if dth * S.get("dth", dth) < 0:  # turning point: amplitude of the half swing just completed
            S["last_amp"] = S["half_amp"]
            S["half_amp"] = 0.0
        S["half_amp"] = max(S["half_amp"], abs(th))
        S["dth"] = dth
        S["theta"] = th
        # pumping: kick through the bottom of the arc (muscular work, booked so QA can account for it) until the
        # swing is big enough to release
        target = math.radians(a.release_deg + 12.0)
        hang = max(0.12, a.duration or 0.0)  # grab_swing.duration: dangle (and look) before starting to pump
        pumping = S["last_amp"] < target and abs(th) < math.radians(30.0) and abs(dth) > 1e-6 and t - S["t0"] > hang
        segd = self.seg.data
        if pumping:
            st = self.world.state(self.cid)
            r = (st.pos[0] - S["B"][0], st.pos[1] - S["B"][1])
            rn = math.hypot(*r) or 1.0
            tdir = (-r[1] / rn, r[0] / rn)  # CCW tangent
            sgn = 1.0 if (st.vel[0] * tdir[0] + st.vel[1] * tdir[1]) >= 0 else -1.0
            self.world.apply_impulse(self.cid, (tdir[0] * sgn * MASS * PUMP_ACC * dt, tdir[1] * sgn * MASS * PUMP_ACC * dt))
            S["work"] += PUMP_ACC * dt * abs(st.vel[0] * tdir[0] + st.vel[1] * tdir[1])
            if not segd["pumps"] or segd["pumps"][-1][1] < t - 1.5 * dt:
                segd["pumps"].append([t, t])
            segd["pumps"][-1][1] = t
        segd["work"].append((t, S["work"]))
        # dismount: let go at the top of the swing on the release side (velocity ~ 0: a clean, predictable drop)
        if S["passes"] >= a.swings and th * side >= math.radians(a.release_deg) and dth * side <= 0:
            self.world.remove_pin(self.cid)
            st = self.world.state(self.cid)
            self.mode = "airborne"
            self.air = {"intent": "fall", "t0": t, "released": True}
            self._open("airborne", t, intent="fall", release=True)
            self.emit(Event(t, "release", self.cid, {"bar": S["bar"], "angle_deg": math.degrees(th), "speed": math.hypot(*st.vel)}))

    def _trigger_switch(self, t: float, switch_id: str) -> None:
        sw = next(s for s in self.env.switches if s.id == switch_id)
        start = t + sw.effect.delay
        g_now = self.gravity.at(start)
        mag = sw.effect.magnitude or math.hypot(*g_now)
        a0 = math.atan2(g_now[1], g_now[0])
        if sw.effect.rotate_deg is not None:
            sweep = math.radians(sw.effect.rotate_deg)
        else:
            d = sw.effect.to
            diff = math.atan2(d[1], d[0]) - a0
            if sw.effect.turn == "ccw":
                sweep = diff % (2 * math.pi)
            elif sw.effect.turn == "cw":
                sweep = -((-diff) % (2 * math.pi))
            else:
                sweep = wrap_angle(diff)
        a1 = a0 + sweep
        to = (math.cos(a1) * mag, math.sin(a1) * mag)
        to = tuple(0.0 if abs(c) < 1e-9 else c for c in to)
        self.gravity.schedule(GravityTransition(start, sw.effect.duration, to, cause=switch_id, sweep=sweep))
        rel0 = math.degrees(self.gravity.angle_unwrapped(start + sw.effect.duration) - math.atan2(self.gravity.initial[1], self.gravity.initial[0]))
        bw = switch_world(self.env, sw)
        self.emit(Event(t, "press_contact", self.cid, {"switch": switch_id, "point": bw}))
        self.emit(Event(t, "switch_activated", self.cid, {"switch": switch_id}))
        self.emit(Event(start, "gravity_shift", self.cid, {"from": g_now, "to": to, "duration": sw.effect.duration, "switch": switch_id,
                                                          "rel_prev_deg": math.degrees(sweep), "rel_original_deg": rel0}))

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
            self._carried = self.cur  # the action carried through the fall (a portal on the way ends it)
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
            if self.air.get("flip"):
                self._flip_control(t)
            else:
                self.world.set_angular_velocity(self.cid, clamp(10.0 * wrap_angle(self.frame.body_angle - st.angle), -12, 12))
            gd = self.gravity.direction(t)
            catches = hit is not None and -v_dot(gd, hit.normal) > 0.6  # only a surface that can hold the body is braced for
            self.brace = clamp(1 - self.ttc / 0.3, 0, 1) if catches and self.air.get("flip_u", 1.0) > 0.85 else 0.0
            sw = self.air.get("switch")
            if sw and not self.air.get("pressed"):
                d = math.dist(self._shoulder_world(), self.air["button"])
                prev = self.air.get("btn_d")
                self.air["btn_d"] = d
                reach = 0.97 * (self.arm_reach + self.rig.p.hand)
                # slap at the closest approach (or once well within reach), never at the edge of reach on the way up
                if d <= reach and (d <= 0.55 * reach or (prev is not None and d > prev)):
                    self.air["pressed"] = True
                    self.seg.data["press_t"] = t
                    self._trigger_switch(t, sw)
            return
        if self._try_grab(t):
            return
        if self.queue and self.queue[0].type == "grab_swing":
            self.brace = 0.0  # reaching for the bar, not bracing yet
            self.seg.data["reach_bar"] = resolve(self.env, self.queue[0].target)
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
        if nxt is not None and nxt.type == "roll":  # landing roll: the roll absorbs the drop
            self.mode = "grounded"
            self.queue.popleft()
            self.s, self.h, self.v = s, min(h, self.stand_h), vt
            self.cur, self.cur_t0 = nxt, t
            self.world.set_kinematic(self.cid, st.pos, fr.body_angle)
            self._start_roll(t, nxt, landing=approach)
            self._place(t)
            return
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
        heavy = clamp((L["approach"] - 700.0) / 800.0, 0.0, 1.0)  # 0 = light hop, 1 = hard landing
        h, hv = damped_spring(L["h0"], -L["approach"] * 0.9, self.stand_h, 11.0 - 2.0 * heavy, 0.55 + 0.25 * heavy, tau)
        h = min(max(42.0, h), self.stand_h + 1.0)  # never rebound above leg reach (feet stay planted)
        s = L["s0"] + L["vt"] * (1 - math.exp(-12 * tau)) / 12.0
        a, av = damped_spring(L["ang0"], L["w0"], 0.0, 8.0, 0.3, tau)
        self.s, self.h = s, h
        self.world.set_kinematic(self.cid, self.frame.to_world(s, h), self.frame.body_angle + a)
        name, perf = landing_clip(L["approach"])
        min_t = max(0.45, get_clip(name).length(perf) - 0.02)  # the landing performance plays out in full
        nxt = self.queue[0] if self.queue else None
        if nxt is not None and nxt.type in COMBAT and tau > 0.2 and abs(h - self.stand_h) < 12.0 and abs(a) < 0.1:
            # a fighter lands into the fighting stance: no relief beat, the next combat action takes over the absorption
            self.mode = "grounded"
            self.h = self.stand_h - 10.0
            self.fight_mode = True
            self.emit(Event(t, "recovered", self.cid, {"surface": self.frame.tag, "into": nxt.type}))
            self._open("idle", t, fight=True)
            self.cur = None
            self._place(t)
            return
        if tau > min_t and abs(h - self.stand_h) < 1.5 and abs(hv) < 15 and abs(a) < 0.02 and abs(av) < 0.15:
            self.mode = "grounded"
            self.h = self.stand_h
            self.emit(Event(t, "recovered", self.cid, {"surface": self.frame.tag}))
            big = L["approach"] > RECOVER_MIN_APPROACH
            self.hard_landings = getattr(self, "hard_landings", 0) + (1 if big else 0)
            self._open("idle", t, settle=big, settle_k=clamp(L["approach"] / 1300.0, 0.75, 1.25), variant=self.hard_landings - 1)
            if self.queue and self.queue[0].type == "wait_grounded":
                self.queue.popleft()
            # after a hard landing the relief beat (exhale, hands on knees, straighten up) always plays out
            self.cur = ActionSpec(type="idle", character=self.cid, duration=RECOVER_T) if big else None
            self.cur_t0 = t
            self._place(t)

    def finish(self, t_end: float) -> None:
        self.close(t_end)
