"""Ten native actors, two cooperative teams, zero authored actions."""
import json,runpy,sys
from copy import deepcopy
from pathlib import Path

def build():
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](-850,850,-1250,[])
    raw.update(id="ensemble_ten",title="Two teams, one evacuation")
    env=raw["environments"][0]
    env["room"].update(width=3400,style="box",grid_alpha=.03)
    env["obstacles"][0]["size"][0]=3400
    env["theme"]={"accent":"#e5a94b","alert":"#ff3848","back":"#232932","floor":"#161b22","side":"#181e27","background":"#10151b"}
    env["decor"]=[{"kind":"panel","x":x,"y":250,"w":200,"h":120,"color":"#58616c"} for x in range(-1400,1500,400)]
    bases=deepcopy(raw["characters"])
    raw["characters"]=[]
    scene=raw["scenes"][0]
    scene.update(duration=9,actions=[],placements=[],storyline="Two evacuation teams must move to separate safe zones. Each teammate maintains formation around its leader, responding to the leader's actual progress.",goals=["ensemble_completed"])
    roles=[]
    for side,team,color in ((-1,"amber","#ffd04e"),(1,"cyan","#59d6ed")):
        leader=team+"_0"
        for i in range(5):
            cid=team+"_"+str(i)
            ch=deepcopy(bases[0])
            ch.update(id=cid,name=cid)
            ch["style"].update(body_color=color,glow_color=color)
            raw["characters"].append(ch)
            offset=-side*i*140
            scene["placements"].append({"character":cid,"x":side*850+offset,"facing":side,"z":0})
            role={"character":cid,"team":team,"prompt":"Lead your evacuation team to the safe zone." if i==0 else "Stay with your team leader and maintain your own separated formation position.","objective":"reach" if i==0 else "escort"}
            if i==0:
                role["destination_x"]=side*1250
            else:
                role.update(target=leader,offset=offset)
            roles.append(role)
    scene["ensemble"]={"actors":roles,"coordination_hz":5}
    scene["shots"][0].update(end=9,camera={"mode":"static","center":[0,200],"view_height":1500})
    return raw

if __name__=="__main__":
    from apex.ai.ensemble_editor import rehearse_ensemble
    path=Path(sys.argv[1])
    path.write_text(json.dumps(rehearse_ensemble(build(),"s",path.parent),indent=2),encoding="utf-8")
