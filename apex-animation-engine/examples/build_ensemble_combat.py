"""Ten actors in five live hostile encounters; no authored action queues."""
import runpy
from copy import deepcopy

def build():
    raw=runpy.run_path("examples/build_ensemble_ten.py")["build"]()
    raw.update(id="ensemble_combat",title="Five hostile encounters")
    env=raw["environments"][0]
    env["room"]["width"]=6200
    env["obstacles"][0]["size"][0]=6200
    sc=raw["scenes"][0]
    sc.update(duration=9,storyline="Five security agents intercept five escaping intruders. Each agent selects a hostile target and attempts a real hit. Intruders move to their individual escape destinations.",goals=[])
    for i in range(5):
        x=-2200+i*950
        for team in ("amber","cyan"):
            cid=team+"_"+str(i)
            pl=next(p for p in sc["placements"] if p["character"]==cid)
            role=next(a for a in sc["ensemble"]["actors"] if a["character"]==cid)
            role.pop("target",None)
            role.pop("offset",None)
            if team=="amber":
                pl.update(x=x,facing=1,z=0)
                role.update(objective="intercept",prompt="Intercept a hostile intruder and land a genuine attack.",aggression=.9)
                role.pop("destination_x",None)
            else:
                pl.update(x=x+90,facing=-1,z=0)
                role.update(objective="reach",destination_x=x+420,prompt="Escape the hostile agent and reach your safe position.")
    sc["ensemble"]["hostile_teams"]=[["amber","cyan"]]
    sc["shots"][0].update(end=9,camera={"mode":"static","center":[0,200],"view_height":2900})
    return raw
