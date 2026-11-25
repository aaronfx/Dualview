"""Local project-to-preview-to-approved-final pipeline using native APEX.

Every production has an independent directory and immutable input spec.
Technical failure is never released as a final film. Cache reuse is gated by
the project/scene/settings/source fingerprint and prior native QA.
"""
from __future__ import annotations
from pathlib import Path
import json,hashlib,re,subprocess,os
from .production_memory import ProductionMemory,digest
from ..scene.schema import ProjectSpec

def atomic(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(data,indent=2,default=str),encoding="utf-8");os.replace(tmp,path)
def read(path):return json.loads(Path(path).read_text(encoding="utf-8"))
def file_hash(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def engine_hash():
    root=Path(__file__).resolve().parents[1]
    return digest([(str(p.relative_to(root)),file_hash(p)) for p in sorted(root.rglob("*"))
                   if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"])
def safe_project(p):
    p=ProjectSpec.model_validate(p)
    if not 1<=len(p.scenes)<=12 or sum(s.duration for s in p.scenes)>300:
        raise ValueError("Local first-release production limit: 12 scenes / 300 seconds")
    for s in p.scenes:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}",s.id):raise ValueError("Unsafe scene id")
    if p.width%2 or p.height%2:raise ValueError("Video dimensions must be even")
    return p
def scene_fingerprint(p,s,settings,engine):
    # Include full characters and used environment; project-global style/seed
    # and scene order also affect the native renderer.
    return digest({"engine":engine,"settings":settings,"seed":p.seed,"fps":p.fps,
                   "width":p.width,"height":p.height,"index":list(p.scenes).index(s),
                   "scene":s.model_dump(mode="json"),"characters":[c.model_dump(mode="json") for c in p.characters],
                   "environment":p.environment(s.environment).model_dump(mode="json")})

def create_from_brief(brief,directory,*,offline=False,reason=""):
    from .smart_director import plan_story
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if (directory/"project.json").exists():raise ValueError("Production already exists")
    project,trace=plan_story(brief,offline=offline,reason=reason)
    project=safe_project(project)
    raw=project.model_dump(mode="json")
    # New productions default to ink, existing projects remain unchanged.
    for ch in raw["characters"]:
        ch["style"].update(visual_profile="apex_ink",performance_profile="continuous",has_scarf=False)
    project=safe_project(raw)
    from .cinematic_staging import stage_cinematics
    project, staging = stage_cinematics(project)
    atomic(directory/"cinematic_trace.json",staging)
    atomic(directory/"story_trace.json",trace)
    atomic(directory/"project.json",project.model_dump(mode="json"))
    return project

def stage_project(project,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if (directory/"project.json").exists():raise ValueError("Production already exists")
    p=safe_project(project)
    atomic(directory/"project.json",p.model_dump(mode="json"))
    return p

def run_production(directory,*,final=False,progress=None):
    from ..scene.runtime import SceneRuntime
    from ..scene.goals import derive_goals,matches
    from ..scene.solver import stuck_characters
    from ..qa.creative import audit_creative_plan
    from ..render.film import render_film
    from ..qa.director_critic import critique
    from ..qa.video_critic import inspect_video
    from .smart_director import ordered_evidence
    directory=Path(directory);p=safe_project(ProjectSpec.model_validate(read(directory/"project.json")))
    spec_hash=digest(p.model_dump(mode="json"));eng=engine_hash()
    memory=ProductionMemory(directory/"memory.sqlite")
    settings={"final":final,"samples":2 if final else 1,"scale":1.0 if final else min(1.,540/p.height)}
    # Require approval of exactly this preview/spec/engine, never a different revision.
    if final:
        preview=read(directory/"preview_report.json")
        if not preview.get("technical_pass") or preview["project_hash"]!=spec_hash or preview["engine_hash"]!=eng:
            raise ValueError("Generate a fresh passing preview before final render")
        if file_hash(directory/"preview.mp4")!=preview["video_hash"] or not memory.approved(p.id,preview["approval_key"]):
            raise ValueError("Exact preview must be reviewed and approved")
    mode="final" if final else "preview";report_path=directory/(mode+"_report.json")
    report_path.unlink(missing_ok=True)
    say=progress or (lambda *a:None)
    evidence={};critiques={}
    for i,s in enumerate(p.scenes):
        say("rehearsal",i/len(p.scenes),s.id)
        rt=SceneRuntime(p,s.id,strict=False);sim=rt.simulate()
        if s.goals:ordered_evidence(s.goals,sim.events,sim.duration)
        else:
            for g in derive_goals(s):
                if not any(matches(g,e) and e.t<=sim.duration for e in sim.events):raise ValueError(f"Missing derived goal {g}")
        failures=[c.violation for c in sim.controllers.values() if c.violation]+stuck_characters(sim)
        if failures or any(e.type=="action_impossible" for e in sim.events):raise ValueError(f"{s.id}: {failures or 'impossible action'}")
        evidence[s.id]=sim.events
        critiques[s.id]=critique(rt)
        memory.record(p.id,s.id,sim)
    if p.creative_plan:
        fails=[x.name for x in audit_creative_plan(p,evidence) if x.status=="FAIL"]
        if fails:raise ValueError("Creative contract failed: "+", ".join(fails))
    work=directory/(mode+"_scenes");work.mkdir(exist_ok=True)
    cache_path=work/"cache.json";old=read(cache_path) if cache_path.exists() else {};cache={};dirty=[]
    for i,s in enumerate(p.scenes):
        fingerprint=scene_fingerprint(p,s,settings,eng)
        seg=work/f"{i:02d}_{s.id}.mp4";meta=Path(str(seg)+".json")
        qa=Path(str(seg)+".qa.json")
        prior=old.get(s.id,{})
        if (prior.get("fingerprint")==fingerprint and seg.exists() and meta.exists() and qa.exists()
                and prior.get("video_hash")==file_hash(seg) and prior.get("qa_hash")==file_hash(qa)
                and prior.get("meta_hash")==file_hash(meta) and read(qa).get("passed") is True):
            cache[s.id]=prior
        else:
            dirty.append(s.id)
            cache[s.id]={"fingerprint":fingerprint}
    video=directory/(mode+".mp4")
    def checkpoint(i,s,m):
        seg=work/f"{i:02d}_{s.id}.mp4";meta=Path(str(seg)+".json");qa=Path(str(seg)+".qa.json")
        if not m.failed and qa.exists() and read(qa).get("passed") is True:
            cache[s.id].update(video_hash=file_hash(seg),qa_hash=file_hash(qa),meta_hash=file_hash(meta))
            # Carry forward only validated cache entries for untouched scenes.
            atomic(cache_path,{**old,**{k:v for k,v in cache.items() if "video_hash" in v}})
    res=render_film(p,str(video),samples=settings["samples"],preview_scale=settings["scale"],
                    work_dir=str(work),qa=True,only=dirty,progress=say,on_scene=checkpoint)
    bad=[m.scene for m in res.scenes if m.failed or "FAIL" in m.gates.values() or not m.gates]
    bad += [c["name"] for c in res.film_checks if c["status"]=="FAIL"]
    for i,s in enumerate(p.scenes):
        seg=work/f"{i:02d}_{s.id}.mp4";meta=Path(str(seg)+".json");qa=Path(str(seg)+".qa.json")
        if seg.exists() and meta.exists() and qa.exists() and read(qa).get("passed") is True:
            cache[s.id].update(video_hash=file_hash(seg),qa_hash=file_hash(qa),meta_hash=file_hash(meta))
    atomic(cache_path,cache)
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(video),"-f","null","-"],check=True,timeout=300)
    vh=file_hash(video)
    report={"technical_pass":not bad,"failures":bad,"project_hash":spec_hash,"engine_hash":eng,
            "video_hash":vh,"approval_key":digest([spec_hash,eng,vh]),"render":res.to_dict(),
            "telemetry":critiques,"pixel_review":inspect_video(video),"rendered_scenes":dirty,
            "artistic_review":"owner_approved_preview" if final else "pending"}
    atomic(report_path,report)
    if bad:raise RuntimeError("Native QA rejected: "+", ".join(bad))
    return report

def approve_preview(directory,review):
    directory=Path(directory);p=safe_project(read(directory/"project.json"));r=read(directory/"preview_report.json")
    if not r.get("technical_pass") or r["project_hash"]!=digest(p.model_dump(mode="json")) or r["engine_hash"]!=engine_hash():
        raise ValueError("Preview is not a current passing render")
    if file_hash(directory/"preview.mp4")!=r["video_hash"]:raise ValueError("Preview file changed")
    ProductionMemory(directory/"memory.sqlite").approve(p.id,r["approval_key"],review)
    return r["approval_key"]
