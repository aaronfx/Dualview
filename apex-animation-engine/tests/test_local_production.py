from pathlib import Path
import runpy
import pytest
from apex.ai.local_production import safe_project,stage_project,scene_fingerprint,approve_preview
from apex.qa.video_critic import inspect_video
from apex.scene.schema import ProjectSpec
def world():
    return ProjectSpec.model_validate(runpy.run_path(str(Path(__file__).parents[1]/"examples/build_impossible_crossing.py"))["world"]())
def test_stage_and_refuse_overwrite(tmp_path):
    p=world();stage_project(p,tmp_path)
    with pytest.raises(ValueError,match="already exists"):stage_project(p,tmp_path)
def test_cache_fingerprint_changes_with_style():
    p=world();s=p.scenes[0]
    k=scene_fingerprint(p,s,{"scale":1}, "engine")
    assert k!=scene_fingerprint(p,s,{"scale":.5},"engine")
    raw=p.model_dump(mode="json");raw["characters"][0]["style"]["body_color"]="#123456"
    q=ProjectSpec.model_validate(raw)
    assert k!=scene_fingerprint(q,q.scenes[0],{"scale":1},"engine")
def test_no_approval_without_preview(tmp_path):
    stage_project(world(),tmp_path)
    with pytest.raises(FileNotFoundError):approve_preview(tmp_path,"review")
