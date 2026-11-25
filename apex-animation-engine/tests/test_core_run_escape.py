"""Production-only verification; native engine is not changed."""
import runpy
from pathlib import Path
from apex.scene.schema import ProjectSpec
ROOT=Path(__file__).resolve().parents[1]
module=runpy.run_path(str(ROOT/"examples/build_core_run_escape.py"))
def test_escape_cut_preserves_rigs_and_tracks():
    import json
    p=module["build"]()
    core=json.loads((ROOT/"examples/core_run.json").read_text())
    assert p["characters"]==core["characters"]
    original={s["id"]:s for s in core["scenes"]}
    assert all(s["actions"]==original[s["id"]]["actions"] for s in p["scenes"] if s["id"] in original)
    assert abs(sum(s["duration"] for s in p["scenes"])-180)<.001
    assert len(ProjectSpec.model_validate(p).scenes)==6
