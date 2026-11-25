"""Isolated native acrobatics tests; goal only, no action list."""
import json,sys,runpy
from pathlib import Path

def build(kind):
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-450,800,650,[])
    scene=raw["scenes"][0]
    scene["placements"]=scene["placements"][:1]
    scene["placements"][0]["destination_x"]=650
    scene["actions"]=[]
    scene["duration"]=10
    scene["shots"][0].update(end=10,camera={"mode":"track_x","target":"iko","center":[0,200],"view_height":620})
    scene["goals"]=["autonomous_reached@iko"]
    raw["id"]="autonomous_"+kind
    env=raw["environments"][0]
    geom={"slide":([0,140],[150,50]),"vault":([0,25],[65,50]),"climb":([0,125],[180,250])}
    center,size=geom[kind]
    env["obstacles"].append({"id":"challenge","kind":"beam" if kind=="slide" else "platform","style":"girder","color":"#8197a8","center":center,"size":size})
    return raw

if __name__=="__main__":
    Path(sys.argv[2]).write_text(json.dumps(build(sys.argv[1])),encoding="utf-8")
