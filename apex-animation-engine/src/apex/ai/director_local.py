"""Local Smart Director entrypoint: python -m apex.ai.director_local."""
import argparse
import json
from pathlib import Path
from .capabilities import catalogue
from .smart_director import CrossRequest, cross_and_collect, rehearse, write_selection, render_selection, plan_story
from ..scene.schema import ProjectSpec

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    c=sub.add_parser("capabilities")
    c.add_argument("--out",type=Path)
    for name in ("cross","rehearse"):
        c=sub.add_parser(name)
        c.add_argument("project",type=Path)
        c.add_argument("request",type=Path)
        c.add_argument("--out",type=Path,required=True)
        c.add_argument("--render",action="store_true")
        c.add_argument("--final",action="store_true")
    c=sub.add_parser("mission",help="Use budgeted AI to select a typed native tool from a brief")
    c.add_argument("project",type=Path)
    c.add_argument("brief",type=Path)
    c.add_argument("--scene",required=True)
    c.add_argument("--reason",required=True)
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--render",action="store_true")
    c.add_argument("--final",action="store_true")
    c=sub.add_parser("produce",help="Local native preview/final production from a brief or saved project")
    c.add_argument("source",type=Path)
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--offline",action="store_true")
    c.add_argument("--reason",default="")
    c.add_argument("--project",action="store_true")
    c=sub.add_parser("resume")
    c.add_argument("--out",type=Path,required=True)
    c=sub.add_parser("approve")
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--review",required=True)
    c=sub.add_parser("revise")
    c.add_argument("scene")
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--revision",type=Path,required=True)
    c=sub.add_parser("vision-review")
    c.add_argument("video",type=Path)
    c.add_argument("--model",required=True)
    c.add_argument("--out",type=Path,required=True)
    c=sub.add_parser("story")
    c.add_argument("brief",type=Path)
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--offline",action="store_true")
    c.add_argument("--reason",default="")
    args=p.parse_args()
    if args.command not in ("capabilities","resume","approve","revise","vision-review") and args.out.exists() and any(args.out.iterdir()):
        p.error("Use a new empty output directory for every production run")
    if args.command=="vision-review":
        from ..qa.local_vision_critic import review_video
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(review_video(args.video,args.model),indent=2),encoding="utf-8")
        return 0
    if args.command=="capabilities":
        data=json.dumps(catalogue(),indent=2)
        if args.out: args.out.write_text(data,encoding="utf-8")
        else: print(data)
        return 0
    if args.command in ("produce","resume","approve","revise"):
        from .local_production import create_from_brief,stage_project,run_production,approve_preview
        def progress(stage,fraction,message):print(f"{stage} {fraction:.0%} {message}",flush=True)
        if args.command=="produce":
            if args.project:stage_project(ProjectSpec.model_validate_json(args.source.read_text(encoding="utf-8")),args.out)
            else:create_from_brief(args.source.read_text(encoding="utf-8"),args.out,offline=args.offline,reason=args.reason)
        if args.command=="revise":
            from .scene_revision import revise_scene
            revise_scene(args.out,args.scene,args.revision)
            args.out=args.revision
        if args.command=="approve":approve_preview(args.out,args.review)
        run_production(args.out,final=args.command=="approve",progress=progress)
        return 0
    if args.command=="mission":
        from .mission import run_mission
        from .providers import provider_from_env
        project=ProjectSpec.model_validate_json(args.project.read_text(encoding="utf-8"))
        provider=provider_from_env(reason=args.reason)
        if provider is None: raise ValueError("Configure an explicitly approved AI provider for mission mode")
        selection, trace=run_mission(project,args.scene,args.brief.read_text(encoding="utf-8"),provider)
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/"mission_trace.json").write_text(json.dumps(trace,indent=2,default=str),encoding="utf-8")
        write_selection(selection,args.out)
        if selection.project is None: print("No mission passed; see mission_trace.json"); return 2
        if args.render: print(render_selection(selection,args.out,final=args.final))
        return 0
    if args.command=="story":
        project, trace=plan_story(args.brief.read_text(encoding="utf-8"),offline=args.offline,reason=args.reason)
        args.out.mkdir(parents=True,exist_ok=True)
        (args.out/"project.json").write_text(project.model_dump_json(indent=2),encoding="utf-8")
        (args.out/"story_trace.json").write_text(json.dumps(trace,indent=2,default=str),encoding="utf-8")
        print("Story plan written; rehearse and review before rendering.")
        return 0
    project=ProjectSpec.model_validate_json(args.project.read_text(encoding="utf-8"))
    request=json.loads(args.request.read_text(encoding="utf-8"))
    if args.command=="cross":
        selection=cross_and_collect(project,CrossRequest.model_validate(request))
    else:
        if set(request)-{"scene_id","candidates","max_trials"}: raise ValueError("Unknown rehearsal request key")
        selection=rehearse(project,request["scene_id"],request["candidates"],max_trials=request.get("max_trials",6))
    write_selection(selection,args.out)
    print(json.dumps(selection.report(),default=str,indent=2))
    if selection.project is None: return 2
    if args.render: print(render_selection(selection,args.out,final=args.final))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
