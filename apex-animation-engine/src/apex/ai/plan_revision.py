"""D10.4 — structured partial-response handling.

Failure 3: the AI's first response is a full plan (thousands of tokens); later repair responses are tiny
(50-265 tokens). The old repair path treated a tiny targeted correction as a COMPLETE replacement project, discarding
the previously validated instructions.

A PlanRevision keeps the last validated action list for a scene and applies targeted patches to it — replacing,
updating, inserting or deleting individual actions — then re-compiles and validates the whole result through the
deterministic compiler. A valid patch is recorded as a new revision; an invalid patch is rejected and the previous
revision is preserved. The model may therefore return just the correction, not the entire project.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from ..scene.schema import ProjectSpec
from .plan_compiler import compile_scene, CompileError


@dataclass
class Revision:
    n: int
    actions: list
    repairs: list
    source: str            # "full" | "patch" | "rejected"
    note: str = ""


class PlanRevision:
    """Tracks the validated action plan for one scene and applies targeted partial corrections."""

    def __init__(self, project, scene_id: str):
        self.project = ProjectSpec.model_validate(project)
        self.scene_id = scene_id
        self.history: list[Revision] = []
        self._actions: list = []

    @property
    def actions(self):
        return deepcopy(self._actions)

    def _commit(self, actions, source, repairs, note=""):
        compiled, reps = compile_scene(self.project.model_dump(mode="json"), self.scene_id, actions=actions)
        validated = [a.model_dump(mode="json") for a in compiled.scenes[0].actions]
        self._actions = validated
        self.history.append(Revision(len(self.history) + 1, validated, [r.as_dict() for r in reps], source, note))
        return compiled

    def set_full(self, actions):
        """The first (full) AI plan. Compiled + validated; becomes revision 1."""
        return self._commit(list(actions), "full", [])

    def patch(self, ops):
        """Apply targeted ops to the CURRENT validated actions, preserving everything else. An op is one of:
          {"op":"replace","index":i,"action":{...}}  {"op":"update","index":i,"fields":{...}}
          {"op":"insert","index":i,"action":{...}}    {"op":"delete","index":i}
        A valid patch records a new revision; an invalid one is rejected and the previous revision is preserved."""
        if not self._actions:
            raise CompileError("no base plan to patch; call set_full first")
        candidate = deepcopy(self._actions)
        try:
            for op in (ops if isinstance(ops, list) else [ops]):
                kind = op["op"]
                if kind in ("replace", "update", "delete") and not (0 <= op["index"] < len(candidate)):
                    raise CompileError(f"patch index {op.get('index')} out of range")
                if kind == "replace":
                    candidate[op["index"]] = dict(op["action"])
                elif kind == "update":
                    candidate[op["index"]] = {**candidate[op["index"]], **op["fields"]}
                elif kind == "insert":
                    candidate.insert(op["index"], dict(op["action"]))
                elif kind == "delete":
                    candidate.pop(op["index"])
                else:
                    raise CompileError(f"unknown patch op {kind!r}")
            return self._commit(candidate, "patch", [])
        except (CompileError, KeyError, ValueError, TypeError) as e:
            # reject: keep the previous validated revision intact
            self.history.append(Revision(len(self.history) + 1, self.actions, [], "rejected", str(e)))
            raise CompileError(f"patch rejected, previous revision preserved: {e}")

    def report(self) -> dict:
        return {"scene": self.scene_id, "revisions": [
            {"n": r.n, "source": r.source, "actions": len(r.actions), "repairs": len(r.repairs), "note": r.note}
            for r in self.history], "current_actions": len(self._actions)}
