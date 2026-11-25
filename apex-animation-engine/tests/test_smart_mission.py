from pathlib import Path
import json
import runpy
import pytest
from apex.ai.mission import TOOL_SCHEMA,run_mission,dispatch
from apex.ai.smart_director import Selection,Trial
from apex.scene.schema import ProjectSpec

def world():
    builder=runpy.run_path(str(Path(__file__).parents[1]/"examples/build_impossible_crossing.py"))
    return ProjectSpec.model_validate(builder["world"]())

def test_unknown_tool_rejected():
    with pytest.raises(ValueError):
        TOOL_SCHEMA.validate_json('{"tool":"shell","command":"run arbitrary code"}')

def test_tool_scene_is_not_changeable():
    call=TOOL_SCHEMA.validate_python({"tool":"cross_and_collect","request":{"scene_id":"other","actor":"iko","obstacle_id":"barrier","goal_prop_id":"spark"}})
    with pytest.raises(ValueError,match="cannot change"):
        dispatch(world(),"cross",call)

def test_mission_repairs_invalid_call(monkeypatch):
    p=world()
    class Fake:
        name="test-provider"
        calls=0
        def complete(self,system,user,max_tokens=0):
            self.calls+=1
            if self.calls==1:return '{"tool":"invented"}'
            assert "rejection" in user
            return json.dumps({"tool":"cross_and_collect","request":{"scene_id":"cross","actor":"iko","obstacle_id":"barrier","goal_prop_id":"spark"}})
    def accepted(project,request):
        return Selection(project,request.scene_id,[Trial("test",True,"test double")],"test")
    monkeypatch.setattr("apex.ai.mission.cross_and_collect",accepted)
    result,trace=run_mission(p,"cross","Collect the spark",Fake())
    assert result.project is p and trace["status"]=="accepted" and len(trace["attempts"])==2

def test_no_provider_claims_success_for_unsupported():
    class Fake:
        name="test-provider"
        def complete(self,*args,**kwargs):return '{"tool":"unsupported","reason":"Not implemented"}'
    result,trace=run_mission(world(),"cross","Unsupported",Fake())
    assert result.project is None and trace["status"]=="failed"
