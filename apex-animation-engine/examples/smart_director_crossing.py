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
    p.add_argument("--legacy",action="store_true",help="Preserve original character and environment appearance")
    args=p.parse_args()
    raw=world()
    if not args.legacy:
        for ch in raw["characters"]:
            ch["style"].update(visual_profile="apex_ink",performance_profile="continuous",has_scarf=False)
        env=raw["environments"][0]
        env["room"].update(style="open",entry_door=False)
        env["backdrop"]={"kind":"tower","art_profile":"industrial_depth","seed":92,"weather":"motes","weather_amount":0.3}
    project=ProjectSpec.model_validate(raw)
    objective=CrossRequest(scene_id="cross",actor="iko",obstacle_id="barrier",
                           goal_prop_id="spark",movable_prop_id="crate")
    selection=cross_and_collect(project,objective)
    write_selection(selection,args.out)
    print(json.dumps(selection.report(),indent=2,default=str))
    if selection.project is None: return 2
    if args.render: print(render_selection(selection,args.out,final=args.final))
    return 0

if __name__=="__main__": raise SystemExit(main())
