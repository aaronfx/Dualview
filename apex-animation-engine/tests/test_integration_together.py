"""Unified-branch integration: the reconciled subsystems co-exist and interoperate on one branch, offline.

Verifies that autonomous choreography (obstacle assessment), the D10 instruction compiler + self-repair, D10.5
independent story verification, the signed-term math transformation, Local Studio / local production, and the
OpenRouter-backed studio modules all import and work together without a paid call. It does not invoke any network
path — it proves the pieces reconciled by `apex-unified` are present and compatible in one process.
"""
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.goals import matches


def test_autonomous_choreography_adapts_and_traces():
    from apex.ai.obstacle_course import plan_course
    scene, rep = plan_course([{"id": "a", "center": [-200, 65], "size": [80, 130]},
                              {"id": "b", "center": [300, 80], "size": [80, 160]}],
                             start_x=-640, width=3200, max_jump_apex=260)
    sim = SceneRuntime(ProjectSpec.model_validate(scene), "s").simulate()
    assert any(matches("pick_up@iko[prop=core]", e) for e in sim.events)
    assert all("considered" in s and s["considered"] for s in rep["segments"])  # full decision trace


def test_d10_compiler_self_repairs_camera_prop_target():
    from apex.ai.plan_compiler import compile_scene
    base = {"schema_version": "0.1", "id": "x", "title": "x", "fps": 24, "width": 320, "height": 180, "seed": 1,
            "characters": [{"id": "iko", "name": "IKO"}],
            "environments": [{"id": "e", "room": {"width": 800, "height": 400, "entry_door": False},
                              "props": [{"id": "girder", "kind": "glyph", "glyph": "8", "position": [0, 60],
                                         "size": [40, 50], "mass": 1.0}], "obstacles": [], "exits": []}],
            "scenes": [{"id": "s", "environment": "e", "duration": 5.0, "placements": [{"character": "iko", "x": 0}],
                        "actions": [], "goals": [], "shots": [{"id": "sh", "start": 0, "end": 5.0,
                        "camera": {"mode": "static", "center": [0, 0]}}]}]}
    proj, repairs = compile_scene(base, "s", actions=[], shots=[{"id": "sh", "start": 0, "end": 5.0, "kind": "wide",
                    "camera": {"mode": "follow", "target": "prop:girder"}}])
    assert proj is not None and repairs, "camera prop-target was not self-repaired"


def test_d10_story_verification_and_math_and_studio_coexist():
    from apex.ai.story_check import detect_archetype
    from apex.scene.math_transposition import plan_additive_transposition
    import apex.ai.local_production as lp
    assert detect_archetype("Two allies: one is pinned, the other frees them, then they fist-bump.") == "rescue"
    assert callable(plan_additive_transposition)
    assert hasattr(lp, "create_from_brief") and hasattr(lp, "run_production")
