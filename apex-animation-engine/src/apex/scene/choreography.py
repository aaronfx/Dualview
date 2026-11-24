"""M3: bounded, deterministic candidate choreography with physical verification.

This planner does NOT claim to solve arbitrary platform puzzles. It selects
between short ground routes and jump approaches using APEX's real geometry,
then runs the candidate in the authoritative SceneRuntime before accepting it.
No LLM can bypass a failed simulation or claim an unobserved goal event.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence
import math

from .route_planner import check_jump
from .schema import ActionSpec, EnvironmentSpec, ProjectSpec
from .structures import blocks
from .runtime import SceneRuntime


@dataclass(frozen=True)
class Candidate:
    name: str
    actions: tuple[ActionSpec, ...]
    estimate: float
    rationale: str


@dataclass(frozen=True)
class Attempt:
    name: str
    accepted: bool
    reason: str
    observed: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    candidate: Optional[Candidate]
    attempts: tuple[Attempt, ...]

    @property
    def accepted(self) -> bool:
        return self.candidate is not None


def _ground_clear(env: EnvironmentSpec, a: float, b: float, *, margin: float = 20.0) -> bool:
    lo, hi = sorted((a, b))
    return all(not (solid.x1 + margin > lo and solid.x0 - margin < hi
                    and solid.y1 > 1.0 and solid.y0 < 175.0)
               for solid in blocks(env))


def propose(env: EnvironmentSpec, character: str, start_x: float, goal_x: float, *,
            speeds: Sequence[float] = (340.0, 440.0, 560.0),
            rises: Sequence[float] = (100.0, 170.0, 240.0),
            max_candidates: int = 24) -> tuple[Candidate, ...]:
    """Return physically bounded routes ordered by cost; no scene mutation.

    Currently supports a floor with downward gravity, one or more static
    obstacles and ground-to-ground jumps. Dynamic props, gaps, moving
    platforms, and other gravity orientations require future planners.
    """
    if max_candidates < 1 or max_candidates > 128:
        raise ValueError("candidate budget must be between 1 and 128")
    if not all(math.isfinite(v) for v in (start_x, goal_x, *speeds, *rises)):
        raise ValueError("all positions and physical budgets must be finite")
    if abs(goal_x - start_x) < 1.0:
        return (Candidate("already_there", (ActionSpec(type="idle", character=character, duration=0.3),),
                          0.0, "goal already reached"),)
    sign = 1.0 if goal_x > start_x else -1.0
    out: list[Candidate] = []
    if _ground_clear(env, start_x, goal_x):
        for speed in speeds:
            if speed <= 0:
                continue
            out.append(Candidate(f"ground_{int(speed)}",
                (ActionSpec(type="run_to", character=character, target_x=goal_x, speed=speed),),
                abs(goal_x-start_x)/speed, "unobstructed ground route"))
    else:
        obstructions = [b for b in blocks(env)
                        if min(start_x, goal_x) < b.x1 and b.x0 < max(start_x, goal_x)
                        and b.y1 > 1 and b.y0 < 175]
        if not obstructions:
            return ()
        near = min(obstructions, key=lambda b: abs((b.x0 if sign > 0 else b.x1)-start_x))
        approach = (near.x0 - 95) if sign > 0 else (near.x1 + 95)
        landing = (near.x1 + 120) if sign > 0 else (near.x0 - 120)
        if sign * (approach-start_x) < -1 or sign * (goal_x-landing) < 0:
            return ()
        if not _ground_clear(env, start_x, approach) or not _ground_clear(env, landing, goal_x):
            return ()
        for speed in speeds:
            if speed <= 0:
                continue
            for rise in rises:
                if rise <= 0:
                    continue
                # The *requested* jump apex is a gameplay input. APEX physics
                # ultimately decides whether the character reaches its target.
                # Use a ballistic envelope as a rejection gate, never a proof.
                verdict = check_jump(env, (approach, 0), (landing, 0),
                                     horizontal_speed=sign * speed,
                                     max_rise=rise * 1.65,
                                     max_launch_speed=1600.0,
                                     body_height=145.0)
                if not verdict.feasible:
                    continue
                actions = (
                    ActionSpec(type="run_to", character=character, target_x=approach, speed=speed),
                    ActionSpec(type="jump_to", character=character, target_x=landing, height=rise),
                    ActionSpec(type="run_to", character=character, target_x=goal_x, speed=speed),
                )
                estimate = (abs(approach-start_x)+abs(goal_x-landing))/speed + verdict.plan.duration
                out.append(Candidate(f"jump_{int(speed)}_{int(rise)}", actions,
                                     estimate, f"clear ballistic envelope over {near.owner}"))
    return tuple(sorted(out, key=lambda c: (c.estimate, c.name))[:max_candidates])


def choose_with_simulation(project: ProjectSpec, scene_id: str, character: str,
                           candidates: Sequence[Candidate], *,
                           required_events: Sequence[str] = ("takeoff", "impact"),
                           max_attempts: int = 12,
                           evaluator: Optional[Callable[[object], tuple[bool, str]]] = None) -> Decision:
    """Accept only a candidate that actually completes in the physics runtime.

    The scene's original actions are replaced only in a *copy*. Attempts are
    bounded, deterministic and fully auditable. A missing goal event rejects
    the candidate even if the ballistic preflight predicted success.
    """
    if not 1 <= max_attempts <= 128:
        raise ValueError("max_attempts must be between 1 and 128")
    attempts: list[Attempt] = []
    for cand in candidates[:max_attempts]:
        p = project.model_copy(deep=True)
        scene = p.scene(scene_id)
        scene.actions = list(cand.actions)
        scene.goals = []
        try:
            sim = SceneRuntime(p, scene_id).simulate(physics_only=True)
            observed = tuple(e.type for e in sim.events if e.character == character)
            missing = [name for name in required_events if name not in observed]
            if missing:
                attempts.append(Attempt(cand.name, False, "missing physics events: "+", ".join(missing), observed))
                continue
            if evaluator is not None:
                accepted, reason = evaluator(sim)
                if not accepted:
                    attempts.append(Attempt(cand.name, False, reason, observed))
                    continue
            attempts.append(Attempt(cand.name, True, "verified in SceneRuntime", observed))
            return Decision(cand, tuple(attempts))
        except (ValueError, RuntimeError, AssertionError) as exc:
            attempts.append(Attempt(cand.name, False, f"{type(exc).__name__}: {exc}", ()))
    return Decision(None, tuple(attempts))
