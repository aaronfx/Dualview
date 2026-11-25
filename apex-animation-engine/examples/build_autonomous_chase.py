"""Two independent objectives, one continuous action environment."""
import json,sys,runpy
from pathlib import Path

def build(paced=False, hostile=False):
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
    if hostile:
        raw["id"]="hostile_facility"
        raw["title"]="Hostile Facility Escape"
        scene["placements"][1].update(x=-1740,z=0,hostile_pursuit=True)
        env["room"].update(road_view=False,style="box",grid_alpha=.03)
        env["theme"]={"accent":"#e5a94b","alert":"#ff3848","back":"#232932","floor":"#161b22","side":"#181e27","background":"#10151b"}
        env["decor"]=[{"kind":"pipe","x":-2500,"y":440,"x2":2500,"y2":440,"color":"#7c8791"}]
        for i,x in enumerate(range(-2200,2400,420)):
            env["decor"] += [{"kind":"panel","x":x,"y":250,"w":230,"h":145,"color":"#58616c"},{"kind":"lamp","x":x,"y":650,"color":"#e8ae70"},{"kind":"screen","x":x+120,"y":330,"w":130,"h":70,"text":"LOCKDOWN" if i%2==0 else "SECURITY","color":"#d74d46"}]
        for ob in env["obstacles"]:
            ob["color"]="#58636e" if ob["id"]=="ground" else "#a58b55"
        raw["characters"][1]["style"].update(body_color="#ed4545",glow_color="#ff3333",limb_width=10.0)
    if paced:
        from apex.ai.action_pacing import fit_goal_scene
        raw=fit_goal_scene(raw,"s","iko")
    return raw

if __name__=="__main__":
    Path(sys.argv[1]).write_text(json.dumps(build(True, hostile='--hostile' in sys.argv)),encoding="utf-8")
