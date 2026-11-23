"""Objective story-contract QA across mathematical, rhythm and cinematic productions.

These checks verify authored logic and simulation evidence, NOT artistic quality.
They are intentionally runnable without a renderer, GPU or live LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from ..scene.goals import matches
from ..scene.math_semantics import verify_rewrite


@dataclass(frozen=True)
class CreativeCheck:
    name: str
    status: str  # PASS | FAIL | WARN | SKIP
    details: str = ""
    metric: Optional[float] = None
    threshold: Optional[float] = None


def _check(name: str, failures: list[str], success: str) -> CreativeCheck:
    return CreativeCheck(name, "FAIL" if failures else "PASS", "; ".join(failures[:15]) if failures else success)


def audit_creative_plan(project: Any, events_by_scene: Optional[Mapping[str, Sequence[Any]]] = None) -> list[CreativeCheck]:
    """Evaluate an optional CreativePlan against actual ProjectSpec and scene events.

    `events_by_scene=None` means the simulation is NOT checked; it is never
    falsely treated as a passed proof. All scene/action/video QA remains separate.
    """
    plan = getattr(project, "creative_plan", None)
    if plan is None:
        return []
    beats, scenes = plan.beats, {s.id: s for s in project.scenes}
    order = {s.id: i for i, s in enumerate(project.scenes)}
    out: list[CreativeCheck] = []
    scene_errors, causal_errors, state_errors, math_errors, rhythm_errors, event_errors = [], [], [], [], [], []
    seen: set[str] = set()
    state = dict(plan.initial_state)
    prev_position = (-1, -1.0)
    reached = 0
    math_count = 0
    beats_on_grid = 0
    required_proof = 0
    actors: set[str] = set()

    for beat in beats:
        sc = scenes.get(beat.scene)
        if sc is None:
            scene_errors.append(f"{beat.id}: unknown scene {beat.scene}")
        else:
            pos = (order[beat.scene], beat.t)
            if pos < prev_position:
                scene_errors.append(f"{beat.id}: time or scene order goes backward")
            prev_position = pos
            if beat.t > sc.duration:
                scene_errors.append(f"{beat.id}: time {beat.t:g}s exceeds {sc.duration:g}s")
            if beat.actor:
                placed = {pl.character for pl in sc.placements}
                if beat.actor not in placed:
                    scene_errors.append(f"{beat.id}: actor {beat.actor} absent from {sc.id}")
        if beat.actor:
            actors.add(beat.actor)
        for cause in beat.causes:
            if cause not in seen:
                causal_errors.append(f"{beat.id}: cause {cause!r} not an earlier beat")
        if beat.kind not in ("setup", "transition") and not beat.causes:
            causal_errors.append(f"{beat.id}: {beat.kind} has no recorded cause")
        if beat.kind == "payoff":
            reached += 1
        seen.add(beat.id)

        for key, value in beat.requires.items():
            if state.get(key) != value:
                state_errors.append(f"{beat.id}: {key} needs {value!r}, found {state.get(key)!r}")
        state.update(beat.effects)
        if beat.math is not None:
            math_count += 1
            try:
                proof = verify_rewrite(beat.math.before, beat.math.after)
                if not proof.valid:
                    math_errors.append(f"{beat.id}: invalid math: {proof.explanation}")
            except (ValueError, TypeError, OverflowError, ZeroDivisionError, NotImplementedError) as exc:
                math_errors.append(f"{beat.id}: {type(exc).__name__}: {exc}")
        if beat.on_beat:
            beats_on_grid += 1
            if sc is None or sc.music is None:
                rhythm_errors.append(f"{beat.id}: on_beat requires a scene music grid")
            else:
                period = 60.0 / sc.music.bpm
                k = round((beat.film_t - sc.music.offset) / period)
                nearest = sc.music.offset + max(0, k) * period
                delta_frames = abs(nearest - beat.film_t) * project.fps
                if k < 0 or delta_frames > plan.beat_tolerance_frames + 1e-6:
                    rhythm_errors.append(f"{beat.id}: event is {delta_frames:.2f} frames off the musical grid")

        if beat.proof_event:
            required_proof += 1
            if events_by_scene is None:
                continue
            scene_events = events_by_scene.get(beat.scene, ())
            # Event data is produced by the simulation, never by the creative plan.
            if not any(matches(beat.proof_event, e) and abs(e.t - beat.t) <= beat.tolerance for e in scene_events):
                event_errors.append(f"{beat.id}: missing {beat.proof_event} near {beat.t:g}s (+/-{beat.tolerance:g}s)")

    out.append(_check("creative_scene_integrity", scene_errors, "all beat times, scenes and actors are valid"))
    out.append(_check("creative_causality", causal_errors, "all non-setup beats trace to earlier causes"))
    out.append(_check("creative_world_state", state_errors, "narrative state prerequisites and transitions agree"))
    out.append(_check("creative_math_truth", math_errors, f"{math_count} symbolic rewrite(s) verified"))
    out.append(_check("creative_music_sync", rhythm_errors, f"{beats_on_grid} event(s) align to the film-time music grid"))
    if events_by_scene is None:
        out.append(CreativeCheck("creative_simulation_evidence", "SKIP",
                                 f"{required_proof} declared engine event(s) still need simulation evidence"))
    elif required_proof:
        out.append(_check("creative_simulation_evidence", event_errors,
                          f"{required_proof} important event(s) verified in simulation"))
    else:
        out.append(CreativeCheck("creative_simulation_evidence", "SKIP", "no simulation events declared in creative plan"))

    kinds = {b.kind for b in beats}
    coverage = []
    if "payoff" not in kinds:
        coverage.append("no payoff beat")
    if plan.profile in ("math", "hybrid") and math_count == 0:
        coverage.append("mathematical profile has no symbolic rewrite")
    if plan.profile in ("arcade", "hybrid") and beats_on_grid < 2:
        coverage.append("arcade profile needs at least two film-clock rhythm events")
    if plan.profile in ("epic", "hybrid"):
        if len({b.scene for b in beats}) < 2:
            coverage.append("epic profile needs multi-scene continuity")
        if len(actors) < 2:
            coverage.append("epic profile needs at least two acting characters")
        if "reversal" not in kinds:
            coverage.append("epic profile needs a reversal")
    out.append(_check("creative_reference_coverage", coverage, f"{plan.profile} narrative capabilities declared"))
    if "payoff" in kinds and reached < 1:
        out.append(CreativeCheck("creative_payoff", "FAIL", "missing payoff"))
    else:
        out.append(CreativeCheck("creative_payoff", "PASS" if "payoff" in kinds else "FAIL",
                                 f"{reached} payoff(s) tied to causal beats" if reached else "no payoff"))

    # These are deliberately NOT automated. Numeric QA cannot certify that a
    # character feels alive, a fight is inventive, or a film matches a reference.
    out.append(CreativeCheck("creative_human_artistic_review", "SKIP",
                             "acting, choreography, story clarity and emotional payoff require 2+ human reviewers"))
    return out
