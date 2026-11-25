"""D10.1-D10.3 deterministic compiler / reference resolver / self-repair — offline fixtures that reproduce the two
reported AI validation failures and prove they are corrected (or rejected when ambiguous) with NO API calls and NO
change to physical outcomes."""
import pytest

from apex.ai.plan_compiler import compile_scene, compiler_report, CompileError
from apex.scene.schema import ProjectSpec


def _scene(props, chars=("iko",)):
    return {
        "schema_version": "0.1", "id": "fix", "title": "fix", "fps": 24, "width": 1280, "height": 720, "seed": 1,
        "characters": [{"id": c, "name": c.upper()} for c in chars],
        "environments": [{"id": "e", "room": {"width": 2000, "height": 900, "entry_door": False},
                          "props": props, "obstacles": [], "exits": []}],
        "scenes": [{"id": "fix", "environment": "e", "duration": 10.0,
                    "placements": [{"character": c, "x": -200 + 120 * i, "facing": 1} for i, c in enumerate(chars)],
                    "actions": [], "goals": [],
                    "shots": [{"id": "s", "kind": "wide", "start": 0, "end": 10.0,
                               "camera": {"mode": "follow", "target": "iko", "view_height": 700}}]}],
    }


GIRDER = {"id": "girder", "kind": "glyph", "glyph": "8", "position": [0, 60], "size": [120, 120], "mass": 9, "solid": True}


# ---- Failure 1: invalid camera reference (prop in camera.target) --------------------------------------------
def test_f1_camera_target_prop_is_moved_to_include_and_retargeted():
    proj = _scene([GIRDER])
    bad_shots = [{"id": "s", "kind": "wide", "start": 0, "end": 10.0,
                  "camera": {"mode": "follow", "target": "prop:girder", "view_height": 700}}]
    p, repairs = compile_scene(proj, "fix", shots=bad_shots)
    cam = p.scenes[0].shots[0].camera
    assert cam.target == "iko"                       # retargeted to the only character
    assert "prop:girder" in cam.include              # object kept in frame instead
    assert any(r.field == "camera.target" for r in repairs)
    ProjectSpec.model_validate(p.model_dump(mode="json"))   # the repaired project is natively valid


def test_f1_ambiguous_subject_uses_static_framing():
    proj = _scene([GIRDER], chars=("iko", "pell"))
    bad_shots = [{"id": "s", "kind": "wide", "start": 0, "end": 10.0,
                  "camera": {"mode": "follow", "target": "obstacle:girder", "view_height": 700}}]
    p, repairs = compile_scene(proj, "fix", shots=bad_shots)
    cam = p.scenes[0].shots[0].camera
    assert cam.target is None and cam.mode == "static" and cam.center is not None
    assert "prop:girder" in cam.include              # namespace also corrected (obstacle -> prop)


# ---- Failure 2: missing mandatory action parameter (lift without target) ------------------------------------
def test_f2_lift_without_target_infers_sole_candidate():
    proj = _scene([GIRDER])
    p, repairs = compile_scene(proj, "fix", actions=[{"character": "iko", "type": "lift"}])
    assert p.scenes[0].actions[0].target == "prop:girder"
    assert any(r.field == "target" for r in repairs)


def test_f2_lift_without_target_rejects_when_ambiguous():
    two = [GIRDER, {"id": "crate", "kind": "crate", "position": [300, 45], "size": [90, 90], "mass": 9, "solid": True}]
    proj = _scene(two)
    with pytest.raises(CompileError) as exc:
        compile_scene(proj, "fix", actions=[{"character": "iko", "type": "lift"}])
    assert "refusing to guess" in str(exc.value)     # ambiguous -> rejected, never guessed


def test_f2_missing_nonfillable_param_is_rejected_not_guessed():
    proj = _scene([GIRDER])
    with pytest.raises(CompileError):
        compile_scene(proj, "fix", actions=[{"character": "iko", "type": "strike", "target": "char:iko"}])  # missing move


# ---- reference resolver: correct unambiguous, reject unknown -------------------------------------------------
def test_bare_name_target_resolved_to_namespace():
    proj = _scene([GIRDER])
    p, repairs = compile_scene(proj, "fix", actions=[{"character": "iko", "type": "pick_up", "target": "girder"}])
    assert p.scenes[0].actions[0].target == "prop:girder"


def test_unknown_reference_rejected():
    proj = _scene([GIRDER])
    with pytest.raises(CompileError):
        compile_scene(proj, "fix", actions=[{"character": "iko", "type": "pick_up", "target": "prop:ghost"}])


def test_valid_plan_passes_without_repairs():
    proj = _scene([GIRDER])
    p, repairs = compile_scene(proj, "fix", actions=[{"character": "iko", "type": "pick_up", "target": "prop:girder"}])
    assert repairs == []
    assert compiler_report(repairs)["count"] == 0
