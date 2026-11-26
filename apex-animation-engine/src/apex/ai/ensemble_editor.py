"""Native outcome-driven editorial timing for live ensembles."""
from copy import deepcopy
from math import ceil
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime

def finish_ensemble(raw,scene_id,tail=.35):
    if not .1<=tail<=.65:
        raise ValueError("invalid final hold")
    raw=deepcopy(raw)
    p=ProjectSpec.model_validate(raw)
    sim=SceneRuntime(p,scene_id).simulate(physics_only=True)
    sc=next(s for s in raw["scenes"] if s["id"]==scene_id)
    actors={a["character"] for a in sc["ensemble"]["actors"]}
    witnesses={e.character for e in sim.events if e.type=="ensemble_objective"}
    end=next((e.t for e in sim.events if e.type=="ensemble_completed"),None)
    if end is None or witnesses!=actors:
        missing=sorted(actors-witnesses)
        final={cid:{"x":c.s,"mode":c.mode,"current":c.cur.type if c.cur else None,"goal":c.autonomous_brain.goal,"done":c.autonomous_brain.done} for cid,c in sim.controllers.items()}
        raise ValueError(f"cannot edit away unfinished ensemble objectives; missing={missing}; final={final}")
    if len(sc["shots"])!=1:
        raise ValueError("automatic trim currently requires a single shot")
    duration=min(sc["duration"],ceil((end+tail)*p.fps)/p.fps)
    sc["duration"]=duration
    sc["shots"][0]["end"]=duration
    check=SceneRuntime(ProjectSpec.model_validate(raw),scene_id).simulate(physics_only=True)
    if {e.character for e in check.events if e.type=="ensemble_objective"}!=actors or not any(e.type=="ensemble_completed" for e in check.events):
        raise ValueError("edited scene lost native outcome evidence")
    return raw

def event_camera_candidates(raw,scene_id,sim):
    """Generate editorial coverage from native events without authoring motion."""
    from math import floor
    sc=next(s for s in raw["scenes"] if s["id"]==scene_id)
    events=[e for e in sim.events if e.character in sim.controllers and e.type in ("hit","hand_grab","pick_up","stood_up","act")]
    if not events or sc["duration"]<2:
        return []
    # Avoid competing cuts in the same short beat; prefer resolved contact.
    weights={"hand_grab":5,"hit":4,"stood_up":3,"pick_up":3,"act":1}
    selected=[]
    for e in sorted(events,key=lambda e:(-weights[e.type],e.t,str(e.character))):
        if all(abs(e.t-other.t)>=1.6 for other in selected):
            selected.append(e)
        if len(selected)>=4:
            break
    result=deepcopy(raw)
    scene=next(s for s in result["scenes"] if s["id"]==scene_id)
    duration=scene["duration"]
    # Keep an establishing frame before the first action. Each cut has a
    # minimum duration of .5 s; shots cover every frame with no gaps.
    cuts=[(0,None)]
    for ev in sorted(selected,key=lambda e:e.t):
        start=floor(max(.5,ev.t-.45)*raw["fps"])/raw["fps"]
        if start-cuts[-1][0]>=.5 and duration-start>=.75:
            cuts.append((start,ev))
    if len(cuts)<2:
        return []
    shots=[]
    wide=deepcopy(sc["shots"][0]["camera"])
    for i,(start,ev) in enumerate(cuts):
        end=cuts[i+1][0] if i+1<len(cuts) else duration
        if ev is None:
            camera=wide
            kind="establishing"
        else:
            cid=ev.character
            other=ev.data.get("target") or ev.data.get("with") or ev.data.get("helper")
            include=[]
            if isinstance(other,str):
                other=other.removeprefix("char:")
            if other in sim.controllers and other!=cid:
                # Include a partner only if that partner remains within a
                # readable distance throughout the cut, not merely at impact.
                a,b=sim.controllers[cid],sim.controllers[other]
                a_rec=[v for v in a.records if start<=v.t<=end]
                b_rec=[v for v in b.records if start<=v.t<=end]
                if a_rec and b_rec and max(abs(x.pos[0]-y.pos[0]) for x,y in zip(a_rec,b_rec))<550:
                    include=["char:"+other]
            camera={"mode":"follow","target":cid,"include":include,"keep_in_frame":True,
                    "view_height":620 if include else 520,"lead":.12}
            kind="tracking"
        shots.append({"id":"ensemble_cut_"+str(i),"start":start,"end":end,"kind":kind,"camera":camera})
    scene["shots"]=shots
    return [result]

def rehearse_ensemble(raw,scene_id,directory):
    """Compare static and event-directed coverage using unchanged native QA."""
    import json
    from pathlib import Path
    from ..qa.inspector import Inspector
    from ..render.pipeline import build_camera
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    base=finish_ensemble(raw,scene_id)
    base_p=ProjectSpec.model_validate(base)
    sim=SceneRuntime(base_p,scene_id).simulate(physics_only=True)
    accepted=[]
    reports=[]
    for i,candidate in enumerate([base,*event_camera_candidates(base,scene_id,sim)]):
        row={"candidate":i,"accepted":False}
        try:
            p=ProjectSpec.model_validate(candidate)
            rt=SceneRuntime(p,scene_id)
            result=rt.simulate()
            if not any(e.type=="ensemble_completed" for e in result.events):
                raise ValueError("native scene did not complete")
            qa=Inspector(rt,build_camera(rt,p.width/p.height),p.fps,(p.width,p.height)).run(check_determinism=False)
            row["checks"]=[{"name":c.name,"status":c.status,"metric":c.metric,"details":c.details} for c in qa.checks]
            if not qa.passed:
                raise ValueError("native Inspector rejected camera or performance")
            row["accepted"]=True
            warnings=sum(c.status=="WARN" for c in qa.checks)
            size=next((c.metric for c in qa.checks if c.name=="composition_subject_size"),0) or 0
            accepted.append((warnings,-size,-len(p.scene(scene_id).shots),i,candidate))
        except (ValueError,RuntimeError,KeyError,TypeError,ArithmeticError) as exc:
            row["reason"]=str(exc)
        reports.append(row)
        (directory/"ensemble_rehearsal.json").write_text(json.dumps(reports,indent=2,default=str),encoding="utf-8")
    if not accepted:
        raise ValueError("No ensemble rehearsal passed native QA; inspect ensemble_rehearsal.json")
    winner=min(accepted,key=lambda q:q[:4])
    (directory/"ensemble_selection.json").write_text(json.dumps({"candidate":winner[3],"warnings":winner[0],"shot_count":-winner[2],"artistic_review":"pending"},indent=2),encoding="utf-8")
    return winner[4]
