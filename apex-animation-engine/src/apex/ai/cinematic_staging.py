"""Conservative event-driven art and score direction on native scene plans."""
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime

def stage_cinematics(project):
    p=ProjectSpec.model_validate(project);raw=p.model_dump(mode="json");trace=[]
    # Only add a profile to supported open industrial worlds, not arbitrary rooms.
    for env in raw["environments"]:
        bd=env.get("backdrop")
        if bd and bd["kind"]=="tower" and env["room"]["style"]=="open":
            bd["art_profile"]="industrial_depth"
    for s in raw["scenes"]:
        if s.get("score") is not None:continue
        scene=p.scene(s["id"]);sim=SceneRuntime(p,scene.id,strict=False).simulate(physics_only=True)
        hazard=next((e for e in sim.events if e.type in ("pinned","knockdown","collapse","rope_snap","hit")),None)
        resolve=next((e for e in sim.events if e.type in ("freed","pulled_up","exit_together","exit_reached","math_evaluate") and
                      (hazard is None or e.t>=hazard.t)),None)
        cues=[{"mood":"calm","at":0}]
        if hazard:cues.append({"mood":"tension","at":float(hazard.t)})
        if resolve:cues.append({"mood":"triumph","at":float(resolve.t)})
        s["score"]={"key":"D","level":.42,"cues":cues}
        trace.append({"scene":s["id"],"source":"native events","score":cues})
    return ProjectSpec.model_validate(raw),trace
