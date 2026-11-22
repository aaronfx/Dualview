"""Scene runtime: builds the physical world from a SceneSpec, runs the deterministic fixed-step simulation,
and exposes a pure `evaluate(t)` for rendering, QA and partial re-rendering.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..core.mathx import Vec
from ..motion.animator import Animator
from ..motion.controller import CharacterController, Event
from ..motion.frames import GroundFrame, room_frames
from . import glyphs, structures
from ..motion.secondary import DustField, ScarfSim
from ..physics.gravity import GravityField
from ..physics.world import PhysicsWorld
from ..rig.stickman import Pose, Proportions, StickmanRig
from .schema import CharacterSpec, EnvironmentSpec, ProjectSpec, SceneSpec
from .targets import exit_portal, exit_world, switch_world

DOOR_UNLOCK_S = 0.7  # seal bars retract
DOOR_OPEN_S = 0.6  # door panel slides open
DOOR_CLOSE_DELAY = 0.75  # the door closes behind the character...
DOOR_CLOSE_S = 0.5  # ...over this long

SIM_HZ = 240


BREAK_LOOSE = 30.0  # u/s: a prop with stick-slip friction switches to sliding friction only past this speed (hysteresis)


@dataclass
class PropState:
    id: str
    kind: str
    size: Vec
    pos: Vec
    angle: float
    z: float = 0.0
    depth: float = 60.0
    front: bool = False  # drawn in front of the characters (nearer the camera than the character plane)
    glyph: Optional[str] = None  # the glyph it is now (it may have morphed)
    morph: Optional[tuple] = None  # (from, to, u) while it is visibly changing shape


@dataclass
class RopeState:
    id: str
    a: Vec
    b: Vec
    length: float
    color: str
    snapped: bool = False


@dataclass
class FrameState:
    t: float
    poses: Dict[str, Pose]
    props: List[PropState]
    gravity: Vec
    gravity_label: str
    switch_glow: Dict[str, float]
    events_recent: List[Event]
    scarves: Dict[str, List[np.ndarray]] = field(default_factory=dict)
    dust: Optional[np.ndarray] = None
    dust_prev: Optional[np.ndarray] = None
    doors: Dict[str, Tuple[str, float]] = field(default_factory=dict)  # exit id -> (state, progress 0..1)
    ropes: List[RopeState] = field(default_factory=list)
    depth: Dict[str, float] = field(default_factory=dict)  # character id -> depth lane at this instant
    orbs_taken: Dict[str, float] = field(default_factory=dict)  # collected orb id -> when (Milestone 4)
    orb_fired: Dict[str, float] = field(default_factory=dict)  # orb id -> seconds since it last fired
    collapsed: set = field(default_factory=set)  # structures that have given way by now (Milestone 6)


@dataclass
class SimulationResult:
    duration: float
    frames: Dict[str, GroundFrame]
    gravity: GravityField
    animators: Dict[str, Animator]
    controllers: Dict[str, CharacterController]
    events: List[Event]
    prop_times: np.ndarray
    prop_tracks: Dict[str, np.ndarray]  # id -> (n, 3) x, y, angle
    static_segments: List[Tuple[str, Vec, Vec, float]]
    scarves: Dict[str, ScarfSim] = field(default_factory=dict)
    dust: Optional[DustField] = None
    doors: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)  # exit id -> state-machine times
    rope_snaps: Dict[str, float] = field(default_factory=dict)  # rope id -> time it broke
    rope_peak: Dict[str, float] = field(default_factory=dict)  # rope id -> highest tension seen (force units)
    prop_cuts: Dict[str, List[int]] = field(default_factory=dict)  # prop id -> first track samples after a portal
    orbs_taken: Dict[str, float] = field(default_factory=dict)
    morphs: Dict[str, List[dict]] = field(default_factory=dict)  # prop id -> its shape changes (Milestone 5)
    broken: Dict[str, float] = field(default_factory=dict)  # breakable prop id -> when it broke (Milestone 5)
    fragment_parent: Dict[str, str] = field(default_factory=dict)  # piece id -> the prop it came from
    creatures: list = field(default_factory=list)  # creature drivers (Milestone 5)

    def glyph_at(self, pid: str, t: float, base: Optional[str]):
        """(the glyph a prop physically is at t, (from, to, u) while it is visibly morphing or None)."""
        g, blend = base, None
        for m in self.morphs.get(pid, []):
            if t < m["t0"]:
                break
            if m["t_swap"] is None or t < m["t_swap"]:
                end = m["t_swap"] if m["t_swap"] is not None else m["t0"] + m["duration"]
                blend = (m["from"], m["to"], min(1.0, (t - m["t0"]) / max(1e-6, end - m["t0"])), m.get("nudge", (0.0, 0.0)))
                break
            g = m["to"]
        return g, blend

    def alive(self, pid: str, t: float) -> bool:
        """A prop is in the scene: a breakable prop until it breaks; its pieces from then on."""
        par = self.fragment_parent.get(pid)
        if par is not None:
            return par in self.broken and t >= self.broken[par]
        return not (pid in self.broken and t >= self.broken[pid])


def interp_track(times: np.ndarray, col: np.ndarray, t: float, cuts=()) -> float:
    """Linear interpolation of a 240 Hz track that never mixes the samples on either side of a portal jump."""
    if cuts:
        i = int(np.searchsorted(times, t, side="left"))
        if i in cuts and 0 < i < len(times) and t < times[i]:
            return float(col[i - 1])
    return float(np.interp(t, times, col))


def door_state(d: Dict[str, Optional[float]], t: float) -> Tuple[str, float]:
    """Door state machine: sealed -> unlocking -> unlocked -> opening -> open -> exited -> closing -> closed."""
    u0, o0, x0 = d.get("unlock_t"), d.get("open_t"), d.get("exit_t")
    if x0 is not None and t >= x0 + DOOR_CLOSE_DELAY:
        u = (t - x0 - DOOR_CLOSE_DELAY) / DOOR_CLOSE_S
        return ("closing", u) if u < 1.0 else ("closed", 1.0)
    if u0 is None or t < u0:
        return "sealed", 0.0
    if t < u0 + DOOR_UNLOCK_S:
        return "unlocking", (t - u0) / DOOR_UNLOCK_S
    if o0 is None or t < o0:
        return "unlocked", 1.0
    if t < o0 + DOOR_OPEN_S:
        return "opening", (t - o0) / DOOR_OPEN_S
    if x0 is not None and t >= x0:
        return "exited", 1.0
    return "open", 1.0


class SceneRuntime:
    def __init__(self, project: ProjectSpec, scene_id: str, strict: bool = True):
        self.project = project
        self.strict = strict  # False: an impossible action stops that character (recorded) instead of raising
        self.scene: SceneSpec = project.scene(scene_id)
        self.env: EnvironmentSpec = project.environment(self.scene.environment)
        self.rigs: Dict[str, StickmanRig] = {}
        for pl in self.scene.placements:
            spec: CharacterSpec = project.character(pl.character)
            self.rigs[pl.character] = StickmanRig(Proportions(**spec.proportions))
        self.result: Optional[SimulationResult] = None

    # ------------------------------------------------------------ simulation
    def simulate(self, physics_only: bool = False, horizon: Optional[float] = None) -> SimulationResult:
        """Simulate the scene. `physics_only` skips the animation layer (poses, scarves, dust): it is much faster and
        is what the planners and the setup solver use. `horizon` simulates for a different length than the scene.

        With music (Milestone 4): beat waits end on beats of the film clock. When hit-stops or slow motion make film
        and story time differ, and those depend on the simulated events, the scene is simulated again with the
        previous pass's warp until the beat waits stop moving (at most 4 passes). Shot boundaries near a beat are then
        snapped onto it (`beat_log` records each)."""
        from .beats import BeatClock, snap_shots
        music = self.scene.music
        if music is None:
            return self._simulate_once(physics_only, horizon, None)
        from ..render.timewarp import build_warp
        waits = any(a.type == "wait_beat" for a in self.scene.actions)
        clock = BeatClock(music)
        res = self._simulate_once(physics_only, horizon, clock)
        self.beat_passes = 1
        if waits and self.scene.time_fx is not None:
            prev = None
            for _ in range(3):
                w = build_warp(self.scene, res.events, res.duration, self.project.fps)
                ends = [round(e.t, 5) for e in res.events if e.type == "beat_wait_end"]
                if w.is_identity() or ends == prev:
                    break
                prev = ends
                res = self._simulate_once(physics_only, horizon, BeatClock(music, w.film_at, w.sim_at))
                self.beat_passes += 1
        if not physics_only and music.snap_cuts and horizon is None:
            w = build_warp(self.scene, res.events, res.duration, self.project.fps)
            locks = [e.t for e in res.events if e.type == "portal_exit"]  # characters and props: the picture cuts there
            shots, self.beat_log = snap_shots(self.scene, w, self.project.fps, locks)
            self.scene = self.scene.model_copy(update={"shots": shots})
        return res

    def _simulate_once(self, physics_only: bool, horizon: Optional[float], clock) -> SimulationResult:
        room = self.env.room
        world = PhysicsWorld(self.env.gravity)
        hw = room.width / 2
        world.add_static_segment("floor", (-hw - 50, 0), (hw + 50, 0), 2.0)
        world.add_static_segment("wall_right", (hw, -50), (hw, room.height + 50), 2.0)
        world.add_static_segment("wall_left", (-hw, -50), (-hw, room.height + 50), 2.0)
        world.add_static_segment("ceiling", (-hw - 50, room.height), (hw + 50, room.height), 2.0)
        T, H = 120.0, room.height
        world.add_slab("floor", [(-hw - T, -T), (hw + T, -T), (hw + T, 0.0), (-hw - T, 0.0)])
        world.add_slab("ceiling", [(-hw - T, H), (hw + T, H), (hw + T, H + T), (-hw - T, H + T)])
        world.add_slab("wall_right", [(hw, -T), (hw + T, -T), (hw + T, H + T), (hw, H + T)])
        world.add_slab("wall_left", [(-hw - T, -T), (-hw, -T), (-hw, H + T), (-hw - T, H + T)])
        for ob in self.env.obstacles:
            if ob.kind in ("beam", "platform"):
                world.add_static_box(ob.id, ob.center, ob.size)
            elif ob.kind == "glyph":
                for a, b, r, tag in structures.shape_tags(ob):
                    world.add_static_segment(tag, a, b, r)
        for pr in self.env.props:
            if pr.kind == "glyph":
                wgt = pr.weight or glyphs.default_weight(pr.size)
                com, masses = glyphs.mass_props(pr.glyph, pr.size, wgt, pr.mass)
                world.add_compound(pr.id, pr.position, glyphs.segments(pr.glyph, pr.size), wgt / 2, masses, com, angle=pr.angle,
                                   friction=pr.friction, elasticity=0.25, collide_characters=pr.collide_characters, solid=pr.solid)
                continue
            world.add_box(pr.id, pr.position, pr.size, pr.mass, angle=pr.angle, friction=pr.friction,
                          elasticity=0.15 if pr.mass < 20 else 0.02,  # heavy steel does not bounce
                          collide_characters=pr.collide_characters, com=pr.com, solid=pr.solid)
        for pr in self.env.props:  # depth extents for the character-body contact filter
            world.depth[pr.id] = (float(pr.z), pr.depth / 2)
        from ..motion.creatures import CreatureDriver
        drivers = [CreatureDriver(cr, world, k) for k, cr in enumerate(self.env.creatures)]
        frag_of = {p.id: p.fragment_of for p in self.env.props if p.fragment_of}
        breakables = {p.id: p for p in self.env.props if p.breakable is not None}
        for fid in frag_of:  # pieces are out of play until their prop breaks
            world.deactivate(fid)
        collapsing = {ob.id: ob for ob in self.env.obstacles if ob.collapse is not None}
        stood_on: Dict[str, float] = {}

        def collapse(oid: str, tn: float) -> None:
            ob = collapsing.pop(oid)
            world.remove_static(oid)
            for fid, par in frag_of.items():
                if par == oid:
                    st = world.state(fid)
                    world.activate(fid, st.pos, st.angle, (0.0, 0.0), 0.0)
            broken[oid] = tn
            events.append(Event(tn, "collapse", oid, {"obstacle": oid, "point": tuple(ob.center),
                                                      "pieces": [f for f, p in frag_of.items() if p == oid]}))
            for c in ctrls.values():  # whoever stood on it loses their footing
                if c.frame.owner == oid and c.mode in ("grounded", "landing"):
                    c.mode = "grounded"
                    c._step_off(tn)
        broken: Dict[str, float] = {}
        specs = {p.id: p for p in self.env.props}
        from .goals import matches as _matches
        morph_q = {p.id: list(p.morphs) for p in self.env.props if p.morphs}
        world.glyph_now = {p.id: p.glyph for p in self.env.props if p.kind == "glyph"}
        morph_log: Dict[str, List[dict]] = {}
        morphing: Dict[str, dict] = {}

        def morph_tick(tn: float, i_sample: int) -> None:
            for pid, q in morph_q.items():
                if pid in morphing or not q:
                    continue
                m = q[0]
                after = morph_log[pid][-1]["t0"] if morph_log.get(pid) else -1.0
                if (m.at is not None and tn >= m.at) or (m.on is not None and any(
                        e.t > after and e.t + m.delay <= tn and _matches(m.on, e) for e in events)):
                    q.pop(0)
                    rec = {"t0": tn, "duration": m.duration, "from": world.glyph_now[pid], "to": m.to, "t_swap": None}
                    morph_log.setdefault(pid, []).append(rec)
                    morphing[pid] = rec
                    events.append(Event(tn, "morph_start", pid, {"prop": pid, "from": rec["from"], "to": m.to,
                                                                 "point": world.state(pid).pos}))
            for pid, rec in list(morphing.items()):
                if tn < rec["t0"] + rec["duration"]:
                    continue
                sp = specs[pid]
                wgt = sp.weight or glyphs.default_weight(sp.size)
                segs = glyphs.segments(rec["to"], sp.size)
                com, masses = glyphs.mass_props(rec["to"], sp.size, wgt, sp.mass)
                b = world._bodies[pid]
                # where the new shape goes: the centre of mass stays put (the origin moves by the change in centre)
                ca_, sa_ = math.cos(b.angle), math.sin(b.angle)
                cg0, cg1 = b.center_of_gravity, com
                base = ((cg0.x - cg1[0]) * ca_ - (cg0.y - cg1[1]) * sa_, (cg0.x - cg1[0]) * sa_ + (cg0.y - cg1[1]) * ca_)
                hit = world.blockers(pid, segs, wgt / 2, base)
                nudge = (0.0, 0.0)
                if hit and not any(h in ctrls for h in hit):
                    # only structures (the floor under a growing stroke) in the way: the shape pushes itself clear by
                    # the smallest step that frees it (up first, then sideways), as the solver would push it out
                    for d in range(2, 2 * int(max(sp.size)) + 2, 2):
                        cand = next(((dx * d, dy * d) for dx, dy in ((0, 1), (1, 0), (-1, 0))
                                     if not world.blockers(pid, segs, wgt / 2, (base[0] + dx * d, base[1] + dy * d))), None)
                        if cand is not None:
                            nudge, hit = cand, []
                            break
                if hit:  # a character (or nowhere free) in the way: wait
                    if not rec.get("blocked"):
                        rec["blocked"] = tn
                        events.append(Event(tn, "morph_blocked", pid, {"prop": pid, "by": sorted(set(hit))}))
                    continue
                c0, v0, w0 = b.local_to_world(b.center_of_gravity), (b.velocity.x, b.velocity.y), b.angular_velocity
                I0, I1 = world.reshape(pid, segs, wgt / 2, masses, com, nudge)
                rec["nudge"] = nudge
                prop_cuts.setdefault(pid, []).append(i_sample)  # the body's origin jumps (centre kept, or nudged): a cut
                c1 = b.local_to_world(b.center_of_gravity)
                world.glyph_now[pid] = rec["to"]
                rec.update(t_swap=tn, I0=I0, I1=I1, w0=w0, w1=b.angular_velocity, v0=v0, v1=(b.velocity.x, b.velocity.y),
                           c0=(c0.x, c0.y), c1=(c1.x, c1.y))
                del morphing[pid]
                events.append(Event(tn, "morph", pid, {"prop": pid, "from": rec["from"], "to": rec["to"], "point": (c1.x, c1.y)}))

        def park(fid: str) -> None:  # an unbroken prop's piece rides along inside it
            st = world.state(frag_of[fid])
            loc = specs[fid].local
            ca, sa = math.cos(st.angle), math.sin(st.angle)
            world.set_kinematic(fid, (st.pos[0] + loc[0] * ca - loc[1] * sa, st.pos[1] + loc[0] * sa + loc[1] * ca), st.angle)

        def shatter(pid: str, tb: float, j: float, pt) -> None:
            body = world._bodies[pid]
            v, w, m0 = body.velocity, body.angular_velocity, body.mass
            cp = body.local_to_world(body.center_of_gravity)
            frs = [f for f, par in frag_of.items() if par == pid]
            for f in frs:
                park(f)
            cogs = {f: world._bodies[f].local_to_world(world._bodies[f].center_of_gravity) for f in frs}
            mean = sum(math.dist(cogs[f], cp) for f in frs) / max(1, len(frs))
            k = breakables[pid].breakable.scatter / mean if mean > 1e-6 else 0.0
            pv = {}
            for f in frs:
                st = world.state(f)
                rx, ry = cogs[f].x - cp.x, cogs[f].y - cp.y
                # rigid motion at the piece's centre of mass, plus a radial scatter proportional to its offset (the
                # mass-weighted offsets sum to zero, so the scatter adds no momentum)
                vel = (v.x - w * ry + k * rx, v.y + w * rx + k * ry)
                world.activate(f, st.pos, st.angle, vel, w)
                pv[f] = (vel, world._bodies[f].mass)
            world.deactivate(pid)
            broken[pid] = tb
            events.append(Event(tb, "break", pid, {"prop": pid, "impulse": j, "threshold": breakables[pid].breakable.impulse,
                                                   "point": tuple(pt) if pt else tuple(body.position), "pieces": frs,
                                                   "momentum": (m0 * v.x, m0 * v.y), "spin": w, "mass": m0,
                                                   "piece_motion": pv}))
        for rp in self.env.ropes:
            a_id = rp.a.split(":", 1)[1]
            if rp.b.startswith("world:"):
                bx, by = (float(v) for v in rp.b.split(":", 1)[1].split(","))
                world.add_rope(rp.id, a_id, rp.a_local, "world", (bx, by), rp.length)
            else:
                world.add_rope(rp.id, a_id, rp.a_local, rp.b.split(":", 1)[1], rp.b_local, rp.length)
        rope_prev = {rp.id: 0.0 for rp in self.env.ropes}
        rope_peak = {rp.id: 0.0 for rp in self.env.ropes}
        snapped: Dict[str, float] = {}
        last_hit: Dict[Tuple[str, str], float] = {}
        frames = room_frames(room.width, room.height)
        frames.update(structures.top_frames(self.env))
        gravity = GravityField(initial=self.env.gravity)
        events: List[Event] = []
        doors: Dict[str, Dict[str, Optional[float]]] = {ex.id: {"unlock_t": None if ex.sealed else -DOOR_UNLOCK_S - 1.0,  # unsealed: open to all
                                                                 "open_t": None, "exit_t": None} for ex in self.env.exits}
        unlock_by = {ex.unlock_on.split(":", 1)[1]: ex.id for ex in self.env.exits if ex.unlock_on and ex.unlock_on.startswith("switch:")}
        together = {ex.id: ex.unlock_on.split(":", 1)[1].split(",") for ex in self.env.exits
                    if ex.unlock_on and ex.unlock_on.startswith("together:")}
        failed: set = set()

        def emit(e: Event) -> None:
            events.append(e)
            if e.type == "switch_activated" and e.data.get("switch") in unlock_by:
                ex_id = unlock_by[e.data["switch"]]
                tr = next((g for g in gravity.transitions if g.cause == e.data["switch"] and g.t_start >= e.t - 1e-9), None)
                tu = (tr.t_start + tr.duration) if tr else e.t + 0.3  # the seal releases once the new gravity has settled
                doors[ex_id]["unlock_t"] = tu
                events.append(Event(tu, "door_unlocking", e.character, {"exit": ex_id}))
                events.append(Event(tu + DOOR_UNLOCK_S, "door_unlocked", e.character, {"exit": ex_id}))
            elif e.type == "exit_reached":
                doors[e.data["exit"]]["exit_t"] = e.t
                events.append(Event(e.t + DOOR_CLOSE_DELAY, "door_close", e.character, {"exit": e.data["exit"]}))

        ctrls: Dict[str, CharacterController] = {}
        for pl in self.scene.placements:
            acts = [a for a in self.scene.actions if a.character == pl.character]
            ctrls[pl.character] = CharacterController(pl.character, self.rigs[pl.character], world, frames, gravity, self.env,
                                                      pl.x, pl.facing, acts, emit, doors)
            ctrls[pl.character].strength = self.project.character(pl.character).strength
            ctrls[pl.character].strict = self.strict
            ctrls[pl.character].z = float(pl.z)
            if pl.on:  # starts standing on a structure's top
                c_ = ctrls[pl.character]
                c_.frame = structures.obstacle_top(self.env, frames, pl.on.split(":", 1)[1], pl.x)
                world.set_kinematic(pl.character, c_.frame.to_world(c_.s, c_.h), c_.frame.body_angle)
                c_.seg.frame = c_.frame.tag  # the opening segment stands on it too (with no action, nothing reopens it)
        shared = {"taken": {}}
        for c in ctrls.values():  # characters can see each other, the props and everything that has happened so far
            c.others, c.all_events = ctrls, events
            c.arcade = shared
            if clock is not None:
                c.beat_clock = clock
        from ..motion.arcade import portal_maps
        pmaps = portal_maps(self.env)
        roped = {r.a.split(":", 1)[1] for r in self.env.ropes} | {r.b.split(":", 1)[1] for r in self.env.ropes if r.b.startswith("prop:")}
        prop_prev: Dict[str, Vec] = {}
        prop_cuts: Dict[str, List[int]] = {}
        dt = 1.0 / SIM_HZ
        sim_len = horizon if horizon is not None else self.scene.duration
        n = int(round(sim_len * SIM_HZ)) + 1
        prop_ids = [p.id for p in self.env.props]
        prop_tracks = {pid: np.zeros((n, 3)) for pid in prop_ids}
        times = np.zeros(n)
        t = 0.0
        prop_speed_prev: Dict[str, float] = {}
        stick = {p.id: p for p in self.env.props if p.static_friction is not None}
        sliding: Dict[str, bool] = {}
        for i in range(n):
            t = i * dt
            world.set_gravity(gravity.at(t))
            for pid, sp in stick.items():  # stick-slip friction: static while at rest, kinetic once it has broken loose
                st = world.state(pid)
                speed = math.hypot(*st.vel)
                if speed > BREAK_LOOSE:  # genuinely forced past static friction (not just knocked by a bump)
                    sliding[pid] = True
                elif speed < 4.0:
                    sliding[pid] = False
                world.set_friction(pid, sp.friction if sliding.get(pid) else sp.static_friction)
            for fid, par in frag_of.items():
                if par not in broken and par in specs:  # (a collapsing structure's planks lie still in it)
                    park(fid)
            for oid, ob in list(collapsing.items()):  # a structure gives way
                cs = ob.collapse
                go = False
                if cs.under is not None:
                    c = ctrls.get(cs.under)
                    if c is not None and c.frame.owner == oid and c.mode == "grounded":
                        stood_on.setdefault(oid, t)
                    go = oid in stood_on and t - stood_on[oid] >= cs.after
                go = go or (cs.at is not None and t >= cs.at) or (cs.on is not None and any(_matches(cs.on, e) for e in events))
                if go and oid in collapsing:  # the first of its triggers
                    collapse(oid, t)
            for c in ctrls.values():
                c.update(t, dt)
            for dv in drivers:
                dv.tick(t, gravity.at(t))
            contacts = world.step(dt)
            for dv in drivers:
                dv.after_step(t + dt, events, Event)
            if morph_q:
                morph_tick(t + dt, i)
            for pid, sp in breakables.items():  # a blow hard enough breaks it
                if pid not in broken:
                    j, pt, _ = world.step_impulse.get(pid, (0.0, None, 0.0))
                    if j >= sp.breakable.impulse:
                        shatter(pid, t + dt, j, pt)
            for c in ctrls.values():
                c.after_step(t + dt, contacts)
            for ex_id, who in together.items():  # an exit that opens only for everyone at once
                d = doors[ex_id]
                if d["unlock_t"] is None:
                    ew = exit_world(self.env, ex_id)
                    ex = next(x for x in self.env.exits if x.id == ex_id)
                    if all(w in ctrls and ctrls[w].mode == "grounded" and math.dist(world.state(w).pos, ew) <= ex.open_radius for w in who):
                        d["unlock_t"] = t + dt
                        events.append(Event(t + dt, "exit_together", who[0], {"exit": ex_id, "with": who, "point": ew}))
                        events.append(Event(t + dt, "door_unlocking", who[0], {"exit": ex_id}))
                        events.append(Event(t + dt + DOOR_UNLOCK_S, "door_unlocked", who[0], {"exit": ex_id}))
            if self.scene.fail is not None:  # falling out of the level
                for cid, c in ctrls.items():
                    if cid in failed or (self.scene.fail.characters and cid not in self.scene.fail.characters):
                        continue
                    p_ = world.state(cid).pos
                    if p_[1] < self.scene.fail.below:
                        failed.add(cid)
                        events.append(Event(t + dt, "fail", cid, {"point": p_}))
            for ex in self.env.exits:  # automatic door: opens for a grounded character once unlocked
                d = doors[ex.id]
                if d["open_t"] is None and d["unlock_t"] is not None and t >= d["unlock_t"] + DOOR_UNLOCK_S:
                    ew = exit_world(self.env, ex.id)
                    for cid, c in ctrls.items():
                        if c.mode == "grounded" and math.dist(world.state(cid).pos, ew) <= ex.open_radius:
                            d["open_t"] = t
                            events.append(Event(t, "door_open", cid, {"exit": ex.id}))
                            break
            for rp in self.env.ropes:  # a strap snapping taut (or breaking) is an event (sound, camera shake, QA)
                if rp.id in snapped:
                    continue
                tension = world.rope_tension(rp.id, dt)
                rope_peak[rp.id] = max(rope_peak[rp.id], tension)
                if rp.break_force is not None and tension > rp.break_force:
                    pa, pb, ln = world.rope_points(rp.id)
                    world.cut_rope(rp.id)
                    snapped[rp.id] = t + dt
                    events.append(Event(t + dt, "rope_snap", rp.id, {"rope": rp.id, "point": ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)}))
                    continue
                pa, pb, ln = world.rope_points(rp.id)
                d = math.dist(pa, pb)
                if rope_prev[rp.id] < 0.985 * ln <= d:
                    events.append(Event(t + dt, "rope_taut", rp.id, {"rope": rp.id, "point": ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)}))
                rope_prev[rp.id] = d
            for ce in contacts:
                key = (ce.a, ce.b)
                if ce.a in prop_tracks and ce.normal_speed > 120 and t - last_hit.get(key, -1.0) > 0.15:
                    last_hit[key] = t
                    events.append(Event(ce.t, "prop_impact", ce.a, {"surface": ce.b, "normal_speed": ce.normal_speed, "point": ce.point}))
            if pmaps:  # a free prop crossing a portal comes out of the other end with its velocity rotated
                for pid in prop_ids:
                    st = world.state(pid)
                    p0 = prop_prev.get(pid)
                    prop_prev[pid] = st.pos
                    if p0 is None or pid in roped or pid in world.carried or world.is_kinematic(pid):
                        continue
                    for gid, pm in pmaps.items():
                        if pm.crossed(p0, st.pos):
                            p2 = pm.point(st.pos)
                            world.teleport(pid, p2, pm.angle(st.angle), pm.vec(st.vel), pm.spin(st.angvel))
                            prop_prev[pid] = p2
                            prop_cuts.setdefault(pid, []).append(i)
                            events.append(Event(t + dt, "portal_enter", pid, {"portal": gid, "point": st.pos, "speed": math.hypot(*st.vel),
                                                                              "velocity": st.vel}))
                            events.append(Event(t + dt, "portal_exit", pid, {"portal": pm.b.id, "from": gid, "point": p2,
                                                                             "speed": math.hypot(*st.vel), "velocity": pm.vec(st.vel)}))
                            break
            for c in ctrls.values():  # a prop carried through a portal jumps with its carrier
                for (tc, what) in c.portal_log:
                    if what.startswith("prop:") and abs(tc - (t + dt)) < 1e-9:
                        prop_cuts.setdefault(what[5:], []).append(i)
            times[i] = t + dt
            for pid in prop_ids:
                st = world.state(pid)
                prop_tracks[pid][i] = (st.pos[0], st.pos[1], st.angle)
        end = sim_len
        for c in ctrls.values():
            c.finish(end + dt)
        if physics_only:
            events.sort(key=lambda e: (e.t, e.type))
            self.result = SimulationResult(end, frames, gravity, {}, ctrls, events, times, prop_tracks, world.static_segments(),
                                           {}, None, doors, snapped, rope_peak, prop_cuts, dict(shared["taken"]), morph_log, broken, frag_of, drivers)
            return self.result
        animators = {}
        for cid, c in ctrls.items():
            spec = self.project.character(cid)
            animators[cid] = Animator(cid, self.rigs[cid], spec.style, c.segments, c.records, frames, events)
            animators[cid].portals = [exit_portal(self.env, ex.id) for ex in self.env.exits if ex.unlock_on]
            animators[cid].carry_spans = c.carry_log
        _pt = np.array(times)
        _tracks = {pid: (tr[:, 0].copy(), tr[:, 1].copy(), np.unwrap(tr[:, 2])) for pid, tr in prop_tracks.items()}

        def prop_at(pid: str, tt: float) -> Tuple[float, float, float]:
            x, y, a = _tracks[pid]
            cu = prop_cuts.get(pid, ())
            return interp_track(_pt, x, tt, cu), interp_track(_pt, y, tt, cu), interp_track(_pt, a, tt, cu)

        for an in animators.values():
            an.prop_at, an.others = prop_at, animators
            an.prop_specs = {p.id: p for p in self.env.props}
            events.extend(animators[cid].footsteps)
        for tr in gravity.transitions:
            events.append(Event(tr.t_start + tr.duration, "gravity_settled", "", {"to": tr.to}))
        events.sort(key=lambda e: (e.t, e.type))
        scarves = {}
        for cid, an in animators.items():
            if self.project.character(cid).style.has_scarf:
                scarves[cid] = ScarfSim(an.pose_at, self.rigs[cid], gravity, (-hw, 0.0, hw, room.height), 0.0, end + 0.1,
                                        seed=self.project.seed,
                                        portals=[exit_portal(self.env, ex.id) for ex in self.env.exits if ex.unlock_on or not ex.sealed])
        impulses = [(e.t, e.data["point"], 260.0 * min(1.5, e.data.get("normal_speed", 600) / 900)) for e in events
                    if e.type == "impact" and "point" in e.data]
        impulses += [(e.t, switch_world(self.env, next(sw for sw in self.env.switches if sw.id == e.data["switch"])), 180.0)
                     for e in events if e.type == "switch_activated"]
        dust = DustField(self.env.dust, room, gravity, impulses, end + 0.1, seed=self.project.seed) if self.env.dust else None
        self.result = SimulationResult(end, frames, gravity, animators, ctrls, events, times, prop_tracks, world.static_segments(),
                                       scarves, dust, doors, snapped, rope_peak, prop_cuts, dict(shared["taken"]), morph_log, broken, frag_of, drivers)
        return self.result

    # ------------------------------------------------------------ evaluation
    def evaluate(self, t: float) -> FrameState:
        r = self.result or self.simulate()
        poses = {cid: a.pose_at(t) for cid, a in r.animators.items()}
        props = []
        for pr in self.env.props:
            if not r.alive(pr.id, t):
                continue
            tr = r.prop_tracks[pr.id]
            cu = r.prop_cuts.get(pr.id, ())
            x = interp_track(r.prop_times, tr[:, 0], t, cu)
            y = interp_track(r.prop_times, tr[:, 1], t, cu)
            a = interp_track(r.prop_times, np.unwrap(tr[:, 2]), t, cu)
            g, bl = r.glyph_at(pr.id, t, pr.glyph) if pr.kind == "glyph" else (None, None)
            if bl is not None:  # the physical swap keeps the centre of mass still: end the blend where the new shape will sit
                w_ = pr.weight or glyphs.default_weight(pr.size)
                ca_, cb_ = glyphs.mass_props(bl[0], pr.size, w_, pr.mass)[0], glyphs.mass_props(bl[1], pr.size, w_, pr.mass)[0]
                nx, ny = bl[3]
                cs, sn = math.cos(a), math.sin(a)  # the nudge (world) in the prop's own frame
                bl = bl[:3] + ((ca_[0] - cb_[0] + nx * cs + ny * sn, ca_[1] - cb_[1] - nx * sn + ny * cs),)
            props.append(PropState(pr.id, pr.kind, pr.size, (x, y), a, pr.z, pr.depth, pr.z < -5.0, g, bl))
        ropes = []
        for rp in self.env.ropes:
            ends = []
            for ref, loc in ((rp.a, rp.a_local), (rp.b, rp.b_local)):
                k, _, v = ref.partition(":")
                if k == "world":
                    ends.append(tuple(float(c) for c in v.split(",")))
                else:
                    ps = next(p for p in props if p.id == v)
                    ca, sa = math.cos(ps.angle), math.sin(ps.angle)
                    ends.append((ps.pos[0] + loc[0] * ca - loc[1] * sa, ps.pos[1] + loc[0] * sa + loc[1] * ca))
            ropes.append(RopeState(rp.id, ends[0], ends[1], rp.length, rp.color, t >= r.rope_snaps.get(rp.id, 1e9)))
        glow = {}
        for sw in self.env.switches:
            g = 0.55 + 0.08 * math.sin(t * 5)
            for e in r.events:
                if e.type == "switch_activated" and e.data.get("switch") == sw.id and t >= e.t:
                    g += 2.2 * math.exp(-(t - e.t) * 6) + 0.6 * max(0.0, math.sin((t - e.t) * math.pi * 7)) * math.exp(-(t - e.t) * 1.2)
            glow[sw.id] = g
        recent = [e for e in r.events if 0 <= t - e.t < 1.0]
        scarves = {cid: sc.at(t) for cid, sc in r.scarves.items()}
        dust = r.dust.at(t) if r.dust else None
        dprev = r.dust.at(t - 0.06) if r.dust else None
        doors = {ex_id: door_state(d, t) for ex_id, d in r.doors.items()}
        fired = {}
        for e in r.events:
            if e.type.startswith("orb_") and e.t <= t:
                fired[e.data["orb"]] = t - e.t
        return FrameState(t, poses, props, r.gravity.at(t), r.gravity.state_label(t), glow, recent, scarves, dust, dprev, doors, ropes,
                          {cid: a.depth_at(t) for cid, a in r.animators.items()},
                          {k: v for k, v in r.orbs_taken.items() if v <= t}, fired,
                          {o.id for o in self.env.obstacles if o.id in r.broken and t >= r.broken[o.id]})

    def state_hash(self, times: List[float]) -> str:
        """Hash of character joints over the given times (determinism / regression checks)."""
        h = hashlib.sha256()
        for t in times:
            fs = self.evaluate(t)
            for cid in sorted(fs.poses):
                j = self.rigs[cid].world_joints(fs.poses[cid])
                h.update(json.dumps({k: (round(v[0], 4), round(v[1], 4)) for k, v in sorted(j.items())}).encode())
        return h.hexdigest()
