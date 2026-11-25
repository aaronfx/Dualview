"""Native telemetry critic with timestamped, bounded repair suggestions.

This is not a learned visual model. Actual image/video artistic review remains
a distinct gate. Suggestions never modify physics or remove required goals.
"""
from __future__ import annotations
from .actor_pacing import audit_character
from .visual_prop_audit import inspect_visual_props

def critique(runtime):
    sim=runtime.result or runtime.simulate()
    findings=[]
    for cid in sim.controllers:
        report=audit_character(sim,cid)
        for w in report.windows:
            if w.counted:
                findings.append({"kind":w.category,"actor":cid,"start":w.start,"end":w.end,
                                 "severity":"advisory","reason":w.reason,
                                 "repair":"shorten unmotivated idle or rehearse a feasible alternative"})
    for w in inspect_visual_props(runtime):
        findings.append({"kind":"visible_prop_overlap","severity":"advisory",**w,
                         "repair":"inspect foreground overlap; use collision-aware route if physically solid"})
    for e in sim.events:
        if e.type in ("action_impossible","morph_blocked","help_missed","grab_missed"):
            findings.append({"kind":e.type,"actor":e.character,"start":e.t,"end":e.t,
                             "severity":"review","reason":e.data,
                             "repair":"rehearse corrected native action or layout"})
    return {"method":"native telemetry; not an image-space AI review",
            "artistic_review":"required","findings":findings}

def repair_candidates(project,scene_id):
    """Conservative pacing alternatives. Every change needs full native rehearsal."""
    scene=project.scene(scene_id)
    original=[a.model_dump(mode="json") for a in scene.actions]
    yield {"name":"original","actions":original}
    for ratio in (.75,.5):
        actions=[dict(a) for a in original]
        changed=False
        for a in actions:
            if a["type"]=="idle" and (a.get("duration") or 0)>.65 and not a.get("until"):
                a["duration"]=max(.45,a["duration"]*ratio);changed=True
        if changed:yield {"name":f"shorten_idle_{ratio}","actions":actions}
