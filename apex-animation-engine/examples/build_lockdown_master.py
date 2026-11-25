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
    # The original 17,000-unit route ended after 62.7 seconds. Expand
    # the playable corridor, not the motion duration or actor speed.
    scale=2.65
    env=raw["environments"][0]
    env["room"]["width"]*=scale
    env["obstacles"][0]["size"][0]*=scale
    for obstacle in env["obstacles"][1:]:
        obstacle["center"][0]*=scale
    # Intermediate traversal challenges keep the new route playable.
    for i,x in enumerate((-7700,-4200,-1100,2100,4800,7600)):
        env["obstacles"].append({"id":f"extended_hazard_{i}","kind":"beam" if i%2==0 else "platform",
            "style":"girder","color":"#a58b55","center":[x*scale,140 if i%2==0 else 25],
            "size":[150,50] if i%2==0 else [65,50]})
    env["decor"]=[{"kind":"pipe","x":-24900,"y":440,"x2":24900,"y2":440,"color":"#7c8791"}]
    for i,x in enumerate(range(-24500,24900,420)):
        env["decor"] += [{"kind":"panel","x":x,"y":250,"w":230,"h":145,"color":"#58616c"},
                         {"kind":"lamp","x":x,"y":650,"color":"#e8ae70"},
                         {"kind":"screen","x":x+120,"y":330,"w":130,"h":70,"text":"LOCKDOWN" if i%2==0 else "SECURITY","color":"#d74d46"}]
    # Keep opening contact distance intact; distribute the remaining cast.
    for placement in sc["placements"]:
        placement["x"]*=scale
    sc["placements"][1]["x"]=sc["placements"][0]["x"]+90
    sc["ensemble"]["actors"][0]["destination_x"]*=scale
    sc["storyline"]=" ".join(f'{a["title"]}: '+", ".join(a["dramatic_requirements"]) for a in spec["acts"])
    sc["ensemble"]["conflict"].update(attack_slots=3,require_distinct_contacts=True,activation_radius=1100)
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

def opening_preview(raw):
    result=deepcopy(raw)
    scene=result["scenes"][0]
    scene["duration"]=15
    scene["shots"]=scene["shots"][:1]
    scene["goals"]=[]
    result["id"]="lockdown_opening_rehearsal"
    result["title"]="LOCKDOWN opening rehearsal (unaccepted draft)"
    return result

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
    passed=all(a["passed"] for a in results) and len(foes)==9 and len(targets)>=spec["minimum_distinct_hero_targets"] and not friendly and not idle and escape is not None and spec["acts"][-1]["start"]<=escape<=spec["duration"]
    return {"duration":spec["duration"],"actor_count":len(sim.controllers),"authored_actions":len(raw["scenes"][0]["actions"]),"acts":results,"hero_idle_segments":idle,"enemy_engagements":sorted(foes),"hero_targets":sorted(targets),"friendly_fire":len(friendly),"escape_time":escape,"native_acceptance":passed,"creative_review":"not performed","final":{k:{"x":v.s,"mode":v.mode,"lying":v.lying,"action":v.cur.type if v.cur else None} for k,v in sim.controllers.items()}}

if __name__=="__main__":
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    path=Path(sys.argv[1])
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=build()
    path.write_text(json.dumps(raw,indent=2),encoding="utf-8")
    sim=SceneRuntime(ProjectSpec.model_validate(raw),"s").simulate(physics_only=True)
    evidence=audit(raw,sim)
    (path.parent/"opening_preview.json").write_text(json.dumps(opening_preview(raw),indent=2),encoding="utf-8")
    (path.parent/"native_trace.json").write_text(json.dumps([{"t":e.t,"actor":e.character,"event":e.type,"data":e.data} for e in sim.events if e.type in ("autonomous_decision","autonomous_blocked","autonomous_replan","autonomous_reached","conflict_engagement","hit","whiff","blocked","knockdown","stood_up","slide_end","vault","climbed","takeoff","ensemble_intent","body_block","adaptive_evade","adaptive_resume","action_impossible","conflict_escape")],indent=2,default=str),encoding="utf-8")
    (path.parent/"production_evidence.json").write_text(json.dumps(evidence,indent=2,default=str),encoding="utf-8")
    print(json.dumps(evidence,indent=2,default=str))
    if not evidence["native_acceptance"]:
        raise SystemExit("Master film rejected by narrative and pacing gates")
