"""Offline full-story bridge: real native rehearsal, no paid model calls."""
import json
from copy import deepcopy

import pytest
from apex.ai.director import StoryDirector, PlanningError
from apex.ai.story_native_plans import split_native_plans, execute_native_plans
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.goals import matches


def world():
    return {
        "schema_version":"0.1", "id":"native_story", "title":"A discovery", "fps":24,
        "width":1280, "height":720, "seed":1,
        "characters":[{"id":"iko","name":"IKO"}],
        "environments":[{"id":"e","room":{"width":1200,"height":700,"entry_door":False},
                         "props":[{"id":"spark","kind":"glyph","glyph":"8","position":[100,40],
                                   "size":[40,60],"mass":1,"solid":False}]}],
        "scenes":[{"id":"s","environment":"e","duration":3,
                   "placements":[{"character":"iko","x":-100,"facing":1}],
                   "actions":[], "goals":["notice@iko[target=prop:spark]"],
                   "shots":[{"id":"wide","start":0,"end":3,"kind":"wide",
                             "camera":{"mode":"follow","target":"iko","view_height":580}}]}],
        "native_plans":[{"tool":"objectives","request":{"scene_id":"s","max_trials":1,
                           "tasks":[{"id":"find","actor":"iko","kind":"observe","target":"prop:spark"}]}}]
    }


class Fake:
    name="test-provider"
    def __init__(self, raw):
        self.raw=raw
        self.calls=0
    def complete(self, system, prompt, max_tokens=0):
        self.calls+=1
        return json.dumps(self.raw)


def test_story_uses_existing_native_objective_rehearsal():
    raw=world()
    original=deepcopy(raw)
    provider=Fake(raw)
    director=StoryDirector(provider,max_repairs=0)
    p=director.plan("IKO notices the symbol.")
    assert provider.calls==1 and raw==original
    assert p.scene("s").actions[0].type=="notice"
    assert director.log[0]["native_planning"][0]["native_report"]["accepted"]
    assert p.scene("s").goals==original["scenes"][0]["goals"]
    sim=SceneRuntime(p,"s").simulate(physics_only=True)
    assert any(matches(p.scene("s").goals[0],e) for e in sim.events)


def test_conflicting_authored_queue_is_not_overwritten():
    raw=world()
    raw["scenes"][0]["actions"]=[{"character":"iko","type":"idle","duration":1}]
    p,plans=split_native_plans(raw)
    with pytest.raises(ValueError,match="no authored actions"):
        execute_native_plans(ProjectSpec.model_validate(p),plans,[])


def test_unknown_target_is_rejected_by_story_director():
    raw=world()
    raw["native_plans"][0]["request"]["tasks"][0]["target"]="prop:missing"
    with pytest.raises(PlanningError,match="does not exist"):
        StoryDirector(Fake(raw),max_repairs=0).plan("IKO notices a missing symbol.")


def test_reject_duplicate_delegation_and_non_story_tools():
    raw=world()
    raw["native_plans"]*=2
    with pytest.raises(ValueError,match="one native plan"):
        split_native_plans(raw)
    raw["native_plans"]=[{"tool":"unsupported","reason":"test"}]
    with pytest.raises(ValueError,match="only objectives and ensemble"):
        split_native_plans(raw)


def test_ordinary_authored_project_is_not_modified():
    raw=world()
    raw.pop("native_plans")
    p,plans=split_native_plans(raw)
    result,contracts=execute_native_plans(ProjectSpec.model_validate(p),plans,[])
    assert p==raw and contracts==[]
    assert result==ProjectSpec.model_validate(raw)
