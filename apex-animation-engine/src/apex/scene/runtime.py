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
from ..motion.secondary import DustField, ScarfSim
from ..physics.gravity import GravityField
from ..physics.world import PhysicsWorld
from ..rig.stickman import Pose, Proportions, StickmanRig
from .schema import CharacterSpec, EnvironmentSpec, ProjectSpec, SceneSpec

SIM_HZ = 240


@dataclass
class PropState:
    id: str
    kind: str
    size: Vec
    pos: Vec
    angle: float


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


class SceneRuntime:
    def __init__(self, project: ProjectSpec, scene_id: str):
        self.project = project
        self.scene: SceneSpec = project.scene(scene_id)
        self.env: EnvironmentSpec = project.environment(self.scene.environment)
        self.rigs: Dict[str, StickmanRig] = {}
        for pl in self.scene.placements:
            spec: CharacterSpec = project.character(pl.character)
            self.rigs[pl.character] = StickmanRig(Proportions(**spec.proportions))
        self.result: Optional[SimulationResult] = None

    # ------------------------------------------------------------ simulation
    def simulate(self) -> SimulationResult:
        room = self.env.room
        world = PhysicsWorld(self.env.gravity)
        hw = room.width / 2
        world.add_static_segment("floor", (-hw - 50, 0), (hw + 50, 0), 2.0)
        world.add_static_segment("wall_right", (hw, -50), (hw, room.height + 50), 2.0)
        world.add_static_segment("wall_left", (-hw, -50), (-hw, room.height + 50), 2.0)
        world.add_static_segment("ceiling", (-hw - 50, room.height), (hw + 50, room.height), 2.0)
        for pr in self.env.props:
            world.add_box(pr.id, pr.position, pr.size, pr.mass)
        frames = room_frames(room.width, room.height)
        gravity = GravityField(initial=self.env.gravity)
        events: List[Event] = []
        ctrls: Dict[str, CharacterController] = {}
        for pl in self.scene.placements:
            acts = [a for a in self.scene.actions if a.character == pl.character]
            ctrls[pl.character] = CharacterController(pl.character, self.rigs[pl.character], world, frames, gravity, self.env,
                                                      pl.x, pl.facing, acts, events.append)
        dt = 1.0 / SIM_HZ
        n = int(round(self.scene.duration * SIM_HZ)) + 1
        prop_ids = [p.id for p in self.env.props]
        prop_tracks = {pid: np.zeros((n, 3)) for pid in prop_ids}
        times = np.zeros(n)
        t = 0.0
        prop_speed_prev: Dict[str, float] = {}
        for i in range(n):
            t = i * dt
            world.set_gravity(gravity.at(t))
            for c in ctrls.values():
                c.update(t, dt)
            contacts = world.step(dt)
            for c in ctrls.values():
                c.after_step(t + dt, contacts)
            for ce in contacts:
                if ce.a in prop_tracks and ce.normal_speed > 120:
                    events.append(Event(ce.t, "prop_impact", ce.a, {"surface": ce.b, "normal_speed": ce.normal_speed, "point": ce.point}))
            times[i] = t + dt
            for pid in prop_ids:
                st = world.state(pid)
                prop_tracks[pid][i] = (st.pos[0], st.pos[1], st.angle)
        end = self.scene.duration
        for c in ctrls.values():
            c.finish(end + dt)
        animators = {}
        for cid, c in ctrls.items():
            spec = self.project.character(cid)
            animators[cid] = Animator(cid, self.rigs[cid], spec.style, c.segments, c.records, frames, events)
            events.extend(animators[cid].footsteps)
        for tr in gravity.transitions:
            events.append(Event(tr.t_start + tr.duration, "gravity_settled", "", {"to": tr.to}))
        events.sort(key=lambda e: (e.t, e.type))
        scarves = {}
        for cid, an in animators.items():
            if self.project.character(cid).style.has_scarf:
                scarves[cid] = ScarfSim(an.pose_at, self.rigs[cid], gravity, (-hw, 0.0, hw, room.height), 0.0, end + 0.1,
                                        seed=self.project.seed)
        impulses = [(e.t, e.data["point"], 260.0 * min(1.5, e.data.get("normal_speed", 600) / 900)) for e in events
                    if e.type == "impact" and "point" in e.data]
        impulses += [(e.t, (switches_x, 60.0), 180.0) for e in events if e.type == "switch_activated"
                     for switches_x in [next(sw.x for sw in self.env.switches if sw.id == e.data["switch"])]]
        dust = DustField(self.env.dust, room, gravity, impulses, end + 0.1, seed=self.project.seed) if self.env.dust else None
        self.result = SimulationResult(end, frames, gravity, animators, ctrls, events, times, prop_tracks, world.static_segments(),
                                       scarves, dust)
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
            props.append(PropState(pr.id, pr.kind, pr.size, (x, y), a))
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
        return FrameState(t, poses, props, r.gravity.at(t), r.gravity.state_label(t), glow, recent, scarves, dust, dprev)

    def state_hash(self, times: List[float]) -> str:
        """Hash of character joints over the given times (determinism / regression checks)."""
        h = hashlib.sha256()
        for t in times:
            fs = self.evaluate(t)
            for cid in sorted(fs.poses):
                j = self.rigs[cid].world_joints(fs.poses[cid])
                h.update(json.dumps({k: (round(v[0], 4), round(v[1], 4)) for k, v in sorted(j.items())}).encode())
        return h.hexdigest()
