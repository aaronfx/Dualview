"""Story-to-ensemble compilation via the existing budgeted provider.

The output changes only ensemble objectives, never environment, rig, placement
or native actions. No external AI call is performed during simulation.
"""
from copy import deepcopy
import json
from ..scene.schema import EnsembleSpec,ProjectSpec

def compile_ensemble_brief(project,scene_id,storyline,briefs,provider):
    if provider is None:
        raise ValueError("configured provider required; no silent offline fallback")
    raw=deepcopy(project.model_dump(mode="json") if hasattr(project,"model_dump") else project)
    scene=next(s for s in raw["scenes"] if s["id"]==scene_id)
    placed={p["character"] for p in scene["placements"]}
    if set(briefs)!=placed or not storyline.strip() or scene["actions"]:
        raise ValueError("every placed actor requires a brief and no authored actions")
    status="failed"
    try:
        instruction="Return JSON matching EnsembleSpec. Select only supported objectives. Preserve each actor ID and exact prompt. Do not invent characters or change their geometry. Schema: "+json.dumps(EnsembleSpec.model_json_schema())
        payload={"storyline":storyline,"briefs":briefs,"placements":scene["placements"],"room":next(e["room"] for e in raw["environments"] if e["id"]==scene["environment"])}
        result=EnsembleSpec.model_validate_json(provider.complete(instruction,json.dumps(payload),max_tokens=4500))
        if {a.character:a.prompt for a in result.actors}!=briefs:
            raise ValueError("compiled cast or briefs differ from the original")
        scene["storyline"]=storyline
        scene["ensemble"]=result.model_dump(mode="json")
        checked=ProjectSpec.model_validate(raw)
        status="accepted"
        return checked
    finally:
        if getattr(provider,"experiment",None) is not None:
            provider.experiment.finish(status,"ensemble brief compilation")

def compile_from_env(project,scene_id,storyline,briefs):
    from .providers import provider_from_env
    return compile_ensemble_brief(project,scene_id,storyline,briefs,provider_from_env(reason="compile ensemble story"))
