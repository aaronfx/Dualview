"""M2 controlled projectile evasion, using only the native physics runtime.

A deliberately narrow contract: one throw at an otherwise stationary defender,
one release-triggered dodge, a complete flight observation, and an unchanged
scene with the reaction removed. No alternative physics or synthetic events.
"""
from __future__ import annotations
import math
from ..scene.schema import ProjectSpec
from ..scene.goals import matches


def verify_projectile_reaction(project, scene_id, defender, thrower, prop, sim):
    from ..scene.runtime import SceneRuntime
    p = ProjectSpec.model_validate(project)
    sc = p.scene(scene_id)
    release_goal = f"throw@{thrower}[prop={prop},target=char:{defender}]"
    hit_goal = f"prop_hit@{prop}[prop={prop},target={defender}]"
    dodge_goal = f"dodge@{defender}"
    actor_actions = [a for a in sc.actions if a.character == defender]
    if (len(actor_actions) != 2 or actor_actions[0].type != "wait_for" or
            actor_actions[0].until != "event:" + release_goal or
            actor_actions[0].lane is not None or actor_actions[1].type != "dodge"):
        raise ValueError("Projectile control requires a release-triggered isolated defender queue")
    def event_list(result, goal):
        return [e for e in result.events if 0 <= e.t <= result.duration and matches(goal,e)]
    def release(result):
        # Reject multiple releases of this object: they make attribution ambiguous.
        all_releases = event_list(result, f"throw@{thrower}[prop={prop}]")
        exact = event_list(result, release_goal)
        if len(all_releases) != 1 or len(exact) != 1:
            raise ValueError("Projectile control requires exactly one specified release")
        ev = exact[0]
        if not any(e.t <= ev.t for e in event_list(result,f"pick_up@{thrower}[prop={prop}]")):
            raise ValueError("Projectile release lacks native pickup evidence")
        if result.duration + 1e-6 < ev.t + 3.0:
            raise ValueError("Projectile control needs complete three-second flight observation")
        return ev
    if any(c.violation for c in sim.controllers.values()):
        raise ValueError("Projectile reaction has controller violations")
    actual = release(sim)
    dodges = event_list(sim,dodge_goal)
    if len(dodges) != 1 or dodges[0].t + 1e-9 < actual.t:
        raise ValueError("No unique post-release dodge")
    if any(e.t >= actual.t for e in event_list(sim,hit_goal)):
        raise ValueError("Projectile contacted defender despite dodge")
    raw = p.model_dump(mode="json")
    scene = next(s for s in raw["scenes"] if s["id"] == scene_id)
    scene["actions"] = [a for a in scene["actions"] if a["character"] != defender]
    scene["actions"].append({"character":defender,"type":"idle","duration":sc.duration})
    stationary = SceneRuntime(ProjectSpec.model_validate(raw),scene_id,strict=False).simulate(physics_only=True)
    if any(c.violation for c in stationary.controllers.values()):
        raise ValueError("Stationary control has controller violations")
    control = release(stationary)
    if (abs(control.t-actual.t)>1e-6 or
            math.dist(control.data["point"],actual.data["point"])>1e-3 or
            abs(control.data["speed"]-actual.data["speed"])>1e-3):
        raise ValueError("Stationary control changed projectile release")
    hits = [e for e in event_list(stationary,hit_goal) if e.t >= control.t]
    if not hits:
        raise ValueError("Stationary control missed: no demonstrated threat")
    if dodges[0].t >= hits[0].t:
        raise ValueError("Dodge started after stationary impact")
    return {"defender":defender,"thrower":thrower,"prop":prop,
            "release_t":float(actual.t),"dodge_t":float(dodges[0].t),
            "control_hit_t":float(hits[0].t),"reaction_hit":False,
            "scope":"one native throw, stationary control, matched release and full flight"}
