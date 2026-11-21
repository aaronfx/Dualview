"""Orbs and portals for the character controller (Milestone 4, simulation side).

Both act on the body's physical state, never on an animation: an orb changes the body's velocity (a mid-air jump, a
boost, a launch pad) and a portal moves the body to the linked portal with its velocity rotated into the exit's frame
(the speed is kept). What happens next (the flight, the landing, a walk carrying on) is the ordinary physics and
controller behaviour. The same portal mapping is used for props (scene runtime) and checked by QA.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..core.mathx import Vec, v_rot
from .acrobatics import _seg_dist

ORB_DEFAULT = {"jump": 130.0, "pad": 170.0, "boost": 320.0, "collect": 0.0}
ORB_REARM = 6.0  # the body must get this much further than touching before an orb fires again


class PortalMap:
    """The rigid map between two portal ends: entering A (moving against A's facing) leaves B along B's facing.

    Two isometries do that: a rotation, and a reflection (mirror about the travel direction, then rotate). In a side
    view the one that keeps "up" up is the natural one (two portals facing the same way mirror the body, like walking
    through a doorway, instead of turning it upside down), so that one is used; on a tie, the rotation."""

    def __init__(self, a, b):
        self.a, self.b = a, b
        ra, rb = math.radians(a.angle), math.radians(b.angle)
        self.na, self.nb = (math.cos(ra), math.sin(ra)), (math.cos(rb), math.sin(rb))
        th = rb - (ra + math.pi)  # rotates -nA onto nB
        self.rot = math.atan2(math.sin(th), math.cos(th))
        c, s_ = math.cos(self.rot), math.sin(self.rot)
        R = ((c, -s_), (s_, c))
        ni = (-self.na[0], -self.na[1])  # mirror about the travel direction n_in: M = 2 n n^T - I
        M = ((2 * ni[0] * ni[0] - 1, 2 * ni[0] * ni[1]), (2 * ni[0] * ni[1], 2 * ni[1] * ni[1] - 1))
        F = tuple(tuple(sum(R[i][k] * M[k][j] for k in range(2)) for j in range(2)) for i in range(2))
        self.mirror = F[1][1] > R[1][1] + 1e-9  # how much of "up" stays up
        self.A = F if self.mirror else R
        self._two_phi = math.atan2(F[1][0], F[0][0])

    def side(self, p: Vec) -> Tuple[float, float]:
        """(signed distance from A's plane, >0 on its open side; offset along the plane)."""
        dx, dy = p[0] - self.a.center[0], p[1] - self.a.center[1]
        return dx * self.na[0] + dy * self.na[1], -dx * self.na[1] + dy * self.na[0]

    def crossed(self, p0: Vec, p1: Vec, margin: float = 0.0) -> bool:
        d0, _ = self.side(p0)
        d1, u1 = self.side(p1)
        return d0 > 0.0 >= d1 and abs(u1) <= self.a.height / 2 - margin

    def vec(self, v: Vec) -> Vec:
        A = self.A
        return (A[0][0] * v[0] + A[0][1] * v[1], A[1][0] * v[0] + A[1][1] * v[1])

    def point(self, p: Vec) -> Vec:
        d = self.vec((p[0] - self.a.center[0], p[1] - self.a.center[1]))
        return (self.b.center[0] + d[0], self.b.center[1] + d[1])

    def angle(self, a: float) -> float:
        # a body's angle is that of its "up" axis minus 90 deg; a reflection maps a direction angle d to 2 phi - d
        return math.remainder(self._two_phi - a - math.pi, 2 * math.pi) if self.mirror else a + self.rot

    def spin(self, w: float) -> float:
        return -w if self.mirror else w


def portal_maps(env) -> Dict[str, PortalMap]:
    ps = {p.id: p for p in env.portals}
    return {p.id: PortalMap(p, ps[p.link]) for p in env.portals}


class ArcadeMixin:
    def _arcade_init(self) -> None:
        self.portal_maps = portal_maps(self.env)
        self.orb_inside: set = set()
        self.arcade = {"taken": {}}  # shared between characters by the runtime (a collected orb is gone for everyone)
        self._arc_prev: Optional[Vec] = None
        self.portal_log: List[Tuple[float, str]] = []  # (time, portal entered): cuts for the animator, camera and QA

    # ------------------------------------------------------------ per step (after the physics step)
    def _arcade_tick(self, t: float) -> None:
        if not (self.env.orbs or self.env.portals):
            return
        st = self.world.state(self.cid)
        p = st.pos
        prev, self._arc_prev = self._arc_prev, p
        if self.lying or self.mode in ("ragdoll", "swing", "falling") or self.ragdoll is not None:
            return
        if prev is not None and self.portal_maps:
            for pid, pm in self.portal_maps.items():
                if pm.crossed(prev, p, margin=8.0):
                    self._through_portal(t, pid, pm, prev, p)
                    return
        if self.env.orbs:
            self._orbs(t, st)

    def _through_portal(self, t: float, pid: str, pm: PortalMap, prev: Vec, p: Vec) -> None:
        from .controller import MASS, Event
        st = self.world.state(self.cid)
        dt = max(1e-6, getattr(self, "_dt", 1.0 / 240.0))
        if self.mode == "airborne":
            v = st.vel
        else:
            v = ((p[0] - prev[0]) / dt, (p[1] - prev[1]) / dt)
        p2, v2 = pm.point(p), pm.vec(v)
        ang2 = pm.angle(st.angle)
        self.emit(Event(t, "portal_enter", self.cid, {"portal": pid, "point": p, "speed": math.hypot(*v), "velocity": v}))
        # a walk into a portal ends there: the body carries its momentum out of the other end and the next action takes
        # over from wherever it comes out (a walk resumed toward its old target could lead straight back in)
        walking = self.cur if self.cur is not None and self.cur.type in ("walk_to", "run_to") else None
        carried = getattr(self, "_carried", None)
        if walking is None and self.queue and self.queue[0] is carried and carried.type in ("walk_to", "run_to"):
            walking = self.queue.popleft()  # the walk that ran off an edge (or a pad) into this portal ends here too
        self._carried = None
        self.cur = None
        if pm.mirror:
            self.facing = -self.facing
        self.portal_log.append((t, pid))
        if self.carrying:
            self.portal_log.append((t, f"prop:{self.carrying}"))
        self._arc_prev = p2
        support = self._support_at(p2, ang2, v2) if self.mode in ("grounded", "landing") else None
        if support is not None:  # the exit stands on a surface: the body runs straight on out of it
            fr, s2 = support
            vt = v2[0] * fr.tangent[0] + v2[1] * fr.tangent[1]
            self.frame, self.s, self.v, self.mode = fr, s2, vt, "grounded"
            if abs(vt) > 1.0:
                self.facing = 1.0 if vt > 0 else -1.0
            self.world.set_kinematic(self.cid, p2, fr.body_angle, (fr.tangent[0] * vt, fr.tangent[1] * vt))
            kind = self.seg.kind if self.seg.kind in ("loco", "idle") else "idle"
            data = {k: x for k, x in self.seg.data.items() if k in ("run", "style", "carry")} if kind == "loco" else {}
            self._open(kind, t, cut=True, portal=pid, **data)
            nxt = self.queue[0] if self.queue else None
            if walking is not None and abs(vt) > 5.0 and not (nxt is not None and nxt.type in ("walk_to", "run_to")):
                # nothing to run on to: the body brakes to a stop from its exit speed (no instant stop)
                dec = 1150.0 if walking.type == "run_to" else 650.0
                stop = self.s + math.copysign(vt * vt / (2 * dec) + 1.0, vt)
                self.queue.appendleft(walking.model_copy(update={"target_x": stop, "target": None, "speed": abs(vt)}))
            self.emit(Event(t, "portal_exit", self.cid, {"portal": pm.b.id, "from": pid, "point": p2, "speed": math.hypot(*v2),
                                                         "velocity": v2, "grounded": True}))
            return
        self.overlay = None
        self.world.set_kinematic(self.cid, p2, ang2)
        self.world.set_dynamic(self.cid, v2, pm.spin(st.angvel), MASS, self.moment)
        self.mode = "airborne"
        if abs(v2[0]) > 1.0:
            self.facing = 1.0 if v2[0] > 0 else -1.0
        # (t is the post-step time: the record taken at t already shows the body at the exit)
        if self.seg.kind == "airborne":  # already in flight: the same flight carries on out of the other end
            data = {k: x for k, x in self.seg.data.items() if k in ("intent", "drop", "flip", "T", "tuck", "onto", "orb")}
            data["t_origin"] = self.seg.data.get("t_origin", self.seg.t0)
            self.air = dict(self.air, portal=pid)
            self._open("airborne", t, cut=True, portal=pid, **data)
        else:
            self.air = {"intent": "jump", "t0": t, "T": 0.6, "portal": pid}
            self._open("airborne", t, intent="jump", T=0.6, cut=True, portal=pid, tuck=0.35)
        self.emit(Event(t, "portal_exit", self.cid, {"portal": pm.b.id, "from": pid, "point": p2, "speed": math.hypot(*v2),
                                                     "velocity": v2}))

    def _support_at(self, p: Vec, ang: float, v: Vec):
        """An upright surface the body would stand on at p (feet at its standing height above it), if any."""
        best = None
        for fr in self.frames.values():
            if abs(fr.normal[1] - 1.0) > 1e-6 or abs(math.remainder(ang - fr.body_angle, 2 * math.pi)) > 0.2:
                continue
            s, h = fr.to_frame(p)
            if (fr.bounded and not (fr.lo + 4.0 <= s <= fr.hi - 4.0)) or abs(h - self.h) > 10.0:
                continue
            if best is None or abs(h - self.h) < best[2]:
                best = (fr, s, abs(h - self.h))
        return None if best is None else best[:2]

    def _orbs(self, t: float, st) -> None:
        from .controller import MASS, Event
        neck = v_rot((0.0, self.shoulder_up), st.angle)
        a, b = st.pos, (st.pos[0] + neck[0], st.pos[1] + neck[1])
        feet = self.frame.to_world(self.s, 0.0) if self.mode in ("grounded", "landing") else None
        from .controller import BODY_R
        for orb in self.env.orbs:
            if orb.kind == "collect" and orb.id in self.arcade["taken"]:
                continue
            if orb.kind == "pad":
                if feet is None:
                    d = math.inf
                else:
                    d = math.dist(feet, orb.center) - orb.radius
            else:
                d = _seg_dist(a, b, orb.center, orb.center)[0] - orb.radius - BODY_R
            if d > 0.0:
                if d > ORB_REARM:
                    self.orb_inside.discard(orb.id)
                continue
            if orb.id in self.orb_inside:
                continue
            self.orb_inside.add(orb.id)
            power = orb.power if orb.power is not None else ORB_DEFAULT[orb.kind]
            g = self.gravity.at(t)
            gm = math.hypot(*g) or 1.0
            up = (-g[0] / gm, -g[1] / gm)
            v0 = st.vel if self.mode == "airborne" else (self.frame.tangent[0] * self.v, self.frame.tangent[1] * self.v)
            data = {"orb": orb.id, "kind": orb.kind, "point": tuple(orb.center), "power": power, "v_before": v0}
            if orb.kind == "collect":
                self.arcade["taken"][orb.id] = t
                self.emit(Event(t, "collect", self.cid, data))
                continue
            if orb.kind in ("jump", "boost") and self.mode != "airborne":
                continue  # a mid-air orb does nothing to a body on the ground
            if orb.kind == "pad" and self.mode not in ("grounded", "landing"):
                continue
            if orb.kind == "boost":
                d_ = 1.0 if (v0[0] if abs(v0[0]) > 1.0 else self.facing) > 0 else -1.0
                v1 = (v0[0] + d_ * power, v0[1])
                self.world.set_dynamic(self.cid, v1, st.angvel, MASS, self.moment)
            else:
                vn = math.sqrt(2.0 * gm * power)
                along = v0[0] * up[0] + v0[1] * up[1]
                v1 = (v0[0] + (vn - along) * up[0], v0[1] + (vn - along) * up[1])
                if self.mode != "airborne":  # a pad: the walk carries on after the landing
                    if self.cur is not None and self.cur.type in ("walk_to", "run_to"):
                        self.queue.appendleft(self.cur)
                        self._carried = self.cur
                    self.cur = None
                    self.world.set_kinematic(self.cid, st.pos, self.frame.body_angle)
                    self.mode = "airborne"
                self.world.set_dynamic(self.cid, v1, 0.0 if orb.flip else st.angvel, MASS, self.moment)
                T = 2.0 * vn / gm
                self.air = {"intent": "jump", "t0": t, "T": T, "flip": orb.flip, "orb": orb.id,
                            "sgn": 0.0 if not orb.flip else (-self.facing if orb.flip == "front" else self.facing),
                            "ang0": st.angle}
                self._open("airborne", t, intent="jump", T=T, flip=orb.flip, orb=orb.id)
                if orb.flip:
                    self.emit(Event(t, "flip", self.cid, {"dir": orb.flip}))
            data["v_after"] = v1
            self.emit(Event(t, f"orb_{orb.kind}", self.cid, data))

    def _pad_on_path(self, s0: float, s1: float) -> bool:
        """A launch pad on this surface between s0 and s1 (a walk over it is launched)."""
        for o in self.env.orbs:
            if o.kind != "pad":
                continue
            s, h = self.frame.to_frame(o.center)
            if abs(h) < o.radius + 6.0 and min(s0, s1) <= s <= max(s0, s1):
                return True
        return False

    # ------------------------------------------------------------ walks that end in a portal
    def _portal_on_path(self, s0: float, s1: float) -> Optional[float]:
        """The s at which a walk from s0 to s1 on this surface first enters a portal (pelvis height), if any."""
        best = None
        # the walk runs at this surface's height, and at the floor's once it steps off the end of a top
        frames = [self.frame] + ([self.frames["floor"]] if self.frame.bounded and "floor" in self.frames else [])
        for fr in frames:
            for pm in self.portal_maps.values():
                p0, p1 = fr.to_world(s0, self.stand_h), fr.to_world(s1, self.stand_h)
                if pm.crossed(p0, p1, margin=8.0):
                    d0, _ = pm.side(p0)
                    d1, _ = pm.side(p1)
                    s = s0 + (s1 - s0) * d0 / (d0 - d1)
                    if fr is not self.frame and fr.lo - 1.0 <= s <= fr.hi + 1.0 and self.frame.lo <= s <= self.frame.hi:
                        continue  # under this top: the walk never runs on the floor there
                    if best is None or abs(s - s0) < abs(best - s0):
                        best = s
        return best
