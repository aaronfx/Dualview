"""CLI contract: the AI Director or Codex can invoke APEX's bounded tactical planner."""
import importlib.util
import json
from pathlib import Path

from apex.cli import main
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def _world():
    path = Path(__file__).resolve().parents[1] / "examples" / "build_impossible_crossing.py"
    spec = importlib.util.spec_from_file_location("build_m3_for_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.world()


def test_cli_emits_a_native_replayable_project_and_explains_rejections(tmp_path):
    source, project, report = (tmp_path / x for x in ("world.json", "chosen.json", "proof.json"))
    source.write_text(json.dumps(_world()), encoding="utf-8")
    code = main([
        "choreo", str(source), "--scene", "cross", "--actor", "iko",
        "--obstacle", "barrier", "--goal-prop", "spark",
        "--movable-prop", "crate", "--max-jump", "210", "--max-seconds", "19",
        "--prefer-prop-interaction", "-o", str(project), "--report", str(report)
    ])
    assert code == 0
    assert source.exists() and project.exists() and report.exists()
    proof = json.loads(report.read_text())
    assert proof["succeeded"] and proof["chosen"] in {"climb_then_drop", "shift_crate_then_climb"}
    assert len(proof["trials"]) == 6
    assert any(not t["accepted"] for t in proof["trials"])
    built = ProjectSpec.model_validate_json(project.read_text())
    assert any(a.type == "climb" for a in built.scenes[0].actions)
    sim = SceneRuntime(built, "cross").simulate(physics_only=True)
    assert any(e.type == "pick_up" and e.character == "iko" and e.data.get("prop") == "spark"
               for e in sim.events)
