"""D10.1-D10.3 — deterministic schema-driven instruction compiler, reference resolver and self-repair.

The LLM communicates creative objectives; this compiler turns them into valid native instructions. It:
  * indexes the real scene (characters, props, obstacles, exits, tools, cameras);
  * resolves references scene-aware, correcting an unambiguous namespace/format error locally and
    REJECTING an ambiguous one rather than guessing;
  * repairs invalid parameter formats, missing mandatory parameters and wrong reference namespaces
    deterministically, recording every correction;
  * validates the result against the native schema + capability catalogue.

It never changes a physical outcome, removes a required story objective, or weakens validation. Repairs are
syntactic/reference only; feasibility and artistry remain the authority of native simulation and QA.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..scene.schema import ActionSpec, ProjectSpec
from .capabilities import REQUIRED, catalogue


class CompileError(ValueError):
    """An ambiguous or unresolvable reference, or a mandatory parameter that cannot be filled unambiguously."""


@dataclass
class Repair:
    where: str          # e.g. "scene.actions[2].target" or "shot[hero].camera.target"
    field: str
    was: Any
    now: Any
    reason: str

    def as_dict(self):
        return {"where": self.where, "field": self.field, "from": self.was, "to": self.now, "reason": self.reason}


@dataclass
class SceneIndex:
    chars: set
    props: set
    obstacles: set
    exits: set
    tools: set          # props usable as a tool/fulcrum (heavy/liftable set dressing)
    heavy: set          # props heavy enough to trap/lift (mass or 'solid')

    @classmethod
    def build(cls, project: ProjectSpec, scene_id: str) -> "SceneIndex":
        sc = next(s for s in project.scenes if s.id == scene_id)
        env = next(e for e in project.environments if e.id == sc.environment)
        chars = {pl.character for pl in sc.placements}
        props = {p.id for p in env.props}
        heavy = {p.id for p in env.props if (getattr(p, "mass", 0) or 0) >= 5 or getattr(p, "solid", False)}
        return cls(chars=chars, props=props, obstacles={o.id for o in env.obstacles},
                   exits={x.id for x in env.exits}, tools=props, heavy=heavy)

    def kind_of(self, name: str) -> Optional[str]:
        for kind, members in (("char", self.chars), ("prop", self.props),
                              ("obstacle", self.obstacles), ("exit", self.exits)):
            if name in members:
                return kind
        return None


_NS = ("char", "prop", "obstacle", "exit", "tool", "point")


def _split(ref: str):
    kind, sep, name = ref.partition(":")
    return (kind, name) if sep else (None, ref)


def resolve(ref: str, index: SceneIndex, expect: tuple[str, ...], where: str, repairs: list) -> str:
    """Resolve a single reference to a canonical `kind:name` within the allowed `expect` namespaces.
    Correct an unambiguous namespace error; reject an ambiguous or unknown reference."""
    kind, name = _split(ref)
    if kind == "point":
        return ref
    if kind in index.__dict__ or kind in _NS:
        # a namespaced ref: verify the name exists in that namespace; if the namespace is wrong but the
        # name is unambiguous elsewhere, correct it.
        actual = index.kind_of(name)
        if actual == kind or (kind == "tool" and name in index.tools):
            return ref
        if actual is not None and actual in expect:
            repairs.append(Repair(where, "namespace", ref, f"{actual}:{name}",
                                  f"'{name}' is a {actual}, not a {kind}"))
            return f"{actual}:{name}"
        raise CompileError(f"{where}: reference {ref!r} does not exist in the scene")
    # a bare name: resolve by the single namespace it belongs to, if unambiguous and allowed
    actual = index.kind_of(name)
    if actual is None:
        raise CompileError(f"{where}: unknown reference {name!r}")
    if actual not in expect:
        raise CompileError(f"{where}: {name!r} is a {actual}, not one of {expect}")
    repairs.append(Repair(where, "namespace", ref, f"{actual}:{name}", "bare name resolved to its namespace"))
    return f"{actual}:{name}"


def repair_camera(cam: dict, index: SceneIndex, where: str, repairs: list) -> dict:
    """Failure 1: camera.target must be a PLACED CHARACTER. A prop/obstacle reference belongs in
    camera.include; correct it there and choose valid framing (retarget to the sole character, else static)."""
    cam = dict(cam)
    tgt = cam.get("target")
    if tgt is None:
        return cam
    kind, name = _split(tgt)
    if tgt in index.chars:          # already a valid character id
        return cam
    if name in index.chars:         # "char:iko" form
        cam["target"] = name
        repairs.append(Repair(where, "camera.target", tgt, name, "stripped namespace from a character target"))
        return cam
    # not a character: move the object into include and fix framing
    obj_kind = index.kind_of(name)
    if obj_kind is None:
        raise CompileError(f"{where}: camera target {tgt!r} is neither a character nor a scene object")
    inc = list(cam.get("include") or [])
    canonical = f"{obj_kind}:{name}"
    if canonical not in inc:
        inc.append(canonical)
    cam["include"] = inc
    if len(index.chars) == 1:       # unambiguous: follow the only actor, keep the object in frame
        only = next(iter(index.chars))
        cam["target"] = only
        repairs.append(Repair(where, "camera.target", tgt, only,
                              f"{tgt} is a {obj_kind}; moved to include and retargeted to the only character"))
    else:                            # ambiguous subject: use static framing on the object's region
        cam["target"] = None
        cam["mode"] = "static"
        if cam.get("center") is None:
            cam["center"] = [0.0, 150.0]
        repairs.append(Repair(where, "camera.target", tgt, None,
                              f"{tgt} is a {obj_kind}; moved to include and switched to static framing"))
    return cam


_TARGET_EXPECT = {
    "lift": ("prop",), "push": ("prop", "obstacle"), "pick_up": ("prop",), "throw": ("prop",),
    "use_lever": ("prop", "obstacle"), "place": ("prop", "point"), "notice": ("char", "prop", "obstacle", "exit"),
    "point": ("char", "prop", "obstacle", "exit"), "look_at": ("char", "prop", "obstacle", "exit"),
    "offer_hand": ("char",), "gesture": ("char",), "strike": ("char",), "grab_swing": ("obstacle", "prop"),
    "reach_exit": ("exit",), "vault": ("obstacle",), "climb": ("obstacle",), "catch_ledge": ("obstacle",),
    "pull_up": ("obstacle", "char"),
}


def _infer_missing(action: dict, param: str, index: SceneIndex, where: str, repairs: list):
    """Failure 2: a mandatory parameter is missing. Fill it ONLY from an unambiguous scene candidate; otherwise
    reject (never guess). For a 'target' this means exactly one plausible object of the expected kind."""
    typ = action["type"]
    if param != "target":
        raise CompileError(f"{where}: action {typ!r} is missing mandatory parameter {param!r}")
    expect = _TARGET_EXPECT.get(typ, ("prop", "obstacle"))
    pool = []
    if "prop" in expect:
        pool += sorted(index.heavy if typ in ("lift", "use_lever", "push") else index.props)
    for kind in expect:
        if kind == "prop":
            continue
        pool += sorted(getattr(index, {"obstacle": "obstacles", "exit": "exits", "char": "chars"}[kind], set()))
    # exclude the acting character itself
    pool = [p for p in pool if p != action.get("character")]
    if len(set(pool)) == 1:
        kind = index.kind_of(pool[0])
        ref = f"{kind}:{pool[0]}"
        action["target"] = ref
        repairs.append(Repair(where, "target", None, ref,
                              f"{typ} had no target; the scene has exactly one {kind} candidate"))
        return
    raise CompileError(f"{where}: {typ} is missing a target and the scene has {len(set(pool))} candidates "
                       f"({sorted(set(pool))}); refusing to guess")


def repair_action(action: dict, index: SceneIndex, where: str, repairs: list) -> dict:
    action = dict(action)
    typ = action.get("type")
    required = REQUIRED.get(typ, [])
    for param in required:
        if param.startswith("target_x OR"):
            if action.get("target_x") is None and not action.get("target"):
                raise CompileError(f"{where}: {typ} needs target_x or a target")
            continue
        if param in ("target", "tool", "fulcrum", "switch", "until", "move", "gesture", "face", "clip",
                     "height") and not action.get(param):
            if param in ("target", "tool", "fulcrum", "switch"):
                _infer_missing(action, "target" if param in ("target", "switch") else param, index, where, repairs)
            else:
                raise CompileError(f"{where}: {typ} is missing mandatory parameter {param!r}")
    # resolve/repair the reference namespace of a target that is present
    if action.get("target") and typ in _TARGET_EXPECT:
        action["target"] = resolve(action["target"], index, _TARGET_EXPECT[typ], where + ".target", repairs)
    return action


def compile_scene(project, scene_id: str, actions=None, shots=None):
    """Compile a creative plan (actions and/or camera shots) into validated native instructions.
    Returns (ProjectSpec, [Repair]). Raises CompileError on an ambiguous/unresolvable reference."""
    p = ProjectSpec.model_validate(project)
    index = SceneIndex.build(p, scene_id)
    data = p.model_dump(mode="json")
    scene = next(s for s in data["scenes"] if s["id"] == scene_id)
    repairs: list = []
    if actions is not None:
        fixed = []
        for i, a in enumerate(actions):
            a = a if isinstance(a, dict) else a.model_dump(mode="json")
            fixed.append(repair_action(a, index, f"scene.actions[{i}]({a.get('type')})", repairs))
        scene["actions"] = [ActionSpec.model_validate(a).model_dump(mode="json") for a in fixed]
    if shots is not None:
        fixed_shots = []
        for sh in shots:
            sh = dict(sh if isinstance(sh, dict) else sh.model_dump(mode="json"))
            sh["camera"] = repair_camera(sh.get("camera", {}), index, f"shot[{sh.get('id')}]", repairs)
            fixed_shots.append(sh)
        scene["shots"] = fixed_shots
    return ProjectSpec.model_validate(data), repairs


def compiler_report(repairs) -> dict:
    return {"method": "deterministic schema + reference resolver; no model call, no physics change",
            "repairs": [r.as_dict() for r in repairs], "count": len(repairs),
            "catalogue_version": catalogue()["version"]}
