"""Independent liveness gate for every story actor, using physical records."""
def audit_hostile_liveness(sim,placements,*,max_idle=1.6):
    reports={}
    for pl in placements:
        role=pl.get("actor_role")
        if not role:
            continue
        cid=pl["character"]
        ctrl=sim.controllers[cid]
        target=sim.controllers[role["opponent"]]
        terminal=next((e.t for e in sim.events if e.character==role["opponent"] and e.type=="autonomous_reached"),sim.duration) if role["role"]=="hunter" else next((e.t for e in sim.events if e.character==cid and e.type=="autonomous_reached"),sim.duration)
        stalls=[]
        from .actor_pacing import audit_character
        pacing=audit_character(sim,cid,min_pause=.38,max_waste=.65)
        for window in pacing.windows:
            if window.category=="movement_stall" and min(window.end,terminal)-window.start>max_idle:
                stalls.append({"start":window.start,"end":min(window.end,terminal),"kind":"movement_stall"})
        for seg in ctrl.segments:
            end=min(seg.t1,terminal)
            if seg.kind=="idle" and end-seg.t0>max_idle:
                # A generic fight flag is not proof of deliberate performance.
                stalls.append({"start":round(seg.t0,3),"end":round(end,3),"kind":"idle","fight":bool(seg.data.get("fight"))})
        reports[cid]={"passed":not stalls,"stalls":stalls,"terminal":terminal,
            "final_x":ctrl.records[-1].pos[0],"opponent_final_x":target.records[-1].pos[0],
            "blocked":[{"t":e.t,**e.data} for e in sim.events if e.character==cid and e.type=="autonomous_blocked"]}
    return reports
