"""Physical interaction behaviours for the character controller (simulation side).

Characters act on props through *bounded forces* applied at their hand contacts. The physics engine decides the
outcome, not the script:
- `push` a prop. If it breaks away faster than the character can follow, contact is lost and the character
  stumbles and falls.
- `lift` a prop by hand. The effort is regulated toward a target rise but clamped to the character's strength, so
  too heavy simply does not come up.
- `use_lever`: pick up a bar, carry it, place it over a fulcrum under the load, and press the handle. Mechanical
  advantage does what the hands could not.

Characters lying prone can be pinned by a prop that comes to rest on them (detected from contact impulses). They can
`struggle`, `crawl_out` once the load is lifted, and `get_up` (alone or helped by another character's `offer_hand`).
`wait_for` and events tie two characters' timelines together; `gesture` makes them touch (fist bump, shoulder pat).

Every phase emits events (sound, camera, QA and the other characters react to them).
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from ..core.mathx import Vec, clamp
from ..scene.schema import ActionSpec

LIE_H = 12.0  # pelvis height above the floor when lying prone
FALL_T = 0.62  # standing -> prone
GETUP_T = 1.55  # prone -> standing, unassisted
CRAWL_SPEED = 74.0
PICKUP_T = 0.65
PLACE_T = 0.6
PRESS_T = 0.9
RELEASE_T = 0.5
GESTURE_T = 1.5
GESTURE_CONTACT = 0.55
OFFER_REACH_T = 0.55  # s: the helper's hand reaches out this long before it can be taken
HELP_WAIT = 4.0  # a helped get_up stops waiting for the hand after this long (the helper is stuck)
INTERACTIONS = ("push", "lift", "use_lever", "struggle", "crawl_out", "get_up", "offer_hand", "gesture", "wait_for")


def _smooth(u: float) -> float:
    u = clamp(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


class InteractionMixin:
    # ------------------------------------------------------------ helpers
    def _pid(self, ref: Optional[str]) -> str:
        return (ref or "").split(":", 1)[1]

    def _prop_pose(self, pid: str) -> Tuple[Vec, float]:
        st = self.world.state(pid)
        return st.pos, st.angle

    def _prop_point(self, pid: str, local: Vec) -> Vec:
        return self.world.body_to_world(pid, local)

    def _prop_extent_s(self, pid: str) -> Tuple[float, float]:
        """The prop's extent along the current support surface (its four corners projected)."""
        sp = self.props[pid]
        hx, hy = sp.size[0] / 2, sp.size[1] / 2
        ss = [self.frame.to_frame(self._prop_point(pid, (cx, cy)))[0] for cx in (-hx, hx) for cy in (-hy, hy)]
        return min(ss), max(ss)

    def _prop_end(self, pid: str, toward_s: float) -> Tuple[Vec, Vec]:
        """(end point on the bottom side, local coordinates) of a long prop's end nearest to `toward_s`."""
        sp = self.props[pid]
        hx, hy = sp.size[0] / 2, sp.size[1] / 2
        long_x = sp.size[0] >= sp.size[1]
        cands = []
        for sgn in (-1.0, 1.0):
            axis = (sgn * (hx - 6.0), 0.0) if long_x else (0.0, sgn * (hy - 6.0))
            for side in (-1.0, 1.0):  # the two faces across the long axis; keep the lower one (the underside)
                loc = (axis[0], side * hy) if long_x else (side * hx, axis[1])
                w = self._prop_point(pid, loc)
                cands.append((abs(self.frame.to_frame(w)[0] - toward_s), self.frame.to_frame(w)[1], w, loc))
        best_end = min(c[0] for c in cands)
        end = [c for c in cands if abs(c[0] - best_end) < 1e-6 or abs(c[0] - best_end) < 8.0]
        lo = min(end, key=lambda c: c[1])
        return lo[2], lo[3]

    def _event_seen(self, spec: Optional[str], t: float) -> bool:
        if not spec:
            return False
        from ..scene.goals import matches
        kind, _, body = spec.partition(":")
        t_from = self.cur_t0 - 1e-9 if kind == "next" else -1e9  # next: only events after the action started
        return any(t_from <= e.t <= t + 1e-9 and matches(body, e) for e in self.all_events)  # (with [key=value] filters)

    def _target_s(self, ref: str) -> float:
        kind, _, ref_id = ref.partition(":")
        if kind == "char":
            return self.others[ref_id].s
        if kind == "prop":
            return self.frame.to_frame(self.world.state(ref_id).pos)[0]
        from ..scene.targets import resolve
        return self.frame.to_frame(resolve(self.env, ref))[0]

    def _go(self, t: float, a: ActionSpec, dest: float, run: bool = False) -> bool:
        """Walk (or run) to `dest` first, then resume action `a`. Returns True if a walk was queued."""
        if abs(dest - self.s) <= 6.0:
            return False
        self.queue.appendleft(a)
        run = run or (a.speed is not None and a.speed > 250.0)  # urgent: run there
        self.queue.appendleft(ActionSpec(type="run_to" if run else "walk_to", character=self.cid, target_x=dest,
                                         speed=a.speed))
        self.cur = None
        self._next_action(t)
        return True

    def _face(self, t: float, a: ActionSpec, d: float) -> bool:
        if d == self.facing:
            return False
        self.queue.appendleft(a)
        self.cur = ActionSpec(type="turn", character=self.cid, face=int(d))
        self.cur_t0 = t
        self._open("turn", t, face_from=self.facing, face_to=d)
        self.emit(self._ev(t, "turn", {"to": int(d)}))
        return True

    def _ev(self, t: float, kind: str, data: Optional[Dict[str, Any]] = None):
        from .controller import Event
        return Event(t, kind, self.cid, dict(data or {}))

    # ------------------------------------------------------------ action start
    def _start_or_resume(self, t: float, a: ActionSpec) -> None:
        if a.type == "use_lever" and self.inter.get("bar") and self.inter_action is a and self.inter.get("phase") in ("to_bar", "carry"):
            I = self.inter
            if I["phase"] == "to_bar":
                bs = self.frame.to_frame(self.world.state(I["bar"]).pos)[0]
                side = 1.0 if self.s >= bs else -1.0
                if self._face(t, a, -side):
                    return
                I.update(phase="pickup", t1=t, rest=self.world.state(I["bar"]))
                self._open("lever", t, phase="pickup", bar=I["bar"], load=I["load"], t_phase=t)
                return
            self._lever_plan(I)
            if self._face(t, a, I["face"]) or self._go(t, a, I["stand"]):
                return
            self._lever_place_start(t)
            return
        self._start_interaction(t, a)

    def _start_interaction(self, t: float, a: ActionSpec) -> None:
        self.inter = {"t0": t}
        I = self.inter
        bad = None
        if self.lying and a.type not in ("struggle", "crawl_out", "get_up", "wait_for"):
            bad = f"{self.cid}: action '{a.type}' is not possible while lying down (use crawl_out / get_up first)"
        if (not self.lying and a.type in ("struggle", "crawl_out", "get_up")) or (self.posture == "supine" and a.type in ("struggle", "crawl_out")):
            bad = (f"{self.cid}: action '{a.type}' needs the character to be lying down at t={t:.2f}s, but it is "
                   f"standing (nothing has knocked it down by then)")
        if bad:
            if getattr(self, "strict", True):
                raise ValueError(bad)
            # non-strict (setup solver): the character stops here and the run is scored on what happened so far
            self.violation = bad
            I.update(phase="blocked")
            self._open(self.posture if self.lying else "idle", t, waiting=True)
            self.emit(self._ev(t, "action_impossible", {"action": a.type, "reason": bad}))
            return
        if a.type == "wait_for":
            self._open(self.posture if self.lying else "idle", t, waiting=True)
        elif a.type == "struggle":
            self._open("prone", t, struggle=True, gaze_prop=self.pinned_by)
        elif a.type == "push":
            pid = self._pid(a.target)
            lo, hi = self._prop_extent_s(pid)
            d = 1.0 if (lo + hi) / 2 >= self.s else -1.0
            face = lo if d > 0 else hi
            stand = face - d * (0.58 * self.arm_reach + 16.0)
            if self._face(t, a, d) or self._go(t, a, stand):
                return
            hand_h = min(self.stand_h + 0.6 * self.shoulder_up, self.frame.to_frame(self._prop_point(pid, (0, 0)))[1]
                         + 0.38 * self.props[pid].size[1])
            grip = self.frame.to_world(face, hand_h)
            I.update(prop=pid, dir=d, offset=face - self.s, grip_local=self.world.local_point(pid, grip), moved0=self.world.state(pid).pos)
            self._open("push", t, prop=pid, dir=d, grip_local=I["grip_local"], effort=a.effort, t_strain=t + 0.45)
            self.emit(self._ev(t, "push_start", {"prop": pid, "point": grip}))
        elif a.type == "lift":
            pid = self._pid(a.target)
            end_w, end_l = self._prop_end(pid, self.s)
            es = self.frame.to_frame(end_w)[0]
            d = 1.0 if es >= self.s else -1.0
            stand = es - d * (0.42 * self.arm_reach + 16.0)
            if self._face(t, a, d) or self._go(t, a, stand):
                return
            end_w, end_l = self._prop_end(pid, self.s)
            I.update(prop=pid, grip_local=end_l, y0=self.frame.to_frame(end_w)[1], rise_max=0.0, dur=a.duration or 2.4)
            self._open("lift", t, prop=pid, grip_local=end_l, effort=a.effort, dur=I["dur"])
            self.emit(self._ev(t, "lift_start", {"prop": pid, "point": end_w}))
        elif a.type == "use_lever":
            self._lever_start(t, a)
        elif a.type == "crawl_out":
            self._open("prone", t, struggle=True, gaze_prop=self.pinned_by, waiting_free=True)
            I.update(phase="wait", prop=self.pinned_by)
        elif a.type == "get_up":
            helper = self._pid(a.target) if a.target else None
            I.update(phase="up", helper=helper, s0=self.s)
            self._open("getup", t, helper=helper, assisted=helper is not None, back=self.posture == "supine", s0=self.s)
            self.emit(self._ev(t, "get_up_start", {"helper": helper}))
        elif a.type == "offer_hand":
            other = self._pid(a.target)
            oc = self.others[other]
            side = 1.0 if self.s >= oc.s else -1.0
            dest = oc.s + side * 0.95 * self.stand_h * 0.85
            if oc.posture == "supine":  # on his back he rises facing his feet: the hand is offered there, past them
                side = float(oc.facing)
                dest = oc.s + side * (0.95 * self.stand_h * 0.85 + 0.53 * oc.p_leg)
            if self._go(t, a, dest) or self._face(t, a, -side):
                return
            I.update(other=other, phase="offer")
            self._open("offer", t, other=other)
            self.emit(self._ev(t, "hand_offered", {"to": other}))
        elif a.type == "gesture":
            other = self._pid(a.target)
            oc = self.others[other]
            side = 1.0 if self.s >= oc.s else -1.0
            gap = a.distance if a.distance else {"fist_bump": 0.78, "shoulder_pat": 0.62, "wave": 1.4, "nudge": 0.5}[a.gesture] * self.stand_h
            dest = oc.s + side * gap
            if self._go(t, a, dest) or self._face(t, a, -side):
                return
            I.update(other=other)
            self._open("gesture", t, other=other, gesture=a.gesture, push=(a.gesture == "nudge" and a.reaction == "stagger"))
            self.emit(self._ev(t, "gesture_start", {"gesture": a.gesture, "with": other}))

    # ------------------------------------------------------------ per-step behaviour
    def _tick_interaction(self, t: float, dt: float, a: ActionSpec) -> None:
        I = self.inter
        tau = t - self.cur_t0
        if I.get("phase") == "blocked":
            return
        if a.type == "wait_for":
            if self._event_seen(a.until, t) or (a.duration and tau >= a.duration):
                self._next_action(t)
        elif a.type == "struggle":  # with `until` it waits for the event (duration, if given, is then a cap)
            if (a.until and self._event_seen(a.until, t)) or (a.duration and tau >= a.duration) or (not a.until and tau >= 1.5):
                self._next_action(t)
        elif a.type == "push":
            self._push_tick(t, dt, a, tau)
        elif a.type == "lift":
            self._lift_tick(t, dt, a, tau)
        elif a.type == "use_lever":
            self._lever_tick(t, dt, a, tau)
        elif a.type == "crawl_out":
            self._crawl_tick(t, dt, a)
        elif a.type == "get_up":
            self._getup_tick(t, dt, a)
        elif a.type == "offer_hand":
            oc = self.others[I["other"]]
            if I["phase"] == "offer" and getattr(oc, "inter", {}).get("phase") == "pulled":
                I["phase"] = "pull"
                self.seg.data["pull_t"] = t
            if any(e.type == "stood_up" and e.character == I["other"] and e.t <= t for e in self.all_events) or tau > 9.0:
                self._next_action(t)
        elif a.type == "gesture":
            if tau >= GESTURE_CONTACT and not I.get("touched"):
                I["touched"] = True
                oc = self.others[I["other"]]
                mid = ((self.world.state(self.cid).pos[0] + self.world.state(oc.cid).pos[0]) / 2,
                       self.frame.to_world(self.s, self.stand_h + self.shoulder_up * 0.7)[1])
                if a.gesture == "nudge" and a.reaction == "stagger":
                    # Deliberate push: only a nearby upright, unoccupied actor
                    # can yield. A missed contact must not fabricate a reaction.
                    from .acrobatics import BODY_PASS_Z, BODY_GAP
                    gap = abs(oc.s - self.s)
                    if (oc.mode == "grounded" and not oc.lying and not oc._gone()
                            and oc.frame is self.frame and abs(oc.z - self.z) < BODY_PASS_Z
                            and BODY_GAP - 2 <= gap <= self.arm_reach + 18
                            and not oc.carrying and (oc.cur is None or oc.cur.type == "idle")):
                        direction = math.copysign(1.0, oc.s - self.s)
                        # Native lane allocator; no instantaneous displacement.
                        bands = [(self.cid, self.z, 40.0)]
                        bands += [(cid, other.z, BODY_PASS_Z / 2)
                                  for cid, other in self.others.items()
                                  if cid not in (self.cid, oc.cid) and abs(other.s - oc.s) < 120]
                        bands += oc._props_in_path(oc.s, oc.s + direction * 65.0)
                        lane = oc._free_lane(bands)
                        self.emit(self._ev(t, "nudge", {"with": oc.cid, "point": mid}))
                        oc._receive(t, self.cid, "nudge", "stagger", 0.35, direction, "body", mid)
                        I["push_contact"] = True
                        if lane is not None:
                            oc.z_target = lane
                        oc.emit(oc._ev(t, "nudge_reaction", {"by": self.cid, "lane": lane}))
                    else:
                        self.emit(self._ev(t, "nudge_missed", {"with": oc.cid}))
                else:
                    self.emit(self._ev(t, a.gesture, {"with": I["other"], "point": mid}))
            if a.gesture == "nudge" and a.reaction == "stagger":
                if tau >= 1.05:
                    oc = self.others[I["other"]]
                    if (I.get("push_contact") and abs(oc.z - self.z) >= 54.0
                            and (oc.cur is None or oc.cur.type == "idle")):
                        self.emit(self._ev(t, "nudge_clear", {"with": oc.cid, "depth_gap": abs(oc.z - self.z)}))
                        self._next_action(t)
                    elif tau >= 2.4 and not I.get("clearance_failed"):
                        # Fail closed: do not advance the queued run into a blocked route.
                        I["clearance_failed"] = True
                        self.emit(self._ev(t, "nudge_blocked", {"with": oc.cid}))
            elif tau >= GESTURE_T:
                self._next_action(t)

    # -- push: brace, strain (bounded force), follow; losing contact -> stumble and fall
    def _push_tick(self, t: float, dt: float, a: ActionSpec, tau: float) -> None:
        I = self.inter
        pid, d = I["prop"], I["dir"]
        lo, hi = self._prop_extent_s(pid)
        face = lo if d > 0 else hi
        if tau >= 0.45:
            ramp = _smooth((tau - 0.45) / 0.8)
            tremble = 1.0 + 0.04 * math.sin(2 * math.pi * 7.5 * tau)
            F = a.effort * self.strength * ramp * tremble
            tan = self.frame.tangent
            self.world.apply_force(pid, (tan[0] * F * d, tan[1] * F * d), self._prop_point(pid, I["grip_local"]))
        want = face - I["offset"]
        step = clamp(want - self.s, -95.0 * dt, 95.0 * dt)  # a heavy push moves at most at a shuffle
        self.v = step / dt
        self.s += step
        if (want - self.s) * d > 16.0:  # it got away
            st = self.world.state(pid)
            self.emit(self._ev(t, "push_lost", {"prop": pid, "speed": math.hypot(*st.vel), "point": st.pos}))
            self._fall_prone(t, d, abs(self.v) + 40.0)
            return
        if a.duration and tau >= a.duration:
            self.emit(self._ev(t, "push_end", {"prop": pid}))
            self._next_action(t)
        elif tau > 4.0 and math.dist(self.world.state(pid).pos, I["moved0"]) < 3.0:
            self.emit(self._ev(t, "push_fail", {"prop": pid}))
            self._next_action(t)

    # -- falling forward to prone (kinematic, so falling bodies and props collide with it)
    def _fall_prone(self, t: float, d: float, v0: float) -> None:
        self.inter = {"t0": t, "phase": "fall", "s0": self.s, "dir": d, "v0": v0}
        self.cur = ActionSpec(type="idle", character=self.cid, note="falling")  # the push action is over
        self.cur_t0 = t
        self.mode = "falling"
        self.world.set_solid_to_props(self.cid, True)  # a falling / lying body is something props can land on
        self._open("fall", t, dir=d, s0=self.s)

    def _falling(self, t: float, dt: float) -> None:
        I = self.inter
        u = clamp((t - I["t0"]) / FALL_T, 0.0, 1.0)
        d = I["dir"]
        e = u * u  # gravity: slow start, fast finish
        self.body_tilt = (math.pi / 2) * e
        lean_len = self.stand_h
        self.s = I["s0"] + d * (I["v0"] * 0.12 * u + 0.55 * lean_len * math.sin(self.body_tilt))
        self.h = max(LIE_H, self.stand_h * math.cos(self.body_tilt) + LIE_H * e)
        self._place(t)
        if u >= 1.0:
            self.mode = "grounded"
            self.posture = "prone"
            self.body_tilt = math.pi / 2
            self.h = LIE_H
            self.v = 0.0
            self.emit(self._ev(t, "body_fall", {"point": self.frame.to_world(self.s, 0.0), "normal_speed": 520.0}))
            self._open("prone", t)
            self.cur = None
            self._place(t)

    # -- pinned detection (after each physics step while prone)
    def _check_pinned(self, t: float) -> None:
        heavy = [pid for pid, sp in self.props.items() if sp.collide_characters and sp.mass >= 20.0 and pid not in self.world.inactive]
        on = None
        for pid in heavy:
            touch, imp = self.world.touching(self.cid, pid, vertical_only=True)
            if touch and imp > 1.0:
                on = pid
                break
        if on is not None:
            self.free_t = None
            if self.pinned_by is None:
                if self.unpinned_t is not None and t - self.unpinned_t < 0.3:  # settling bounce, not a new event
                    self.pinned_by = on
                    return
                self.pinned_by = on
                self.emit(self._ev(t, "pinned", {"by": on, "point": self.world.state(on).pos}))
                if self.seg.kind == "prone":
                    self.seg.data["pinned"] = True
        elif self.pinned_by is not None:
            self.free_t = self.free_t or t
            if t - self.free_t > 0.2:
                self.emit(self._ev(t, "load_off", {"by": self.pinned_by}))
                self.pinned_by = None
                self.unpinned_t = t

    def _heavy_props(self):
        return [pid for pid, sp in self.props.items() if sp.collide_characters and sp.mass >= 20.0 and pid not in self.world.inactive]

    def _nearest_heavy(self) -> Optional[str]:
        best, bd = None, 1e9
        for pid in self._heavy_props():
            lo, hi = self._prop_extent_s(pid)
            d = 0.0 if lo <= self.s <= hi else min(abs(lo - self.s), abs(hi - self.s))
            if d < bd and d < self.stand_h:
                best, bd = pid, d
        return best

    def _load_incoming(self, t: float) -> bool:
        """True while a heavy prop near the body is still coming down (falling or toppling), not while being lifted."""
        I = self.inter
        lo_b, hi_b = sorted((self.s - self.facing * (self.p_leg + 10.0), self.s + self.facing * self.stand_h * 0.55))
        moving = False
        for pid in self._heavy_props():
            st = self.world.state(pid)
            lo, hi = self._prop_extent_s(pid)
            near = hi >= lo_b - self.stand_h and lo <= hi_b + self.stand_h
            down = -(st.vel[0] * self.frame.normal[0] + st.vel[1] * self.frame.normal[1])  # speed toward the floor
            if near and (down > 20.0 or abs(st.angvel) > 0.8):
                moving = True
        if moving:
            I["still_t"] = None
            return True
        I["still_t"] = I.get("still_t") or t
        return t - I["still_t"] < 0.25  # settled for a moment

    # -- crawl out (waits while the load is still on)
    def _crawl_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        I = self.inter
        if I["phase"] == "wait":
            # a load still falling or settling near the body is waited out (crawling from under a post that has
            # not landed yet would be a race); then crawl once nothing rests on the body
            if self.pinned_by is None and not self._load_incoming(t):
                if I.get("prop") is None:
                    I["prop"] = self._nearest_heavy()
                I.update(phase="crawl", c0=t, s0=self.s)
                self._open("crawl", t, s0=self.s, prop=I.get("prop"))
                self.emit(self._ev(t, "crawl_start", {}))
            return
        tau = t - I["c0"]
        v = CRAWL_SPEED * _smooth(tau / 0.4)
        self.s += self.facing * v * dt
        self._place(t)
        feet = self.s - self.facing * (self.p_leg + 6.0)
        if not I.get("freed") and I.get("prop"):
            lo, hi = self._prop_extent_s(I["prop"])
            clear = feet > hi + 6.0 if self.facing > 0 else feet < lo - 6.0
            if clear or abs(self.s - I["s0"]) > 400:
                I["freed"] = True
                I["s_freed"] = self.s
                self.emit(self._ev(t, "freed", {"from": I["prop"]}))
        dist = a.distance or 0.0
        # keep going until clear by more than getting up moves the hips back (so the load cannot land on the feet)
        margin_ok = not I.get("freed") or abs(self.s - I["s_freed"]) >= 0.45 * self.p_leg + 8.0
        if (I.get("freed") or not I.get("prop")) and margin_ok and abs(self.s - I["s0"]) >= dist and tau > 0.6:
            self._open("prone", t, rest=True)
            self._next_action(t)

    # -- getting up (prone -> push-up -> kneel -> stand), optionally pulled up by a helper's hand
    def _getup_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        if self.posture == "supine":
            return self._getup_back_tick(t, dt, a)
        I = self.inter
        tau = t - self.cur_t0
        helper = I["helper"]
        if helper and I["phase"] == "up" and tau >= 0.75:
            hc = self.others[helper]
            if (getattr(hc, "inter", {}).get("phase") in ("offer", "pull") and hc.cur is not None and hc.cur.type == "offer_hand"
                    and t - hc.cur_t0 >= OFFER_REACH_T):  # the offered hand has finished reaching out
                I.update(phase="pulled", tp=t)
                self.seg.data["grab_t"] = t
                self.emit(self._ev(t, "hand_grab", {"with": helper}))
            else:
                tau = 0.75  # kneeling, reaching up, waiting for the hand
                I["wait"] = I.get("wait", 0.0) + dt
                if I["wait"] > HELP_WAIT or not self._help_coming(helper):
                    # the helper is not coming (no offer_hand left for us, or it is stuck): get up unaided
                    self.emit(self._ev(t, "help_missed", {"helper": helper, "waited": round(I["wait"], 2)}))
                    I.update(helper=None, solo_t0=t - 0.75)
                    helper = None
        fail = a.hesitate and not helper  # tries alone and cannot: up onto the hands and knees, then sinks back down
        if fail:
            up_t, dn_t = 0.9, 0.75
            k = 0.5 * GETUP_T * (_smooth(tau / up_t) if tau < up_t else 1.0 - _smooth((tau - up_t) / dn_t))
        elif helper and I["phase"] == "pulled":
            k = clamp(0.75 + (t - I["tp"]) * (GETUP_T - 0.75) / 0.85, 0.0, GETUP_T)
        elif helper:
            k = min(tau, 0.75)
        elif I.get("solo_t0") is not None:
            k = min(t - I["solo_t0"], GETUP_T)
        else:
            k = min(tau, GETUP_T)
        u = k / GETUP_T
        # body tilt (pi/2 prone -> 0 standing), pelvis height and pelvis travel (hips go back over the knees)
        tilt_keys = [(0.0, math.pi / 2), (0.22, 1.25), (0.48, 0.45), (0.7, 0.12), (1.0, 0.0)]
        h_keys = [(0.0, LIE_H), (0.22, 22.0), (0.48, 0.62 * self.p_leg), (0.7, 0.66 * self.p_leg), (1.0, self.stand_h)]
        back_keys = [(0.0, 0.0), (0.48, 0.38 * self.p_leg), (1.0, 0.42 * self.p_leg)]

        def interp(keys):
            for (u0, v0), (u1, v1) in zip(keys, keys[1:]):
                if u <= u1:
                    return v0 + (v1 - v0) * _smooth((u - u0) / (u1 - u0))
            return keys[-1][1]

        self.body_tilt = interp(tilt_keys)
        self.h = interp(h_keys)
        self.s = I["s0"] - self.facing * interp(back_keys)
        self.seg.data["u_rec"] = True
        self._place(t)
        if fail and tau >= up_t + dn_t:
            self.body_tilt, self.h = math.pi / 2, LIE_H
            self.inter["phase"] = "done"
            self.emit(self._ev(t, "get_up_failed", {}))
            self._open("prone", t)
            self._next_action(t)
            return
        if u >= 1.0:
            self.posture, self.body_tilt, self.h = "stand", 0.0, self.stand_h
            self.world.set_solid_to_props(self.cid, False)
            self.knocked = False
            self.inter["phase"] = "done"
            self.emit(self._ev(t, "stood_up", {"helper": helper}))
            self._next_action(t)

    def _help_coming(self, helper: str) -> bool:
        hc = self.others[helper]
        acts = ([hc.cur] if hc.cur is not None else []) + list(hc.queue)
        return any(x.type == "offer_hand" and x.target == f"char:{self.cid}" for x in acts)

    # -- lift by hand: regulated toward a target rise, clamped to strength (physics decides)
    def _lift_tick(self, t: float, dt: float, a: ActionSpec, tau: float) -> None:
        I = self.inter
        pid = I["prop"]
        grip = self._prop_point(pid, I["grip_local"])
        y = self.frame.to_frame(grip)[1]
        I["rise_max"] = max(I["rise_max"], y - I["y0"])
        dur = I["dur"]
        if 0.45 <= tau < dur - 0.4:
            want = I["y0"] + 30.0 * _smooth((tau - 0.45) / 0.9)
            st = self.world.state(pid)
            vy = st.vel[1]
            # effort: rises to a peak, then fatigue sets in
            env = _smooth((tau - 0.45) / 0.6) * (1.0 - 0.3 * _smooth((tau - 1.4) / 0.8))
            Fmax = a.effort * self.strength * env
            F = clamp(2600.0 * (want - y) * self.props[pid].mass / 10.0 - 40.0 * vy * self.props[pid].mass / 10.0
                      + self.props[pid].mass * 1568.0 * 0.5, 0.0, Fmax)
            n = self.frame.normal
            self.world.apply_force(pid, (n[0] * F, n[1] * F), grip)
            self.seg.data.setdefault("force", []).append((t, F / max(1.0, a.effort * self.strength)))
        if tau >= dur - 0.4 and not I.get("reported"):
            I["reported"] = True
            ok = I["rise_max"] >= 12.0
            self.emit(self._ev(t, "lift_ok" if ok else "lift_fail", {"prop": pid, "rise": round(I["rise_max"], 1), "point": grip}))
        if tau >= dur:
            self._next_action(t)

    # -- lever: pick up the bar, carry it, place it over the fulcrum under the load, press, hold, release
    def _lever_start(self, t: float, a: ActionSpec) -> None:
        I = self.inter
        bar, ful, load = self._pid(a.tool), self._pid(a.fulcrum), self._pid(a.target)
        I.update(bar=bar, ful=ful, load=load, phase="to_bar")
        bs = self.frame.to_frame(self.world.state(bar).pos)[0]
        side = 1.0 if self.s >= bs else -1.0
        stand = bs + side * 30.0
        if self._go(t, a, stand) or self._face(t, a, -side):
            return
        I.update(phase="pickup", t1=t, rest=self.world.state(bar))
        self._open("lever", t, phase="pickup", bar=bar, load=load, t_phase=t)

    def _carry_pose(self) -> Tuple[Vec, float]:
        c = self.frame.to_world(self.s + self.facing * 14.0, self.stand_h - 4.0)
        return c, self.frame.body_angle

    def _lever_plan(self, I: Dict[str, Any]) -> None:
        """Where the bar goes: tip under the load's nearest end, resting over the fulcrum, handle toward the user."""
        bar, ful, load = I["bar"], I["ful"], I["load"]
        fsp = self.props[ful]
        ftop = self._prop_point(ful, (0.0, fsp.size[1] / 2 + 2.0))
        fs, fh = self.frame.to_frame(ftop)
        end_w, _ = self._prop_end(load, fs)
        es, eh = self.frame.to_frame(end_w)
        tip_s = es + (6.0 if fs > es else -6.0)
        tip = (tip_s, eh - 3.0)
        dx, dy = fs - tip[0], fh - tip[1]
        n = math.hypot(dx, dy)
        ux, uy = dx / n, dy / n
        L = self.props[bar].size[0]
        center = (tip[0] + ux * L / 2, tip[1] + uy * L / 2)
        handle = (tip[0] + ux * (L - 8.0), tip[1] + uy * (L - 8.0))
        ang = math.atan2(uy, ux)
        I.update(place_center=self.frame.to_world(*center), place_angle=self.frame.body_angle + ang, fulcrum_pt=ftop,
                 handle_s=handle[0], handle_h=handle[1], stand=handle[0] + (16.0 if ux > 0 else -16.0), face=-1.0 if ux > 0 else 1.0,
                 handle_local=(L / 2 - 8.0, 0.0))

    def _lever_tick(self, t: float, dt: float, a: ActionSpec, tau: float) -> None:
        I = self.inter
        bar = I["bar"]
        ph = I["phase"]
        if ph == "pickup":
            u = (t - I["t1"]) / PICKUP_T
            if u >= 0.45:
                if not I.get("grabbed"):
                    I["grabbed"] = True
                    self.emit(self._ev(t, "pick_up", {"prop": bar, "point": self.world.state(bar).pos}))
                k = _smooth((u - 0.45) / 0.55)
                r = I["rest"]
                (cx, cy), ca = self._carry_pose()
                self.world.set_kinematic(bar, (r.pos[0] + (cx - r.pos[0]) * k, r.pos[1] + (cy - r.pos[1]) * k), r.angle + (ca - r.angle) * k)
            if u >= 1.0:
                self.carrying = bar
                self._lever_plan(I)
                I["phase"] = "carry"
                if self._face(t, a, 1.0 if I["stand"] > self.s else -1.0) or self._go(t, a, I["stand"]):
                    return
                self._lever_place_start(t)
        elif ph == "carry":
            self._lever_plan(I)
            if self._face(t, a, I["face"]) or self._go(t, a, I["stand"]):
                return
            self._lever_place_start(t)
        elif ph == "place":
            u = clamp((t - I["t1"]) / PLACE_T, 0.0, 1.0)
            k = _smooth(u)
            c0, a0 = I["from"]
            c1, a1 = I["place_center"], I["place_angle"]
            self.world.set_kinematic(bar, (c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k), a0 + (a1 - a0) * k)
            if u >= 1.0:
                self.carrying = None
                self.world.make_dynamic(bar)
                self.world.set_group([bar, I["ful"]], 7)
                self.world.add_pin(bar, I["fulcrum_pt"])
                self.emit(self._ev(t, "lever_place", {"prop": bar, "point": I["fulcrum_pt"]}))
                I.update(phase="press", t1=t, h0=I["handle_h"])
                self.seg.data.update(phase="press", t_phase=t)
                self.emit(self._ev(t, "lever_engage", {"prop": bar, "point": self._prop_point(bar, I["handle_local"])}))
        elif ph in ("press", "hold"):
            hp = self._prop_point(bar, I["handle_local"])
            h = self.frame.to_frame(hp)[1]
            u = clamp((t - I["t1"]) / PRESS_T, 0.0, 1.0)
            want = I["h0"] + (16.0 - I["h0"]) * _smooth(u)
            vy = self.world.state(bar).angvel
            Fmax = a.effort * self.strength * _smooth(u / 0.3)
            F = clamp(900.0 * (h - want) + 300.0 * vy, 0.0, Fmax)
            n = self.frame.normal
            self.world.apply_force(bar, (-n[0] * F, -n[1] * F), hp)
            if ph == "press" and u >= 1.0:
                I["phase"] = "hold"
                self.seg.data.update(phase="hold", t_phase=t)
            if ph == "hold" and ((a.until and self._event_seen(a.until, t)) or (not a.until and t - I["t1"] > (a.duration or 3.0))
                                 or t - I["t1"] > 12.0):
                I.update(phase="release", t1=t)
                self.seg.data.update(phase="release", t_phase=t)
                self.emit(self._ev(t, "lever_release", {"prop": bar, "point": hp}))
        elif ph == "release":
            if t - I["t1"] >= RELEASE_T:
                self._next_action(t)

    def _lever_place_start(self, t: float) -> None:
        I = self.inter
        st = self.world.state(I["bar"])
        I.update(phase="place", t1=t, **{"from": (st.pos, st.angle)})
        self._open("lever", t, phase="place", bar=I["bar"], load=I["load"], t_phase=t)

    def _carry_tick(self) -> None:
        if self.carrying is not None:
            if self.cur is not None and self.cur.type == "strike" and self.cur.move == "swing_weapon":
                return  # the swing poses the prop itself
            if self.props[self.carrying].kind == "glyph":
                self._pose_prop(self.carrying, *self._hold_pose(self.carrying), self._now)
            else:
                c, a = self._carry_pose()
                self.world.set_kinematic(self.carrying, c, a)
