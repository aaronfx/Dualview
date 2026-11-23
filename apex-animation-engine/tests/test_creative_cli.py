"""Native ProjectSpec + CLI integration for the creative-storyboard gate."""
import json
from apex.cli import main
from apex.ai.director import StoryDirector, system_prompt
import pytest
from apex.scene.schema import ProjectSpec


def I(v): return {"op": "int", "value": v}
def E(op, a, b): return {"op": op, "args": [a, b]}


def minimal(verified=True):
    data = {"schema_version": "0.1", "id": "creative_probe", "title": "Creative QA Probe",
            "fps": 24, "width": 640, "height": 360,
            "characters": [{"id": "kai", "name": "KAI"}],
            "environments": [{"id": "e", "room": {"width": 1200, "height": 900, "entry_door": False},
                              "dust": 0}],
            "scenes": [{"id": "s", "environment": "e", "duration": 4.0,
                        "placements": [{"character": "kai", "x": -350}],
                        "shots": [{"id": "wide", "start": 0, "end": 4,
                                   "camera": {"mode": "static", "center": [0, 200]}}],
                        "actions": [{"character": "kai", "type": "idle", "duration": 3}]}]}
    data["creative_plan"] = {
        "profile": "math", "premise": "A real equation becomes a physical obstacle",
        "beats": [
            {"id": "start", "scene": "s", "t": 0, "kind": "setup", "intent": "a mathematical lock", "actor": "kai"},
            {"id": "solve", "scene": "s", "t": 1, "kind": "response", "intent": "derive the solution",
             "actor": "kai", "causes": ["start"],
             "math": {"before": E("add", I(2), I(2)), "after": I(4 if verified else 5)}},
            {"id": "end", "scene": "s", "t": 2, "kind": "payoff", "intent": "escape the lock",
             "actor": "kai", "causes": ["solve"]}
        ]
    }
    return data


def test_projectspec_accepts_optional_creative_plan():
    p = ProjectSpec.model_validate(minimal())
    assert p.creative_plan.profile == "math" and len(p.creative_plan.beats) == 3
    old = minimal()
    del old["creative_plan"]
    assert ProjectSpec.model_validate(old).creative_plan is None


def test_cli_returns_zero_for_valid_proof_and_nonzero_for_wrong_math(tmp_path):
    src = tmp_path / "p.json"
    report = tmp_path / "report.json"
    src.write_text(json.dumps(minimal()), encoding="utf-8")
    assert main(["creative-qa", str(src), "--report", str(report)]) == 0
    checks = {x["name"]: x for x in json.loads(report.read_text())["checks"]}
    assert checks["creative_math_truth"]["status"] == "PASS"
    assert checks["creative_human_artistic_review"]["status"] == "SKIP"
    src.write_text(json.dumps(minimal(verified=False)), encoding="utf-8")
    assert main(["creative-qa", str(src)]) == 2


def test_ai_director_understands_and_proves_creative_story_contract():
    assert "OPTIONAL CREATIVE PLAN" in system_prompt()
    assert "creative_plan" in system_prompt()
    StoryDirector._dry_run(ProjectSpec.model_validate(minimal(verified=True)))
    with pytest.raises(ValueError, match="creative plan contradicted"):
        StoryDirector._dry_run(ProjectSpec.model_validate(minimal(verified=False)))
