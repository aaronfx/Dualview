"""Goal-only mixed obstacle course. No authored traversal actions."""
import json,sys,runpy
from pathlib import Path

def build():
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-850,-500,1050,[])
    raw["id"]="autonomous_mixed"
    raw["title"]="One objective, independent decisions"
    env=raw["environments"][0]
    env["room"].update(width=3000,road_view=True)
    env["obstacles"][0]["size"][0]=3000
    env["props"]=[{"id":"heavy","kind":"crate","position":[150,30],"size":[70,60],"mass":200,"depth":160}]
    scene=raw["scenes"][0]
    scene["placements"][0]["destination_x"]=1050
    scene["actions"]=[]
    scene["goals"]=["autonomous_reached@iko"]
    scene["duration"]=12
    scene["shots"][0].update(end=12,camera={"mode":"track_x","target":"iko","view_height":620,"center":[0,200]})
    return raw

if __name__=="__main__":
    Path(sys.argv[1]).write_text(json.dumps(build()),encoding="utf-8")
