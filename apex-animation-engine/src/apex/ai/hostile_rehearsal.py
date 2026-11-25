"""Rehearse an ensemble with native outcome witnesses and unchanged QA thresholds."""
import json
from copy import deepcopy
from pathlib import Path
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime
from ..qa.hostile_liveness import audit_hostile_liveness

def evidence(sim,placements):
    reports=audit_hostile_liveness(sim,placements)
    roles={p["character"]:p["actor_role"] for p in placements if p.get("actor_role")}
    ev=[e for e in sim.events if e.character in roles]
    hunter=next(k for k,v in roles.items() if v["role"]=="hunter")
    fugitive=next(k for k,v in roles.items() if v["role"]=="fugitive")
    strikes=[e for e in ev if e.type=="strike_start"]
    attacks={cid:sum(e.character==cid for e in strikes) for cid in roles}
    resolved=[e for e in ev if e.type in ("hit","whiff","blocked")]
    hits=sum(e.type=="hit" for e in resolved)
    exchanges=[e.t for e in strikes]
    escape=any(e.type=="autonomous_reached" and e.character==fugitive for e in ev)
    passed=all(r["passed"] for r in reports.values()) and escape and attacks[hunter]>=2 and attacks[fugitive]>=1 and hits>=1
    return {"passed":passed,"actors":reports,"attacks":attacks,"hit_count":hits,"attack_times":exchanges,"escape":escape,
        "events":[{"t":e.t,"type":e.type,"actor":e.character,"data":e.data} for e in ev if e.type in ("strike_start","hit","whiff","blocked","dodge","autonomous_blocked","autonomous_replan","actor_action_outcome","actor_intent","autonomous_reached")]}

def rehearse_hostile(raw,scene_id,directory):
    from .action_pacing import fit_goal_scene
    from ..qa.inspector import Inspector
    from ..render.pipeline import build_camera
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    trials=[]
    accepted=[]
    # Bounded start-spacing alternatives, unchanged industrial geometry.
    for gap in (90,110,125,75):
        candidate=deepcopy(raw)
        scene=next(s for s in candidate["scenes"] if s["id"]==scene_id)
        fugitive=next(p for p in scene["placements"] if p["actor_role"]["role"]=="fugitive")
        hunter=next(p for p in scene["placements"] if p["actor_role"]["role"]=="hunter")
        hunter["x"]=fugitive["x"]-gap
        entry={"initial_gap":gap}
        try:
            candidate=fit_goal_scene(candidate,scene_id,fugitive["character"])
            project=ProjectSpec.model_validate(candidate)
            rt=SceneRuntime(project,scene_id)
            sim=rt.simulate()
            report=evidence(sim,scene["placements"])
            entry["evidence"]=report
            if not report["passed"]:
                raise ValueError("missing reciprocal combat or liveness evidence")
            qa=Inspector(rt,build_camera(rt,project.width/project.height),project.fps,(project.width,project.height)).run(check_determinism=False)
            entry["checks"]=[{"name":c.name,"status":c.status,"metric":c.metric,"details":c.details} for c in qa.checks]
            if not qa.passed:
                raise ValueError("native geometry or motion QA rejected")
            overlap=next((c.metric for c in qa.checks if c.name=="screen_separation"),0) or 0
            entry["accepted"]=True
            accepted.append((overlap,-sum(report["attacks"].values()),gap,candidate))
        except (ValueError,RuntimeError,KeyError,TypeError,ArithmeticError) as exc:
            entry.update(accepted=False,reason=str(exc))
        trials.append(entry)
        (directory/"rehearsal.json").write_text(json.dumps(trials,indent=2,default=str),encoding="utf-8")
    if not accepted:
        raise ValueError("no verified hostile rehearsal; see rehearsal.json")
    winner=min(accepted,key=lambda q:q[:3])
    (directory/"selection.json").write_text(json.dumps({"gap":winner[2],"screen_overlap":winner[0],"artistic_review":"pending"},indent=2),encoding="utf-8")
    return winner[3]
