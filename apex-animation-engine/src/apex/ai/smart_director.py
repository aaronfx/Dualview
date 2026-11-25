"""D1 Smart Director: typed tools, bounded native rehearsal and honest rendering.

This is a local orchestration layer, not an alternate animation engine.
LLM output never directly controls physics or declares a successful event.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from math import ceil
from pathlib import Path
from typing import Literal
import json
from pydantic import BaseModel, ConfigDict, Field
from ..scene.schema import ActionSpec, ProjectSpec
from ..scene.goals import parse_goal, check_event, matches
from .capabilities import catalogue, validate_candidate

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class CrossRequest(Strict):
    scene_id: str
    actor: str
    obstacle_id: str
    goal_prop_id: str
    movable_prop_id: str | None = None
    pacing: Literal["active", "measured"] = "active"
    max_jump_apex: float = Field(210, ge=40, le=420)
    max_trials: int = Field(6, ge=1, le=8)

class ActionCandidate(Strict):
    name: str = Field(min_length=1, max_length=80)
    actions: list[ActionSpec] = Field(min_length=1, max_length=160)

@dataclass
class Trial:
    name: str
    accepted: bool
    reason: str
    goals: list = field(default_factory=list)
    checks: list = field(default_factory=list)
    payoff: float | None = None

@dataclass
class Selection:
    project: ProjectSpec | None
    scene_id: str
    trials: list[Trial]
    selected: str | None = None
    def report(self):
        return {"selected": self.selected, "scene": self.scene_id,
                "accepted": self.project is not None, "trials": [asdict(t) for t in self.trials],
                "scope": "native rehearsal; artistic approval is separate"}

def ordered_evidence(goals, events, duration):
    """Distinct, chronological, actual events only; no tolerant out-of-order matches."""
    if not goals:
        raise ValueError("Explicit outcome goals required")
    indexed = sorted(enumerate(e for e in events if 0 <= e.t <= duration),
                     key=lambda pair: (pair[1].t, pair[0]))
    cursor, proof = 0, []
    for g in goals:
        typ, _, _ = parse_goal(g)
        check_event(typ, "Smart Director goal")
        for i in range(cursor, len(indexed)):
            e = indexed[i][1]
            if matches(g, e):
                proof.append({"goal": g, "t": float(e.t), "event": e.type,
                              "actor": e.character, "data": dict(e.data)})
                cursor = i + 1
                break
        else:
            raise ValueError(f"Missing ordered native goal: {g}")
    return proof

def _audit(project, scene_id, name, *, extra_goal=None, trim=False, actor=None):
    from ..scene.runtime import SceneRuntime
    from ..qa.inspector import Inspector, gate_of
    from ..render.pipeline import build_camera
    from ..scene.solver import stuck_characters
    rt = SceneRuntime(project, scene_id, strict=False)
    sim = rt.simulate()
    sc = project.scene(scene_id)
    proof = ordered_evidence(sc.goals, sim.events, sim.duration)
    if extra_goal:
        ordered_evidence([extra_goal, sc.goals[-1]], sim.events, sim.duration)
    failures = [f"{cid}: {c.violation}" for cid, c in sim.controllers.items() if c.violation]
    failures += stuck_characters(sim)
    failures += [f"{cid}: unfinished {c.cur.type if c.cur else 'queue'}"
                 for cid, c in sim.controllers.items()
                 if c.queue or (c.cur is not None and c.cur.type not in ("idle", "guard"))]
    failures += [f"{e.type}@{e.character}" for e in sim.events if e.type == "action_impossible"]
    if failures:
        raise ValueError("; ".join(failures))
    payoff = proof[-1]["t"]
    # This diagnostic is advisory; do not convert intentional occlusion into fake physics failures.
    from ..qa.visual_prop_audit import inspect_visual_props
    visual_warnings = inspect_visual_props(rt)
    if trim:
        # Never shorten a required actor's physical action: cross mission only.
        from ..scene.pacing import actor_pace
        tail = actor_pace("active").final_tail
        last = max([payoff, *[e.t for e in sim.events if e.type == "act" and e.character == actor]])
        duration = min(sc.duration, ceil(max(last + 1.25, payoff + tail) * project.fps) / project.fps)
        raw = project.model_dump(mode="json")
        scene = next(s for s in raw["scenes"] if s["id"] == scene_id)
        scene["duration"] = duration
        # Wide establish then native tracking, followed by a readable payoff.
        env = project.environment(sc.environment)
        aspect = project.width / project.height
        establish = min(.83, max(.5, payoff - 1.0))
        cut = min(duration - .5, max(establish + .5, payoff - .15))
        shots = [
            {"id":"establish", "kind":"establishing", "start":0, "end":establish,
             "camera":{"mode":"static", "center":[0, 240], "view_height":max(600,env.room.width/aspect+60)}},
            {"id":"pursuit", "kind":"tracking", "start":establish, "end":cut,
             "camera":{"mode":"follow","target":actor,"view_height":570,"offset":[45,40],"lead":.17}},
            {"id":"payoff", "kind":"medium", "start":cut, "end":duration,
             "camera":{"mode":"follow","target":actor,"view_height":400,"offset":[10,35],"lead":.05},
             "fade_out":.5},
        ]
        if cut - establish < .5 or duration - cut < .5:
            shots = [{"id":"tracking","kind":"tracking","start":0,"end":duration,
                      "camera":{"mode":"follow","target":actor,"view_height":570}}]
        scene["shots"] = shots
        project = ProjectSpec.model_validate(raw)
        # Replay the actual staged version; never transfer evidence from a trial.
        return _audit(project, scene_id, name, extra_goal=extra_goal)
    report = Inspector(rt, build_camera(rt, project.width / project.height),
                       project.fps, (project.width, project.height)).run(check_determinism=False)
    bad = [c.name for c in report.checks if c.status == "FAIL"]
    checks = [{"name": c.name, "status": c.status, "gate": gate_of(c.name)} for c in report.checks]
    checks += [{"name": "visual_prop_overlap", "status": "WARN", "gate": "cinematic", "details": w} for w in visual_warnings]
    if bad:
        return None, Trial(name, False, "Native Inspector rejected: " + ", ".join(bad),
                           proof, checks, payoff)
    return project, Trial(name, True, "Native event, controller and Inspector gates passed",
                          proof, checks, payoff)

def rehearse(project, scene_id, candidates, *, max_trials=6, extra_goals=None, trim_actor=None):
    if not 1 <= max_trials <= 8:
        raise ValueError("Trial limit 1..8")
    project = ProjectSpec.model_validate(project)
    scene = project.scene(scene_id)
    if not scene.goals or not 0 < scene.duration <= 60:
        raise ValueError("Rehearsal requires explicit goals and scene duration <= 60 seconds")
    trials, accepted = [], []
    from itertools import islice
    for raw in islice(candidates, max_trials):
        name = raw.name if isinstance(raw, ActionCandidate) else raw.get("name", "invalid")
        try:
            c = ActionCandidate.model_validate(raw)
            p = validate_candidate(project, scene_id, c.actions)
            winner, trial = _audit(p, scene_id, name, extra_goal=(extra_goals or {}).get(name),
                                   trim=trim_actor is not None, actor=trim_actor)
            trials.append(trial)
            if winner is not None:
                accepted.append((trial.payoff, name, winner))
        except (ValueError, RuntimeError, KeyError, TypeError, IndexError, ArithmeticError) as exc:
            trials.append(Trial(name, False, f"{type(exc).__name__}: {exc}"))
    if not accepted:
        return Selection(None, scene_id, trials)
    _, name, winner = min(accepted, key=lambda item: (item[0], item[1]))
    return Selection(winner, scene_id, trials, name)

def cross_and_collect(project, request: CrossRequest):
    from ..scene.autochoreo import Objective, propose
    project = ProjectSpec.model_validate(project)
    request = CrossRequest.model_validate(request)
    sc = project.scene(request.scene_id)
    if not 4 <= sc.duration <= 60:
        raise ValueError("Crossing scene must be 4..60 seconds")
    obj = Objective(scene_id=sc.id, actor=request.actor, obstacle_id=request.obstacle_id,
                    goal_prop_id=request.goal_prop_id, movable_prop_id=request.movable_prop_id,
                    max_trial_seconds=sc.duration, max_jump_apex=request.max_jump_apex,
                    pacing=request.pacing)
    proposals = propose(project, obj)
    target = f"pick_up@{request.actor}[prop={request.goal_prop_id}]"
    raw = project.model_dump(mode="json")
    scene = next(s for s in raw["scenes"] if s["id"] == sc.id)
    scene["goals"] = list(sc.goals)
    if target not in scene["goals"]:
        scene["goals"].append(target)
    # Preserve every other actor's native action queue. Rehearse the entire scene.
    others = [a for a in scene["actions"] if a["character"] != request.actor]
    p = ProjectSpec.model_validate(raw)
    candidates, extra = [], {}
    for c in proposals:
        # Existing route proposal may have a required physical event. Never accept
        # a claimed climb/vault without the corresponding event.
        candidates.append({"name":c.name, "actions":[*c.actions, *others]})
        if c.required_event and scene["goals"][-1] == target:
            extra[c.name] = f"{c.required_event}@{request.actor}"
    return rehearse(p, sc.id, candidates, max_trials=request.max_trials,
                    extra_goals=extra,
                    trim_actor=request.actor if len(sc.placements)==1 and scene["goals"]==[target] else None)

def write_selection(selection: Selection, directory: Path):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory/"director_trace.json").write_text(json.dumps(selection.report(), indent=2, default=str), encoding="utf-8")
    if selection.project is not None:
        (directory/"project.json").write_text(selection.project.model_dump_json(indent=2), encoding="utf-8")

def render_selection(selection: Selection, directory: Path, *, final=False):
    if selection.project is None or not any(t.name==selection.selected and t.accepted for t in selection.trials):
        raise ValueError("No native rehearsal accepted; render refused")
    from ..render.pipeline import render_scene
    import subprocess
    directory = Path(directory)
    write_selection(selection, directory)
    project = selection.project
    # A new run must not reuse a prior success marker.
    marker = directory/"render_status.json"
    marker.unlink(missing_ok=True)
    path = directory/"video.mp4"
    result = render_scene(project, selection.scene_id, str(path), samples=2 if final else 1,
                          qa=True, preview_scale=1.0 if final else min(1.,540/project.height),
                          qa_path=str(directory/"qa.json"), review_dir=str(directory/"review"))
    if result.qa is None or not result.qa.passed:
        raise RuntimeError("Native render QA failed; inspect qa.json and video as rejected preview")
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(path),"-f","null","-"], check=True)
    marker.write_text(json.dumps({"native_render":"PASS","artistic_review":"pending",
                                 "frames":result.frames,"video":str(path)},indent=2),encoding="utf-8")
    return path

def plan_story(story: str, *, offline=False, reason: str=""):
    """Use the existing StoryDirector budget controls; never silently fake paid AI."""
    from .director import StoryDirector
    d = StoryDirector.from_env(offline=offline, reason=reason)
    if not offline and d.provider is None:
        raise ValueError("No AI provider configured; explicit --offline required for template mode")
    project = d.plan(story)
    return project, {"planner":d.name, "attempts":d.log,
                     "adjustments":d.engine_report, "cost":d.cost_record,
                     "scope":"StoryDirector plan; independent native QA and artistic review required"}
