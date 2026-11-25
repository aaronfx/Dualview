"""Controlled reaction regression: real APEX projectile trajectories."""
import pytest
from apex.ai.reaction_proof import verify_projectile_reaction
from apex.ai.objective_planner import compile_objectives
from apex.ai.ensemble_planner import compile_ensemble, verify_reactions
from apex.ai.capabilities import validate_candidate
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def world(z=0):
    return ProjectSpec.model_validate({
        "schema_version":"0.1","id":"reaction","title":"reaction","fps":24,
        "width":640,"height":360,"seed":3,
        "characters":[{"id":c,"name":c.upper(),"proportions":{"spine":30,"chest":28,"head":24,
                         "thigh":44,"shin":42}} for c in ("kai","rho")],
        "environments":[{"id":"e","room":{"width":1800,"height":900,"entry_door":False},
                         "props":[{"id":"plus","kind":"glyph","glyph":"+","position":[-300,30],
                                   "size":[56,56],"mass":6}],"dust":0}],
        "scenes":[{"id":"s","environment":"e","duration":9,
                   "placements":[{"character":"kai","x":-500,"facing":1},
                                 {"character":"rho","x":300,"facing":-1,"z":z}],
                   "actions":[{"character":"kai","type":"pick_up","target":"prop:plus"},
                              {"character":"kai","type":"walk_to","target_x":-150},
                              {"character":"kai","type":"throw","target":"char:rho"}],
                   "goals":["throw@kai[prop=plus,target=char:rho]","dodge@rho"],
                   "shots":[{"id":"a","start":0,"end":9,"camera":{"mode":"follow","target":"kai","view_height":600}}]}]})


def candidate(z=0):
    p=world(z)
    req={"scene_id":"s","max_trials":1,"tasks":[{"id":"avoid","actor":"rho","kind":"evade_projectile",
          "target":"char:kai","prop":"prop:plus"}]}
    compiled,_=compile_objectives(p,req)
    base,choices,tasks=compile_ensemble(p,compiled)
    return validate_candidate(base,"s",choices[0].actions),tasks


def test_native_dodge_avoids_a_throw_that_hits_stationary_control():
    p,tasks=candidate()
    sim=SceneRuntime(p,"s").simulate(physics_only=True)
    evidence=verify_reactions(p,"s",tasks,sim)
    assert evidence[0]["release_t"] <= evidence[0]["dodge_t"] < evidence[0]["control_hit_t"]
    assert evidence[0]["reaction_hit"] is False


def test_native_throw_that_would_miss_in_depth_is_not_credited():
    p,tasks=candidate(-60)
    sim=SceneRuntime(p,"s").simulate(physics_only=True)
    with pytest.raises(ValueError,match="Stationary control missed"):
        verify_reactions(p,"s",tasks,sim)


def test_uncontrolled_reaction_queue_refused():
    p=world()
    sim=SceneRuntime(p,"s").simulate(physics_only=True)
    with pytest.raises(ValueError,match="isolated defender queue"):
        verify_projectile_reaction(p,"s","rho","kai","plus",sim)
