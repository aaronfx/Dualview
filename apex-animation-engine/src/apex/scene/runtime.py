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
        is what the planners and the setup solver use. `horizon` simulates for a different length than the scene."""
        room = self.env.room
        world = PhysicsWorld(self.env.gravity)
        hw = room.width / 2
        world.add_static_segment("floor", (-hw - 50, 0), (hw + 50, 0), 2.0)
        world.add_static_segment("wall_right", (hw, -50), (hw, room.height + 50), 2.0)
        world.add_static_segment("wall_left", (-hw, -50), (-hw, room.height + 50), 2.0)
        world.add_static_segment("ceiling", (-hw - 50, room.height), (hw + 50, room.height), 2.0)
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
        doors: Dict[str, Dict[str, Optional[float]]] = {ex.id: {"unlock_t": None, "open_t": None, "exit_t": None} for ex in self.env.exits}
        unlock_by = {ex.unlock_on.split(":", 1)[1]: ex.id for ex in self.env.exits if ex.unlock_on}

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
        for c in ctrls.values():  # characters can see each other, the props and everything that has happened so far
            c.others, c.all_events = ctrls, events
        dt = 1.0 / SIM_HZ
        sim_len = horizon if horizon is not None else self.scene.duration
        n = int(round(sim_len * SIM_HZ)) + 1
        prop_ids = [p.id for p in self.env.props]
        prop_tracks = {pid: np.zeros((n, 3)) for pid in prop_ids}
        times = np.zeros(n)
        t = 0.0
        prop_speed_prev: Dict[str, float] = {}
        stick = {p.id: p for p in self.env.props if p.static_friction is not None}
        for i in range(n):
            t = i * dt
            world.set_gravity(gravity.at(t))
            for pid, sp in stick.items():  # stick-slip friction: static while (nearly) at rest, kinetic once sliding
                st = world.state(pid)
                world.set_friction(pid, sp.static_friction if math.hypot(*st.vel) < 4.0 else sp.friction)
            for c in ctrls.values():
                c.update(t, dt)
            contacts = world.step(dt)
            for c in ctrls.values():
                c.after_step(t + dt, contacts)
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
                                           {}, None, doors, snapped, rope_peak)
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
            return float(np.interp(tt, _pt, x)), float(np.interp(tt, _pt, y)), float(np.interp(tt, _pt, a))

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
                                        portals=[exit_portal(self.env, ex.id) for ex in self.env.exits if ex.unlock_on])
        impulses = [(e.t, e.data["point"], 260.0 * min(1.5, e.data.get("normal_speed", 600) / 900)) for e in events
                    if e.type == "impact" and "point" in e.data]
        impulses += [(e.t, switch_world(self.env, next(sw for sw in self.env.switches if sw.id == e.data["switch"])), 180.0)
                     for e in events if e.type == "switch_activated"]
        dust = DustField(self.env.dust, room, gravity, impulses, end + 0.1, seed=self.project.seed) if self.env.dust else None
        self.result = SimulationResult(end, frames, gravity, animators, ctrls, events, times, prop_tracks, world.static_segments(),
                                       scarves, dust, doors, snapped, rope_peak)
        return self.result

    # ------------------------------------------------------------ evaluation
    def evaluate(self, t: float) -> FrameState:
        r = self.result or self.simulate()
        poses = {cid: a.pose_at(t) for cid, a in r.animators.items()}
        props = []
        for pr in self.env.props:
            tr = r.prop_tracks[pr.id]
            x = float(np.interp(t, r.prop_times, tr[:, 0]))
            y = float(np.interp(t, r.prop_times, tr[:, 1]))
            a = float(np.interp(t, r.prop_times, np.unwrap(tr[:, 2])))
            props.append(PropState(pr.id, pr.kind, pr.size, (x, y), a, pr.z, pr.depth, pr.z < -5.0))
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
        return FrameState(t, poses, props, r.gravity.at(t), r.gravity.state_label(t), glow, recent, scarves, dust, dprev, doors, ropes)

    def state_hash(self, times: List[float]) -> str:
        """Hash of character joints over the given times (determinism / regression checks)."""
        h = hashlib.sha256()
        for t in times:
            fs = self.evaluate(t)
            for cid in sorted(fs.poses):
                j = self.rigs[cid].world_joints(fs.poses[cid])
                h.update(json.dumps({k: (round(v[0], 4), round(v[1], 4)) for k, v in sorted(j.items())}).encode())
        return h.hexdigest()
