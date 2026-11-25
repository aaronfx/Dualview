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
    c=sub.add_parser("story")
    c.add_argument("brief",type=Path)
    c.add_argument("--out",type=Path,required=True)
    c.add_argument("--offline",action="store_true")
    c.add_argument("--reason",default="")
    args=p.parse_args()
    if args.command=="capabilities":
        data=json.dumps(catalogue(),indent=2)
        if args.out: args.out.write_text(data,encoding="utf-8")
        else: print(data)
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
