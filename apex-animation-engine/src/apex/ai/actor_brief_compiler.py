"""Compile natural-language actor briefs with the existing budgeted provider.
The provider cannot author actions or change geometry, coordinates, or goals.
"""
import json
from copy import deepcopy
from ..scene.schema import ActorRole,ProjectSpec

def compile_actor_briefs(project,scene_id,storyline,prompts,provider):
    if provider is None:
        raise ValueError("explicit configured provider required; no silent mock")
    raw=deepcopy(project.model_dump(mode="json") if hasattr(project,"model_dump") else project)
    scene=next(s for s in raw["scenes"] if s["id"]==scene_id)
    placements={p["character"]:p for p in scene["placements"]}
    if set(prompts)!=set(placements) or len(placements)!=2:
        raise ValueError("two reciprocal actor briefs required")
    system="Translate story and actor briefs to typed JSON roles. Return only a JSON object mapping each character ID to role data. No actions, positions, scripts or extra keys. ActorRole schema: "+json.dumps(ActorRole.model_json_schema())
    status="failed"
    try:
        reply=provider.complete(system,json.dumps({"storyline":storyline,"prompts":prompts}),max_tokens=1500)
        roles=json.loads(reply)
        if set(roles)!=set(placements):
            raise ValueError("role identifiers differ from scene cast")
        for cid,data in roles.items():
            role=ActorRole.model_validate(data)
            other=next(k for k in placements if k!=cid)
            if role.opponent!=other or role.prompt.strip()!=prompts[cid].strip():
                raise ValueError("actor brief or reciprocal opponent changed")
            p=placements[cid]
            if role.role=="hunter":
                if role.objective!="capture" or p.get("pursue")!=other or p.get("destination_x") is not None:
                    raise ValueError("hunter contradicts scene objective")
                p["hostile_pursuit"]=True
            elif role.objective!="escape" or p.get("destination_x") is None:
                raise ValueError("fugitive contradicts scene objective")
            p["actor_role"]=role.model_dump()
        if {p["actor_role"]["role"] for p in placements.values()}!={"hunter","fugitive"}:
            raise ValueError("roles must oppose each other")
        scene["storyline"]=storyline
        result=ProjectSpec.model_validate(raw)
        status="accepted"
        return result
    finally:
        if getattr(provider,"experiment",None) is not None:
            provider.experiment.finish(status,"actor brief compilation")

def compile_from_env(project,scene_id,storyline,prompts):
    from .providers import provider_from_env
    return compile_actor_briefs(project,scene_id,storyline,prompts,provider_from_env(reason="compile hostile actor briefs"))
