"""M3: bounded, evidence-driven choreography search over existing APEX actions.

The Director supplies an objective and a *real* level. This module proposes
small tactical plans, simulates each using native 240 Hz APEX physics, rejects
plans whose intended effects do not occur, and chooses a feasible plan with
a reproducible trace. It does NOT hallucinate animation, patch the engine
physics, author arbitrary films, or claim artistic quality.

M3 milestone scope: a single actor, a downward-gravity floor, one structural
obstacle between actor and goal, optional movable prop; goal is a physical
pick-up. General graph search and multi-character planning are later work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Optional

from .route_planner import check_jump
from .schema import ActionSpec, ProjectSpec
from .runtime import SceneRuntime
from .pacing import PaceName, actor_pace
from .structures import obstacle_bounds


@dataclass(frozen=True)
class Objective:
    scene_id: str
    actor: str
    obstacle_id: str
    goal_prop_id: str
    max_trial_seconds: float = 20.0
    max_jump_apex: float = 210.0
    prefer_prop_interaction: bool = False
    movable_prop_id: Optional[str] = None
    pacing: PaceName = "active"  # director asks for brisk, decisive acting; measured retains the previous benchmark

    def __post_init__(self):
        if not 4 <= self.max_trial_seconds <= 60:
            raise ValueError("trial budget must be between 4 and 60 seconds")
        if not 40 <= self.max_jump_apex <= 420:
            raise ValueError("jump apex budget must be between 40 and 420")
        actor_pace(self.pacing)  # reject unknown/unsupported styles instead of silently slowing down


@dataclass(frozen=True)
class Candidate:
    name: str
    actions: tuple[dict[str, Any], ...]
    required_event: Optional[str] = None
    optional_push: bool = False
    check_jump_height: Optional[float] = None
    takeoff_x: Optional[float] = None
    landing_x: Optional[float] = None


@dataclass(frozen=True)
class Trial:
    candidate: str
    accepted: bool
    reason: str
    event_times: dict[str, float]
    score: Optional[float] = None
    prop_displacement: Optional[float] = None


@dataclass(frozen=True)
class SearchResult:
    objective: Objective
    chosen: Optional[str]
    actions: tuple[dict[str, Any], ...]
    trials: tuple[Trial, ...]

    @property
    def succeeded(self) -> bool:
        return self.chosen is not None

    def report(self) -> dict[str, Any]:
        return {
            "objective": asdict(self.objective),
            "chosen": self.chosen,
            "succeeded": self.succeeded,
            "attempted": len(self.trials),
            "trials": [asdict(t) for t in self.trials],
            "chosen_actions": [dict(a) for a in self.actions],
            "validity": "native 240 Hz physics events; final rendered-film QA still required"
        }


def _a(actor: str, kind: str, **fields) -> dict[str, Any]:
    return {"character": actor, "type": kind, **fields}


def _first_event(events, name: str, actor: str, *, prop: Optional[str] = None):
    for e in events:
        if e.type == name and e.character == actor and (prop is None or e.data.get("prop") == prop):
            return e
    return None


def propose(project: ProjectSpec, objective: Objective) -> tuple[Candidate, ...]:
    """Generate tactics from geometry, not a hardcoded list of coordinates.

    There is no promise a tactic works. Simulation below must prove the outcome.
    """
    scene = project.scene(objective.scene_id)
    env = project.environment(scene.environment)
    pace = actor_pace(objective.pacing)
    if env.gravity[1] >= 0 or abs(env.gravity[0]) > 1e-6:
        raise ValueError("M3 bounded planner currently supports downward gravity only")
    pl = next((p for p in scene.placements if p.character == objective.actor), None)
    if pl is None:
        raise ValueError(f"actor {objective.actor!r} is not placed in scene")
    ob = next((o for o in env.obstacles if o.id == objective.obstacle_id), None)
    goal = next((p for p in env.props if p.id == objective.goal_prop_id), None)
    if ob is None or goal is None:
        raise ValueError("objective must name a real obstacle and a real goal prop")
    if ob.kind not in ("platform", "glyph"):
        raise ValueError("M3 obstacle must have a climbable top")
    left, right, bottom, top = obstacle_bounds(env, ob.id)
    start, gx = pl.x, goal.position[0]
    if not (start + 40 < left < right < gx - 45):
        raise ValueError("M3 objective requires actor, obstacle and goal ordered left to right")
    if pl.facing != 1:
        raise ValueError("M3 first milestone requires actor initially facing right")
    if not (-env.room.width / 2 + 90 < start < gx < env.room.width / 2 - 70):
        raise ValueError("actor and goal require space clear of room edges")

    # M4 active actors see the problem and show emotion *while already
    # travelling*. No idle notice -> idle act -> start run staircase.
    # Measured mode remains as a controlled, reproducible A/B baseline.
    focus = f"point:{(left + right)/2:g},{top + 35:g}"
    if objective.pacing == "active":
        opening = (
            _a(objective.actor, "run_to", target_x=min(start + 180.0, left - 155.0),
               speed=pace.travel_speed, target=focus, notice_while_moving=True,
               clip="doubt_to_dash", emotion="afraid", intensity=1.14,
               tempo=pace.decision_tempo),
        )
    else:
        opening = (
            _a(objective.actor, "notice", target=focus, duration=pace.notice_seconds),
            _a(objective.actor, "act", clip="doubt_to_dash", emotion="afraid", intensity=1.14,
               tempo=pace.decision_tempo),
        )
    finish = (
        _a(objective.actor, "run_to", target_x=gx - 62, speed=pace.goal_speed),
        _a(objective.actor, "pick_up", target=f"prop:{objective.goal_prop_id}"),
        _a(objective.actor, "act", clip="cheer", emotion="joyful", intensity=0.95,
           tempo=pace.celebration_tempo),
        _a(objective.actor, "idle", duration=pace.end_hold),
    )

    near, far = left - 122, right + 135
    from ..rig.stickman import Proportions
    # _start_climb lands on edge - 0.30*stand_height. Approach exactly
    # there: no redundant short walk initiated after arriving at the barrier.
    proportions = Proportions(**project.character(objective.actor).proportions)
    climb_ready_x = left - 0.30 * proportions.stand_height
    # For an active actor, a verified landing is followed immediately by the
    # goal-directed run. A contact-aware upper-body clip carries the emotion
    # while the real gait owns footsteps; the legacy measured presentation
    # retains a separate knee-contact recovery performance.
    if objective.pacing == "active":
        climb_payoff = (
            _a(objective.actor, "run_to", target_x=gx - 62, speed=pace.goal_speed,
               clip="land_and_dash", emotion="determined",
               intensity=1.05, tempo=pace.recovery_tempo),
        ) + finish[1:]
    else:
        climb_payoff = (
            _a(objective.actor, "act", clip="impact_to_grin", emotion="relieved", intensity=1.08,
               tempo=pace.recovery_tempo),
        ) + finish
    # The landing x is outside the obstacle, not an unexplained teleport.
    base = [
        Candidate("direct_run", opening + (_a(objective.actor, "run_to", target_x=gx - 62, speed=pace.travel_speed),)
                  + finish[1:], required_event=None),
        Candidate("low_jump", opening + (
            _a(objective.actor, "run_to", target_x=near, speed=pace.travel_speed),
            _a(objective.actor, "jump_to", target_x=far, height=min(top + 20, objective.max_jump_apex * 0.70)),
        ) + finish, required_event="takeoff", check_jump_height=min(top + 20, objective.max_jump_apex * 0.70),
            takeoff_x=near, landing_x=far),
        Candidate("powered_jump", opening + (
            _a(objective.actor, "run_to", target_x=near, speed=pace.travel_speed * 1.08),
            _a(objective.actor, "jump_to", target_x=far, height=min(top + 90, objective.max_jump_apex)),
        ) + finish, required_event="takeoff", check_jump_height=min(top + 90, objective.max_jump_apex),
            takeoff_x=near, landing_x=far),
        Candidate("vault", opening + (
            _a(objective.actor, "vault", target=f"obstacle:{ob.id}"),
        ) + finish, required_event="vault"),
        Candidate("climb_then_drop", opening + (
            _a(objective.actor, "run_to", target_x=climb_ready_x, speed=pace.travel_speed),
            _a(objective.actor, "climb", target=f"obstacle:{ob.id}",
               tempo=1.21 if objective.pacing == "active" else 1.0),
            _a(objective.actor, "jump_to", target_x=far, height=85.0),
        ) + climb_payoff, required_event="climbed"),
    ]
    if objective.movable_prop_id:
        movable = next((p for p in env.props if p.id == objective.movable_prop_id), None)
        if movable is None or movable.id == goal.id:
            raise ValueError("movable_prop_id must be another actual prop")
        if movable.position[0] + movable.size[0] / 2 >= left - 35:
            # A crate already contacting the structure is not a safe push route.
            pass
        elif start < movable.position[0]:
            approach = movable.position[0] - movable.size[0] / 2 - 65
            base.append(Candidate("shift_crate_then_climb", opening + (
                _a(objective.actor, "walk_to", target_x=approach, speed=205 if objective.pacing == "active" else 140),
                _a(objective.actor, "push", target=f"prop:{movable.id}", duration=1.10, effort=0.42),
                _a(objective.actor, "climb", target=f"obstacle:{ob.id}"),
                _a(objective.actor, "jump_to", target_x=far, height=85.0),
            ) + finish, required_event="climbed", optional_push=True))
    return tuple(base)


def _trial_project(template: ProjectSpec, objective: Objective, c: Candidate) -> ProjectSpec:
    data = template.model_dump(mode="json")
    sc = next(s for s in data["scenes"] if s["id"] == objective.scene_id)
    # No legacy authored actions are quietly retained: the mission owns this actor.
    sc["actions"] = [dict(a) for a in c.actions]
    sc["goals"] = []  # objective acceptance is verified from events, independently
    sc["duration"] = objective.max_trial_seconds
    sc["shots"] = [{"id": "trial", "start": 0, "end": objective.max_trial_seconds,
                    "kind": "wide", "camera": {"mode": "static", "center": [0, 280], "view_height": 700}}]
    sc["score"] = None
    sc["music"] = None
    sc["time_fx"] = None
    return ProjectSpec.model_validate(data)


def evaluate(project: ProjectSpec, objective: Objective, candidate: Candidate) -> Trial:
    """The trial is rejected unless a real physical pickup occurs without error.

    Physics preflight only rejects impossible jumps; it cannot certify success.
    """
    if candidate.check_jump_height is not None:
        env = project.environment(project.scene(objective.scene_id).environment)
        h = candidate.check_jump_height
        g = -env.gravity[1]
        flight = 2.0 * math.sqrt(2.0 * h / g)
        vx = (candidate.landing_x - candidate.takeoff_x) / flight
        verdict = check_jump(env, (candidate.takeoff_x, 0.0), (candidate.landing_x, 0.0),
                             horizontal_speed=vx, body_height=160.0,
                             max_rise=objective.max_jump_apex, max_launch_speed=1250.0)
        if not verdict.feasible:
            return Trial(candidate.name, False, f"geometry preflight rejected: {verdict.reason}", {})
    try:
        p = _trial_project(project, objective, candidate)
        rt = SceneRuntime(p, objective.scene_id, strict=False)
        result = rt.simulate(physics_only=True)
    except (ValueError, KeyError, RuntimeError, ArithmeticError, TypeError) as exc:
        return Trial(candidate.name, False, f"physics rejected action: {str(exc)[:230]}", {})
    actor = objective.actor
    event_names = ["notice", "act", "takeoff", "impact", "vault", "climbed", "push_start", "push_end",
                   "push_lost", "push_fail", "pick_up", "body_fall"]
    times = {name: round(e.t, 4) for name in event_names
             if (e := _first_event(result.events, name, actor)) is not None}
    failed = [e.type for e in result.events if e.character == actor and
              e.type in ("push_fail", "push_lost", "body_fall", "fail")]
    ctrl = result.controllers.get(actor)
    violation = getattr(ctrl, "violation", None) if ctrl is not None else None
    picked = _first_event(result.events, "pick_up", actor, prop=objective.goal_prop_id)
    if violation or failed:
        return Trial(candidate.name, False, f"controller rejected: {violation or ', '.join(failed)}", times)
    if candidate.required_event and not _first_event(result.events, candidate.required_event, actor):
        return Trial(candidate.name, False, f"missing physics event {candidate.required_event}", times)
    if picked is None:
        return Trial(candidate.name, False, f"goal prop {objective.goal_prop_id} not physically picked up in trial", times)
    movement = None
    if candidate.optional_push:
        pid = objective.movable_prop_id
        track = result.prop_tracks.get(pid)
        if track is not None and len(track):
            movement = round(float(track[-1, 0] - track[0, 0]), 3)
        if not _first_event(result.events, "push_end", actor) or movement is None or movement < 12:
            return Trial(candidate.name, False, "crate manipulation did not move the prop at least 12 units and complete", times,
                         prop_displacement=movement)
    if picked.t >= objective.max_trial_seconds - 0.6:
        return Trial(candidate.name, False, "objective reached too late for payoff", times,
                     prop_displacement=movement)
    # Favor efficient clear movements; reward a *verified* creative environmental
    # interaction only if requested. Never reward a claim without displacement.
    complexity = len(candidate.actions)
    score = round(picked.t + 0.12 * complexity
                  - (2.0 if candidate.optional_push and objective.prefer_prop_interaction else 0.0), 4)
    return Trial(candidate.name, True, "proved: real simulation completed physical goal pickup",
                 times, score, movement)


def search(project: ProjectSpec, objective: Objective) -> SearchResult:
    trials: list[Trial] = []
    candidates = propose(project, objective)
    for c in candidates:
        trials.append(evaluate(project, objective, c))
    winners = [(t.score, i) for i, t in enumerate(trials) if t.accepted and t.score is not None]
    if not winners:
        return SearchResult(objective, None, (), tuple(trials))
    _, selected = min(winners)
    return SearchResult(objective, candidates[selected].name, candidates[selected].actions, tuple(trials))
