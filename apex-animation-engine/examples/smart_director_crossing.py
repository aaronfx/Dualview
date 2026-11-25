"""Offline objective-to-native-preview demonstration (no paid API calls)."""
import argparse
import json
from pathlib import Path
from build_impossible_crossing import world
from apex.scene.schema import ProjectSpec
from apex.ai.smart_director import CrossRequest, cross_and_collect, write_selection, render_selection

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,default=Path("out/smart_director"))
    p.add_argument("--render",action="store_true")
    p.add_argument("--final",action="store_true")
    args=p.parse_args()
    project=ProjectSpec.model_validate(world())
    objective=CrossRequest(scene_id="cross",actor="iko",obstacle_id="barrier",
                           goal_prop_id="spark",movable_prop_id="crate")
    selection=cross_and_collect(project,objective)
    write_selection(selection,args.out)
    print(json.dumps(selection.report(),indent=2,default=str))
    if selection.project is None: return 2
    if args.render: print(render_selection(selection,args.out,final=args.final))
    return 0

if __name__=="__main__": raise SystemExit(main())
