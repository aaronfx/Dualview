"""Ledge catches, hanging and rescues (Milestone 6, simulation side).

- `catch_ledge` (armed behind a walk): a falling body whose hands pass within reach of a corner of the named top catches
  it and hangs from it (hands on the corner, body outside its end face). The catch absorbs the fall in a short dip.
- `hang`: holds on (until an event, a duration, or a rescue). `slip_at` makes the near hand slip off: the body drops a
  little and hangs by one hand.
- `pull_up` (the rescuer): walks to the edge above the hanging character, kneels, reaches down; the two hands meet at
  one point (`hand_grab`), then the rescuer leans back and the hanging body is pulled up and over the edge onto the top
  (the climb's own mantle), and both stand.

Everything is placed by the same geometry the climb uses (hands on the edge, hips outside the end face), so the
animation, QA and physics agree on where the hands are.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

from ..core.mathx import clamp
from ..scene.schema import ActionSpec

KNEEL_T, REACH_T, PULL_T = 0.45, 0.55, 1.25  # rescuer phases (s)
STEP_BACK = 0.55  # the rescuer steps back this far (fraction of standing height) while pulling, making room
STEP_WIN = (0.2, 0.75)  # ... during this part of the pull
HOLD_T = 0.5  # the two hands hold each other this long into the pull; then the pulled one's hands go onto the top


def grip_point(an_a, an_b, t: float):
    """Where two holding hands are: on the line between the shoulders, shared in proportion to the arms' reach (at the
    start of a pull both arms are straight)."""
    def sh(an):  # the real shoulder, from the pose without the grip (the two grips would otherwise depend on each other)
        an._no_grip = True
        try:
            return an.rig.world_joints(an.pose_at(t))["shoulder_n"]
        finally:
            an._no_grip = False
    a, b = sh(an_a), sh(an_b)
    ra = an_a.p.upper_arm + an_a.p.forearm + an_a.p.hand
    rb = an_b.p.upper_arm + an_b.p.forearm + an_b.p.hand
    u = ra / (ra + rb)
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
CATCH_DIP = 10.0  # how far the body drops past the hang point as the arms take the fall (units)


class RescueMixin:
    def _rescue_init(self) -> None:
        self.hang: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------ catching a ledge (while falling)
    def _armed_catch(self) -> Optional[ActionSpec]:
        for a in list(self.queue)[:2]:
            if a.type == "catch_ledge":
                return a
        return None

    def _try_catch(self, t: float) -> bool:
        a = self._armed_catch()
        if a is None:
            return False
        from .controller import Event
        st = self.world.state(self.cid)
        if st.vel[1] > 40.0:  # still rising
            return False
        oid = a.target.split(":", 1)[1]
        if oid in self.world.collapsed:
            return False
        F = self._top_of(a.target)
        sh = self._shoulder_world()
        top = F.origin[1]
        for corner, dc in ((F.lo, 1.0), (F.hi, -1.0)):
            out = (corner - sh[0]) * dc  # > 0: the shoulder is outside the end face
            dy = top - sh[1]
            if -12.0 <= out <= 0.75 * self.stand_h and -0.25 * self.arm_reach <= dy <= 1.05 * (self.arm_reach + self.rig.p.hand):
                self._catch(t, a, F, (corner, top), dc)
                self.emit(Event(t, "ledge_catch", self.cid, {"target": a.target, "point": (corner, top)}))
                return True
        return False

    def _catch(self, t: float, a: ActionSpec, F, E, dc: float) -> None:
        # the walk that was carried into the fall and the catch itself are done
        while self.queue and self.queue[0].type in ("walk_to", "run_to", "catch_ledge"):
            done = self.queue.popleft()
            if done.type == "catch_ledge":
                break
        sh, ar = self.shoulder_up, self.arm_reach
        hang_y = E[1] - (sh + 0.9 * ar)
        P2 = (E[0] - dc * 0.28 * self.stand_h, hang_y)
        self.frame = self.frames["floor"]
        fy = self.frame.origin[1]
        self.mode = "grounded"
        self.facing = dc
        self.v = 0.0
        self.s, self.h = P2[0], P2[1] - fy
        self.body_tilt = 0.0
        self.world.set_kinematic(self.cid, P2, self.frame.body_angle)
        self.hang = {"E": E, "dc": dc, "P2": P2, "t0": t, "top": F, "fy": fy, "slip_t": None, "release_t": None, "reach": None}
        nxt = self.queue[0] if self.queue else None
        if nxt is not None and nxt.type == "hang":
            self.queue.popleft()
            self.cur = nxt
        else:
            self.cur = ActionSpec(type="hang", character=self.cid)
        self.cur_t0 = t
        self._open_hang(t)

    def _open_hang(self, t: float, **extra) -> None:
        H = self.hang
        big = 1e6  # the hang lasts until something ends it
        self._open("climb", t, keys=[(0.0, H["P2"]), (1.0, H["P2"])], edge=H["E"], d=H["dc"], T=big,
                   times=[0.0, -0.3, -0.1, big, big + 0.42, big + 0.82, big + 1.18], hang=True, top_frame=H["top"].tag,
                   hanging=True, slip_t=H["slip_t"], **extra)

    # ------------------------------------------------------------ hanging
    def _hang_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        H = self.hang
        tau = t - H["t0"]
        dip = CATCH_DIP * math.exp(-5.0 * tau) * math.sin(min(tau, 0.6) / 0.6 * math.pi) if tau < 1.2 else 0.0
        drop = 0.0
        slip_at = a.slip_at
        if slip_at is None and a.until is not None and H["slip_t"] is None and self._event_seen(a.until, t):
            slip_at = tau  # slips the moment the `until` event happens (e.g. as the rescuer arrives)
        if slip_at is not None and H["slip_t"] is None and tau >= slip_at and H["release_t"] is None:
            H["slip_t"] = t
            self.seg.data["slip_t"] = t
            self.emit(Event(t, "hang_slip", self.cid, {"point": H["E"]}))
        if H["slip_t"] is not None:
            u = clamp((t - H["slip_t"]) / 0.25, 0.0, 1.0)
            drop = (a.distance or 14.0) * (u * u * (3 - 2 * u))
        x, y = H["P2"]
        self.s, self.h = x, y - H["fy"] - dip - drop
        self.world.set_kinematic(self.cid, self.frame.to_world(self.s, self.h), self.frame.body_angle)
        if H["release_t"] is None and a.duration is not None and tau >= a.duration:
            H["release_t"] = t  # scrambles up unaided
            self.emit(Event(t, "climb_start", self.cid, {"point": H["E"], "unaided": True}))
        if H["release_t"] is not None and t >= H["release_t"]:
            self._pulled_up(t)

    def _pulled_up(self, t: float) -> None:
        """Pulled up and over the edge: the climb's own pull-up and mantle, from the hang."""
        H = self.hang
        E, dc, fy = H["E"], H["dc"], H["fy"]
        top = E[1]
        x0, y0 = self.s, self.h + fy
        P4 = (E[0] - dc * 0.28 * self.stand_h, top - 0.05 * self.stand_h)
        P5 = (E[0] + dc * 0.22 * self.stand_h, top + 0.45 * self.stand_h)
        P6 = (E[0] + dc * 0.42 * self.stand_h, top + self.stand_h)
        times = [-0.3, -0.2, -0.1, 0.0, 0.5, 0.95, 1.3]
        T = times[6]
        keys = [(0.0, (x0, y0)), (times[4] / T, P4), (times[5] / T, P5), (1.0, P6)]
        tilt = [(0.0, 0.0), (times[4] / T, 0.35), (times[5] / T, 0.45), (1.0, 0.0)]
        self.inter = {"t0": t, "T": T, "keys": keys, "tilt": tilt, "frame": H["top"], "edge": E, "d": dc, "grab_t": -1.0,
                      "grabbed": True, "fy": fy, "pulled": True}
        self.cur = ActionSpec(type="climb", character=self.cid, target=f"obstacle:{H['top'].owner}")
        self.cur_t0 = t
        self._open("climb", t, keys=keys, edge=E, d=dc, T=T, times=times, hang=True, top_frame=H["top"].tag, pulled=True,
                   helper=H.get("helper"), M=(H["reach"][2] if H.get("reach") else E))
        self.hang = None

    # ------------------------------------------------------------ the rescuer
    def _start_pull_up(self, t: float, a: ActionSpec) -> None:
        from .controller import Event
        other = a.target.split(":", 1)[1]
        oc = self.others[other]
        H = getattr(oc, "hang", None)
        if H is None:  # not hanging (yet): wait for it
            self._open("idle", t, gaze_ref=a.target)
            self.inter = {"waiting": True}
            return
        E, dc = H["E"], H["dc"]
        F = H["top"]
        if self.frame is not F and self.frame.tag != F.tag:
            lo, hi = getattr(self, "_span_of", lambda G: (G.lo, G.hi))(self.frame)
            if not (self.frame.origin[1] == F.origin[1] and lo - 4 <= E[0] <= hi + 4):
                self._fail(f"{self.cid}: pull_up needs to stand on '{F.owner}' above {other} (on {self.frame.tag})")
                self._next_action(t)
                return
        dest = E[0] + dc * 0.62 * self.stand_h  # far enough back to kneel and lean right out over the edge
        if self._go(t, a, dest, run=True) or self._face(t, a, -dc):
            return
        M = (E[0] - dc * 0.1 * self.stand_h, E[1] - 0.02 * self.stand_h)  # where the hands meet, at the edge
        self.inter = {"other": other, "t0": t, "E": E, "dc": dc, "M": M, "grabbed": False, "released": False, "s0": dest}
        oc.hang["reach"] = (t + KNEEL_T, t + KNEEL_T + REACH_T, M)
        oc.hang["helper"] = self.cid
        oc.seg.data["reach"] = oc.hang["reach"]
        self._open("rescue", t, other=other, E=E, dc=dc, M=M, times=(KNEEL_T, KNEEL_T + REACH_T, KNEEL_T + REACH_T + PULL_T))
        self.emit(Event(t, "rescue_start", self.cid, {"with": other, "point": E}))

    def _pull_up_tick(self, t: float, dt: float, a: ActionSpec) -> None:
        from .controller import Event
        I = self.inter
        if I.get("waiting"):
            oc = self.others[a.target.split(":", 1)[1]]
            if getattr(oc, "hang", None) is not None:
                self._start_pull_up(t, a)
            return
        tau = t - I["t0"]
        oc = self.others[I["other"]]
        r = KNEEL_T + REACH_T
        u = clamp((tau - r - STEP_WIN[0] * PULL_T) / ((STEP_WIN[1] - STEP_WIN[0]) * PULL_T), 0.0, 1.0)
        self.s = I["s0"] + I["dc"] * STEP_BACK * self.stand_h * (u * u * (3 - 2 * u))  # stepping back with the pull
        if not I["grabbed"] and tau >= KNEEL_T + REACH_T:
            I["grabbed"] = True
            self.emit(Event(t, "hand_grab", self.cid, {"with": I["other"], "point": I["M"], "hold": HOLD_T}))
            if oc.hang is not None:
                oc.hang["release_t"] = t  # pulled from now on
        if tau >= KNEEL_T + REACH_T + PULL_T:
            self.emit(Event(t, "pulled_up", I["other"], {"by": self.cid, "point": I["E"]}))
            self._next_action(t)
