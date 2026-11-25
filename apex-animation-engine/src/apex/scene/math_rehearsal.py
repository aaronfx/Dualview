"""Native signed-term rehearsal. No change to equations, goals or physics."""
from copy import deepcopy

def variants(raw):
    yield "original",deepcopy(raw)
    sc=raw["scenes"][0];env=raw["environments"][0];spec=sc["math_transfer"]
    actor=spec["actor"];name=spec.get("name","transpose")
    combined=next(p for p in env["props"] if p["id"]==name+"_evaluation")
    x=combined["position"][0];w=combined["size"][0];room=env["room"]["width"]/2
    for extra in (110.,160.,230.):
        for side in (1,-1):
            dest=x+side*(w/2+extra)
            if abs(dest)>room-90:continue
            for point_duration in (.25,.5):
                p=deepcopy(raw);s=p["scenes"][0];acts=s["actions"]
                i=next(i for i,a in enumerate(acts) if a["character"]==actor and a["type"]=="point" and a.get("target")=="prop:"+name+"_term")
                acts[i]["duration"]=point_duration
                acts.insert(i+1,dict(character=actor,type="run_to",target_x=dest,speed=390.))
                if i+2<len(acts) and acts[i+2]["type"]=="idle":acts[i+2]["duration"]=.2
                for shot in s["shots"]:
                    cam=shot["camera"];cam["view_height"]=max(cam["view_height"],(abs(dest-cam.get("center",[0,0])[0])+100)*2/(p["width"]/p["height"]))
                yield f"clear_rhs_{side}_{int(extra)}_{point_duration}",p

def verify(raw):
    from .schema import ProjectSpec
    from .runtime import SceneRuntime
    from .math_transposition import plan_additive_transposition
    p=ProjectSpec.model_validate(raw);sc=p.scenes[0];spec=sc.math_transfer;name=spec.name;actor=spec.actor
    plan=plan_additive_transposition(spec.equation)
    rt=SceneRuntime(p,sc.id,strict=False);sim=rt.simulate();events=sim.events
    def event(kind,who,prop=None):
        return next((e for e in events if e.type==kind and e.character==who and (prop is None or e.data.get("prop")==prop)),None)
    term=name+"_term";rhs=name+"_rhs";combined=name+"_evaluation"
    picked=event("pick_up",actor,term);crossed=event("math_crossed",actor,term)
    placed=event("math_transferred",actor,term);evaluated=event("math_evaluate",actor,combined)
    morph=event("morph",combined,combined)
    blockers=[dict(t=e.t,data=e.data) for e in events if e.type=="morph_blocked"]
    def require(ok,reason):
        if not ok:raise ValueError(f"{reason}; morph_blocked={blockers!r}")
    require(all(e is not None for e in (picked,crossed,placed,evaluated,morph)),"Missing native transfer/final morph")
    require(picked.t<crossed.t<placed.t<evaluated.t<morph.t,"Events out of order")
    require(evaluated.t-placed.t>=spec.min_hold-1e-6,"Intermediate dwell missing")
    require(not any(e.type=="throw" for e in events),"Signed term thrown away")
    require(not any(c.violation for c in sim.controllers.values()),"Native controller violation")
    def frame(t):return {v.id:v for v in rt.evaluate(t).props}
    before=frame(0);mid=frame((placed.t+evaluated.t)/2);after=frame(min(sc.duration-.5,13.5))
    require(before[term].glyph==plan.source.text,"Incorrect initial signed term")
    require(term in mid and rhs in mid and combined not in mid,"Intermediate operands missing")
    require(mid[term].glyph==plan.destination.text and mid[rhs].glyph==str(plan.rhs_before),"Wrong intermediate equation")
    require(mid[term].pos[0]>mid[rhs].pos[0],"Term on wrong side")
    require(set(after)=={name+"_variable",name+"_equals",combined},"Wrong final objects")
    require(after[combined].glyph.startswith("@") and after[combined].glyph.split(":")[-1]==str(plan.result),"Final native expression not evaluated")
    require(plan.transfer_proof.valid and plan.evaluation_proof.valid,"Invalid mathematical proof")
    return dict(events={e.type:e.t for e in (picked,crossed,placed,evaluated,morph)},intermediate=plan.expression_text,result=plan.result,blockers=blockers)

def rehearse(raw):
    failures=[]
    for name,p in variants(raw):
        try:return p,dict(selected=name,proof=verify(p),rejected=failures)
        except (ValueError,RuntimeError,AssertionError,KeyError,IndexError) as e:failures.append(dict(candidate=name,reason=str(e)))
    raise ValueError("No native equation staging passed; diagnose blocker: "+repr(failures))
