"""LOCKDOWN master production: one continuous native timeline, seven act gates.

This is an intentionally fail-closed rehearsal, not an accepted film.
No state resets at act boundaries and no authored actor action sequences.
"""
import json,sys,runpy,math
from copy import deepcopy
from pathlib import Path

PLAN=Path(__file__).with_name("lockdown_production.json")
def plan():
    return json.loads(PLAN.read_text(encoding="utf-8"))

def build():
    spec=plan()
    raw=runpy.run_path("examples/build_one_vs_nine.py")["build"]()
    raw.update(id="lockdown_master",title=spec["title"])
    sc=raw["scenes"][0]
    sc["duration"]=spec["duration"]
    sc["storyline"]=" ".join(f'{a["title"]}: '+", ".join(a["dramatic_requirements"]) for a in spec["acts"])
    sc["ensemble"]["conflict"].update(attack_slots=3,require_distinct_contacts=True)
    for role,style in zip(sc["ensemble"]["actors"][1:],spec["actors"]):
        role["combat_style"]=style
        role["prompt"]+=f" Your combat specialty is {style}; choose native feasible techniques."
        if style in ("power","commander"):
            role["impact"]="knockdown"
    sc["shots"]=[{"id":"act_"+a["id"],"start":a["start"],"end":a["end"],"kind":"tracking",
        "description":a["title"],"action_objectives":a["dramatic_requirements"],
        "camera":{"mode":"follow","target":"iko","view_height":650 if a["id"] not in ("ambush","commander") else 580,
                  "lead":.14,"keep_in_frame":True,"shake":.35}} for a in spec["acts"]]
    return raw

def longest_gap(times,start,end):
    ordered=[start,*sorted(set(t for t in times if start<=t<=end)),end]
    return max((b-a for a,b in zip(ordered,ordered[1:])),default=0.)

def audit(raw,sim):
    spec=plan()
    events=sim.events
    results=[]
    for act in spec["acts"]:
        subset=[e for e in events if act["start"]<=e.t<act["end"]]
        present={e.type for e in subset}
        missing=sorted(set(act["required_events"])-present)
        # Do not count queue decisions, footstep repetition or intent labels
        # as story progress. Only observable native contact and world events.
        significant={"hit","blocked","whiff","knockdown","stood_up","slide_end","vault","climbed","hand_grab","pick_up","throw","switch_activated","collapse","conflict_escape","ledge_catch","pulled_up"}
        gap=longest_gap([e.t for e in subset if e.type in significant],act["start"],act["end"])
        results.append({"act":act["id"],"missing_events":missing,"max_story_gap":gap,"native_events":{k:sum(e.type==k for e in subset) for k in sorted(present&significant)},"passed":not missing and gap<=spec["maximum_story_event_gap_seconds"]})
    hero=sim.controllers["iko"]
    idle=[]
    for seg in hero.segments:
        if seg.kind=="idle" and not seg.data.get("act") and not seg.data.get("gaze_mode") and seg.t1-seg.t0>spec["maximum_unmotivated_idle_seconds"]:
            idle.append({"start":seg.t0,"end":seg.t1,"duration":seg.t1-seg.t0})
    foes={e.character for e in events if e.type=="conflict_engagement"}
    targets={e.data.get("target") for e in events if e.type=="hit" and e.character=="iko"}
    friendly=[e for e in events if e.type=="hit" and (e.character=="iko")== (e.data.get("target")=="iko")]
    escape=next((e.t for e in events if e.type=="conflict_escape"),None)
    passed=all(a["passed"] for a in results) and len(foes)==9 and len(targets)>=spec["minimum_distinct_hero_targets"] and not friendly and not idle and escape is not None and 152<=escape<=160
    return {"duration":160,"actor_count":len(sim.controllers),"authored_actions":len(raw["scenes"][0]["actions"]),"acts":results,"hero_idle_segments":idle,"enemy_engagements":sorted(foes),"hero_targets":sorted(targets),"friendly_fire":len(friendly),"escape_time":escape,"native_acceptance":passed,"creative_review":"not performed","final":{k:{"x":v.s,"mode":v.mode,"lying":v.lying,"action":v.cur.type if v.cur else None} for k,v in sim.controllers.items()}}

if __name__=="__main__":
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    path=Path(sys.argv[1])
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=build()
    path.write_text(json.dumps(raw,indent=2),encoding="utf-8")
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    evidence=audit(raw,sim)
    (path.parent/"production_evidence.json").write_text(json.dumps(evidence,indent=2,default=str),encoding="utf-8")
    print(json.dumps(evidence,indent=2,default=str))
    if not evidence["native_acceptance"]:
        raise SystemExit("Master film rejected by narrative and pacing gates")
