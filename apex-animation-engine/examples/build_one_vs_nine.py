"""60-second one-versus-nine autonomous facility gauntlet.

Environment layout and story goals are authored; actions are not.
"""
import json,sys,runpy
from copy import deepcopy
from pathlib import Path

def build():
    raw=runpy.run_path("examples/build_autonomous_chase.py")["build"](hostile=True)
    raw.update(id="one_vs_nine",title="LOCKDOWN: One Against Nine")
    env=raw["environments"][0]
    # A longer extension of the approved facility visual style; legacy
    # hostile chase is not changed.
    env["room"]["width"]=19000
    env["obstacles"]=[deepcopy(env["obstacles"][0])]
    env["obstacles"][0]["size"][0]=19000
    for i,(x,kind,wh) in enumerate([(-5500,"beam",(150,50)),(-2700,"platform",(65,50)),(300,"platform",(180,250)),(3200,"beam",(150,50)),(6100,"platform",(65,50))]):
        y=140 if kind=="beam" else wh[1]/2
        env["obstacles"].append({"id":"hazard_"+str(i),"kind":kind,"style":"girder","color":"#a58b55","center":[x,y],"size":list(wh)})
    env["decor"]=[{"kind":"pipe","x":-9400,"y":440,"x2":9400,"y2":440,"color":"#7c8791"}]
    for i,x in enumerate(range(-9000,9300,420)):
        env["decor"] += [{"kind":"panel","x":x,"y":250,"w":230,"h":145,"color":"#58616c"},{"kind":"lamp","x":x,"y":650,"color":"#e8ae70"},{"kind":"screen","x":x+120,"y":330,"w":130,"h":70,"text":"LOCKDOWN" if i%2==0 else "SECURITY","color":"#d74d46"}]
    hero,base=deepcopy(raw["characters"])
    raw["characters"]=[hero]
    sc=raw["scenes"][0]
    sc.update(duration=60,storyline="A lone yellow infiltrator must escape an industrial lockdown. Nine red security fighters independently attempt to stop him. He uses movement, defense, counterattacks and the facility's obstacles to survive. The guards coordinate attack opportunities and recover when injured. The ending is decided by native outcomes.",actions=[],placements=[{"character":"iko","x":-8400,"facing":1,"z":0}],goals=["conflict_escape@iko"])
    roles=[{"character":"iko","team":"infiltrator","prompt":"You are alone and surrounded by enemies. Fight only to create a path to freedom. Avoid being trapped and keep moving toward the exit.","objective":"reach","destination_x":8600,"aggression":.92,"courage":.95}]
    for i,x in enumerate((-8310,-6750,-4050,-1700,1500,4400,6900,7900,8440)):
        cid="guard_"+str(i+1)
        ch=deepcopy(base)
        ch.update(id=cid,name="GUARD "+str(i+1))
        ch["style"]["motion_intelligence"]=True
        raw["characters"].append(ch)
        sc["placements"].append({"character":cid,"x":x,"facing":-1,"z":0})
        roles.append({"character":cid,"team":"security","prompt":"You are a hostile security fighter. Stop the infiltrator, coordinate with nearby teammates and resume the mission after physical recovery.","objective":"intercept","target":"iko","aggression":.7+.025*i,"courage":.8,"priority":5+i%3})
    sc["ensemble"]={"actors":roles,"hostile_teams":[["infiltrator","security"]],"coordination_hz":10,"conflict":{"protagonist":"iko","activation_radius":650,"attack_slots":2,"recovery_delay":2.5}}
    sc["shots"]=[{"id":"hero_tracking","kind":"tracking","start":0,"end":60,"camera":{"mode":"follow","target":"iko","view_height":650,"lead":.14,"keep_in_frame":True,"offset":[0,0]}}]
    return raw

def report(raw):
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    p=ProjectSpec.model_validate(raw)
    sim=SceneRuntime(p,"s").simulate(physics_only=True)
    events=sim.events
    hit=[e for e in events if e.type=="hit"]
    hero_hits=[e for e in hit if e.character=="iko"]
    foes={e.character for e in events if e.type=="conflict_engagement"}
    traversals=[e for e in events if e.character=="iko" and e.type in ("slide_end","vault","climbed","takeoff")]
    escape=next((e.t for e in events if e.type=="conflict_escape"),None)
    hero_records=sim.controllers["iko"].records
    max_idle=0.
    start=None
    for i in range(1,len(hero_records)):
        a,b=hero_records[i-1],hero_records[i]
        # Continuous non-displacement can be valid during a contact/recovery,
        # so report the measure rather than count it as a physics failure.
        if abs(b.pos[0]-a.pos[0])<.5:
            if start is None:start=a.t
            max_idle=max(max_idle,b.t-start)
        else:start=None
    friendly=[e for e in hit if (e.character=="iko")== (e.data.get("target")=="iko")]
    result={"duration":60,"actors":len(p.characters),"authored_actions":len(p.scene("s").actions),"enemy_engagements":sorted(foes),"hero_hits":len(hero_hits),"hero_targets":sorted({e.data["target"] for e in hero_hits}),"enemy_hits":len(hit)-len(hero_hits),"friendly_fire":len(friendly),"escape_time":escape,"traversals":[{"time":e.t,"type":e.type} for e in traversals],"max_low_displacement_seconds":max_idle,"final":{k:{"x":v.s,"mode":v.mode,"lying":v.lying,"action":v.cur.type if v.cur else None} for k,v in sim.controllers.items()},"events":[{"t":e.t,"actor":e.character,"event":e.type,"data":e.data} for e in events if e.type in ("conflict_engagement","conflict_escape","conflict_recovery","ensemble_intent","hit","whiff","blocked","knockdown","autonomous_blocked","autonomous_decision","stood_up","slide_end","vault","climbed","takeoff")]}
    result["passed"]=bool(len(foes)==9 and len(result["hero_targets"])>=5 and not friendly and len(traversals)>=2 and escape is not None and 50<=escape<=59.9)
    return result

if __name__=="__main__":
    path=Path(sys.argv[1])
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=build()
    path.write_text(json.dumps(raw,indent=2),encoding="utf-8")
    evidence=report(raw)
    (path.parent/"conflict_evidence.json").write_text(json.dumps(evidence,indent=2,default=str),encoding="utf-8")
    print({k:v for k,v in evidence.items() if k!="events"})
    if not evidence["passed"]:
        raise SystemExit("Narrative acceptance failed; inspect conflict_evidence.json")
