"""Expanded goal-only course: two actors, two narrow crates and a full-width heavy crate."""
import json,sys,runpy
from pathlib import Path

def build():
    raw=runpy.run_path("examples/build_autonomous_mixed.py")["build"]()
    raw["id"]="autonomous_extended"
    raw["title"]="Independent obstacle course"
    env=raw["environments"][0]
    env["room"]["width"]=5200
    env["obstacles"][0]["size"][0]=5200
    raw["characters"].append({**raw["characters"][1],"id":"ren","name":"REN","style":{**raw["characters"][1]["style"],"body_color":"#ef826b","glow_color":"#ef826b"}})
    scene=raw["scenes"][0]
    scene["placements"][0].update(x=-2200,destination_x=2250)
    scene["placements"][1]["x"]=-1800
    scene["placements"].append({"character":"ren","x":-600,"facing":-1,"z":0})
    env["props"]=[
        {"id":"narrow_a","kind":"crate","position":[-1200,35],"size":[70,70],"mass":40,"depth":35,"color":"#ac8056"},
        {"id":"narrow_b","kind":"crate","position":[50,35],"size":[70,70],"mass":40,"depth":35,"color":"#ac8056"},
        {"id":"heavy","kind":"crate","position":[850,30],"size":[70,60],"mass":200,"depth":160}
    ]
    scene["duration"]=22
    scene["shots"][0]["end"]=22
    return raw

if __name__=="__main__":
    Path(sys.argv[1]).write_text(json.dumps(build()),encoding="utf-8")
