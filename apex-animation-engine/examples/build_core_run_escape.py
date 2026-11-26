"""CORE RUN: The Escape — a directed integration cut using existing native skills.

No new engine capabilities. The five original CORE RUN scenes retain their
action tracks, and the portal rescue from THE LAST RETRY is inserted before
Dawn. A warp is an editorial transition, not a continuous-state claim.
"""
from copy import deepcopy
from pathlib import Path
import json,sys,time,subprocess

HERE=Path(__file__).resolve().parent
ORDER=("city","tower","canyon","arena","escape","summit")
SCALE=2/3
TARGET=180.0
REQUIRED={
    "city":("break@case","vault@iko","hurt@iko","hand_offered@pell","exit_reached@iko"),
    "tower":("climbed@iko","knockdown@iko","hand_offered@pell","point@pell","exit_reached@iko","exit_reached@pell"),
    "canyon":("collapse@bridge","orb_jump@iko","throw_start@pell","creature_break@drone","exit_reached@pell"),
    "arena":("knockdown@iko","disarm@vex","stood_up@iko","knockdown@vex","pick_up@iko[prop=core]","exit_reached@iko"),
    "escape":("portal_exit@iko","orb_jump@iko","ledge_catch@iko","pulled_up@iko","exit_together","exit_reached@iko","exit_reached@pell"),
    "summit":("place@iko","gesture_start@iko","fist_bump@iko"),
}
def build():
    core=json.loads((HERE/"core_run.json").read_text(encoding="utf-8"))
    retry=json.loads((HERE/"last_retry.json").read_text(encoding="utf-8"))
    for c in retry["characters"]:
        assert c==next(k for k in core["characters"] if k["id"]==c["id"])
    raw=deepcopy(core)
    raw.update(id="core_run_escape",title="CORE RUN: THE ESCAPE")
    rescue=deepcopy(next(s for s in retry["scenes"] if s["id"]=="last"))
    environment=deepcopy(next(e for e in retry["environments"] if e["id"]==rescue["environment"]))
    environment["id"]="escape_checkpoint"
    raw["environments"].append(environment)
    rescue.update(id="escape",title="The broken gateway",environment=environment["id"],transition_in="warp")
    rescue.pop("retry_of",None)
    rescue["hud"].pop("retries",None)
    rescue["hud"]["messages"][0]["text"]="GATEWAY OFFLINE"
    # Preserve the proven stunt and emotional beats. Only cut the nonessential
    # final vista in Dawn; the fist bump and restoration remain before the cut.
    raw["scenes"].insert(-1,rescue)
    ending=raw["scenes"][-1]
    ending["duration"]=round(TARGET-sum(s["duration"] for s in raw["scenes"][:-1]),2)
    assert ending["duration"]>ending["shots"][-1]["start"]+1
    ending["shots"][-1]["end"]=ending["duration"]
    ending["hud"]["messages"]=[{"text":"CORE RUN: THE ESCAPE","at":12.25,"duration":2.5,"style":"title"}]
    assert tuple(s["id"] for s in raw["scenes"])==ORDER
    assert abs(sum(s["duration"] for s in raw["scenes"])-TARGET)<.001
    return raw

def project():
    from apex.scene.schema import ProjectSpec
    return ProjectSpec.model_validate(build())

def render_part(out,scene_id):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.goals import matches
    from apex.render.pipeline import render_scene
    from apex.render.film import SceneMetrics,_rss_mb
    p=project()
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    path=out/f"{ORDER.index(scene_id):02d}_{scene_id}.mp4"
    sim=SceneRuntime(p,scene_id).simulate(physics_only=True)
    evidence={"scene":scene_id,"missing":[g for g in REQUIRED[scene_id] if not any(matches(g,e) for e in sim.events)],
              "violations":[str(c.violation) for c in sim.controllers.values() if c.violation],
              "impossible":[str(e.data) for e in sim.events if e.type=="action_impossible"]}
    evidence["passed"]=not any(evidence[k] for k in ("missing","violations","impossible"))
    Path(str(path)+".story.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(evidence),flush=True)
    start=time.monotonic()
    def progress(stage,fraction,msg):
        if fraction==1 or stage=="simulate":print(stage,round(fraction,2),msg,flush=True)
    res=render_scene(p,scene_id,str(path),samples=1,qa=True,preview_scale=SCALE,qa_path=str(path)+".qa.json",progress=progress)
    dt=time.monotonic()-start
    report=res.qa
    meta=SceneMetrics(scene_id,res.frames,round(dt,1),round(res.frames/dt,2),report.gates(),len(report.checks),sorted(c.name for c in report.checks if c.status=="FAIL"),round(_rss_mb(),1))
    Path(str(path)+".json").write_text(json.dumps(vars(meta),indent=2),encoding="utf-8")
    subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(path),"-f","null","-"],check=True)
    print(vars(meta),flush=True)

def assemble(parts,out):
    from apex.render.film import render_film
    from apex.render.video import probe
    p=project()
    parts=Path(parts);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    evidence=[]
    for i,sid in enumerate(ORDER):
        f=parts/f"{i:02d}_{sid}.mp4"
        for suffix in ("",".json",".qa.json",".story.json"):
            if not Path(str(f)+suffix).is_file():raise FileNotFoundError(str(f)+suffix)
        evidence.append(json.loads(Path(str(f)+".story.json").read_text()))
    native=out/"core_run_escape_native.mp4"
    film=render_film(p,str(native),samples=1,preview_scale=SCALE,work_dir=str(parts),only=[])
    report=film.to_dict()
    report["story"]=evidence
    report["native_accepted"]=all(e["passed"] for e in evidence) and not any(s.failed for s in film.scenes) and not any(c["status"]=="FAIL" for c in film.film_checks)
    report["editorial_note"]="Reused directed native performances; no claim of fully autonomous choreography or continuous state across warp cuts."
    # Existing time effects add to the scene-clock duration. Conform the
    # complete render uniformly to the requested runtime, no loops or padding.
    duration=float(probe(str(native))["format"]["duration"])
    factor=duration/TARGET
    report["duration_before_conform"]=duration
    report["speed_factor"]=factor
    report["final_accepted"]=False
    path=out/"CORE_RUN_The_Escape_3min.mp4"
    if .9<=factor<=1.18:
        subprocess.run(["ffmpeg","-y","-loglevel","error","-i",str(native),"-vf",f"setpts=PTS/{factor:.9f},fps=24","-af",f"atempo={factor:.9f},aresample=48000","-t","180","-c:v","libx264","-crf","18","-preset","fast","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-movflags","+faststart",str(path)],check=True)
        subprocess.run(["ffmpeg","-v","error","-xerror","-i",str(path),"-f","null","-"],check=True)
        report["final_duration"]=float(probe(str(path))["format"]["duration"])
        report["final_accepted"]=report["native_accepted"] and abs(report["final_duration"]-180)<.1
    (out/"film_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    (out/"project.json").write_text(json.dumps(build(),indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    if not report["final_accepted"]:
        raise SystemExit("Integration cut is a rehearsal draft: inspect report, do not publish as accepted.")

if __name__=="__main__":
    if sys.argv[1]=="build":
        f=Path(sys.argv[2]);f.parent.mkdir(parents=True,exist_ok=True)
        f.write_text(json.dumps(build(),indent=2),encoding="utf-8")
        project()
    elif sys.argv[1]=="part":render_part(sys.argv[2],sys.argv[3])
    elif sys.argv[1]=="assemble":assemble(sys.argv[2],sys.argv[3])
    else:raise ValueError(sys.argv[1])
