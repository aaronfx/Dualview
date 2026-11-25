"""Bridge full-story planning to existing typed native rehearsal.

Optional planner metadata is removed before ProjectSpec validation. No new
executor, provider call, or silent rewriting of an authored action queue.
"""
from __future__ import annotations
from copy import deepcopy

from .mission import TOOL_SCHEMA, ObjectiveTool, EnsembleTool
from .objective_planner import compile_objectives
from .ensemble_planner import plan_ensemble, topological, verify_task_evidence, verify_reactions
from ..scene.schema import ProjectSpec


def split_native_plans(data):
    if not isinstance(data, dict):
        raise ValueError("Story must be a project object")
    project = deepcopy(data)
    raw = project.pop("native_plans", [])
    if not isinstance(raw, list) or len(raw) > 4:
        raise ValueError("native_plans must be a list of at most four scene requests")
    plans = [TOOL_SCHEMA.validate_python(p) for p in raw]
    if any(not isinstance(p, (ObjectiveTool, EnsembleTool)) for p in plans):
        raise ValueError("Story native_plans support only objectives and ensemble")
    ids = [p.request.scene_id for p in plans]
    if len(ids) != len(set(ids)):
        raise ValueError("Only one native plan per scene")
    return project, plans


def execute_native_plans(project, plans, trace):
    """Plan against the native scene, retaining authored queues of other actors."""
    p = ProjectSpec.model_validate(project)
    contracts = []
    for call in plans:
        req = call.request
        sid = req.scene_id
        sc = p.scene(sid)
        entry = {"scene": sid, "tool": call.tool, "request": req.model_dump(mode="json")}
        trace.append(entry)
        if sc.duration > 60 or not sc.goals:
            raise ValueError(f"scene {sid}: native planning requires explicit goals and duration <=60s")
        actors = {t.actor for t in req.tasks}
        if actors & {a.character for a in sc.actions}:
            raise ValueError(f"scene {sid}: delegated actors must have no authored actions")
        if isinstance(call, ObjectiveTool):
            req, intents = compile_objectives(p, req)
            entry["intents"] = intents
        tasks = topological(req.tasks)
        selection = plan_ensemble(p, req)
        entry["native_report"] = selection.report()
        if selection.project is None or not any(t.accepted and t.name == selection.selected
                                                for t in selection.trials):
            reasons = "; ".join(t.reason for t in selection.trials)[:1200]
            raise ValueError(f"scene {sid}: native planning rejected all candidates: {reasons}")
        # Only import the winning actions, never candidate geometry, goals,
        # camera, cast, or another scene. Preserve original author contract.
        raw = p.model_dump(mode="json")
        scene = next(s for s in raw["scenes"] if s["id"] == sid)
        scene["actions"] = [a.model_dump(mode="json") for a in selection.project.scene(sid).actions]
        p = ProjectSpec.model_validate(raw)
        contracts.append((sid, tasks))
    return p, contracts


def verify_native_plans(project, contracts):
    """Recheck task outcomes after setup solving and event-cut resolution."""
    from ..scene.runtime import SceneRuntime
    for sid, tasks in contracts:
        sim = SceneRuntime(project, sid).simulate(physics_only=True)
        verify_task_evidence(tasks, sim.events, sim.duration)
        verify_reactions(project, sid, tasks, sim)
