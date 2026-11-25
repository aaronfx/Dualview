"""Native three-actor encounter: attack, fall, cooperative recovery, escape."""
import runpy,json,sys
from copy import deepcopy
from pathlib import Path

def build():
    raw=runpy.run_path("examples/build_combined_crossing.py")["_two_char_scene"](0,-90,750,[])
    raw.update(id="ensemble_rescue",title="No one left behind")
    helper=deepcopy(raw["characters"][0])
    helper.update(id="ren",name="REN")
    helper["style"].update(body_color="#70df91",glow_color="#70df91")
    raw["characters"].append(helper)
    sc=raw["scenes"][0]
    sc.update(duration=14,actions=[],storyline="An intruder is knocked down by a guard. An ally helps the fallen intruder stand, then the intruder escapes.",goals=["ensemble_completed"])
    sc["placements"][0].update(x=0,facing=-1)
    sc["placements"][1].update(x=-90,facing=1)
    sc["placements"].append({"character":"ren","x":460,"facing":-1})
    sc["ensemble"]={"perform_emotions":True,"actors":[
        {"character":"iko","team":"blue","prompt":"Survive the guard and reach safety with assistance if hurt.","objective":"reach","destination_x":750},
        {"character":"pell","team":"red","prompt":"Intercept the intruder with a forceful knockdown strike.","objective":"intercept","target":"iko","impact":"knockdown","aggression":.95},
        {"character":"ren","team":"blue","prompt":"Watch your ally and physically help them stand if they fall.","objective":"assist","target":"iko","empathy":.95}
    ],"hostile_teams":[["blue","red"]]}
    sc["shots"][0].update(end=14,camera={"mode":"static","center":[300,200],"view_height":1000})
    return raw

if __name__=="__main__":
    Path(sys.argv[1]).write_text(json.dumps(build(),indent=2),encoding="utf-8")
