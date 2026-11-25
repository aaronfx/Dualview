"""Two independent objectives, one continuous action environment."""
import json,sys,runpy
from pathlib import Path

def build(paced=False):
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-1650,-2100,1900,[])
    raw["id"]="autonomous_chase"
    raw["title"]="The pursuit"
    env=raw["environments"][0]
    env["room"].update(width=5200,road_view=True)
    env["obstacles"][0]["size"][0]=5200
    for oid,kind,center,size in [
        ("low_beam","beam",[-1000,140],[150,50]),
        ("low_wall","platform",[-200,25],[65,50]),
        ("tall_wall","platform",[650,125],[180,250])]:
        env["obstacles"].append({"id":oid,"kind":kind,"style":"girder","color":"#8197a8","center":center,"size":size})
    scene=raw["scenes"][0]
    scene["placements"][0].update(destination_x=1900,action_pace=True)
    scene["placements"][1].update(facing=1,z=40,pursue="iko",action_pace=True)
    raw["characters"][1]["style"].update(body_color="#ef826b",glow_color="#ef826b")
    scene["actions"]=[]
    scene["duration"]=24
    scene["shots"][0].update(end=24,camera={"mode":"follow","target":"iko","include":["char:pell"],"keep_in_frame":True,"view_height":720,"offset":[0,0]})
    scene["goals"]=["autonomous_reached@iko"]
    if paced:
        from apex.ai.action_pacing import fit_goal_scene
        raw=fit_goal_scene(raw,"s","iko")
    return raw

if __name__=="__main__":
    Path(sys.argv[1]).write_text(json.dumps(build(True)),encoding="utf-8")
