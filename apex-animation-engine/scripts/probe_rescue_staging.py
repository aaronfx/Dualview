"""Find physically coherent spectator positions without reverse crate recoil.

Run via GitHub Actions: python scripts/probe_rescue_staging.py
Does not modify the baseline scene JSON.
"""
import json
from pathlib import Path
import os
import numpy as np
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

os.environ["APEX_EXPERIMENTAL_ACTIVE_FALL"] = "1"
os.environ["APEX_EXPERIMENTAL_JOINTED_FALL"] = "1"
data0=json.loads((Path(__file__).resolve().parents[1] / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
cases=[
(170,185,330,.028),(200,210,400,.028),(235,235,450,.028),
(260,270,450,.028),(290,295,500,.028),(320,325,550,.028),
(350,355,600,.028),(420,425,650,.028),(260,270,650,.028),
(-270,-265,400,.028),(-230,-225,480,.028),(-180,-175,450,.028),
(185,185,330,.07),(235,235,450,.07),(260,270,450,.10),
]
for start,target,run,friction in cases:
    d=json.loads(json.dumps(data0))
    place=next(p for p in d["scenes"][0]["placements"] if p["character"]=="juno")
    place["x"]=start
    acts=d["scenes"][0]["actions"]
    next(a for a in acts if a["character"]=="juno" and a["type"]=="walk_to")["target_x"]=target
    next(a for a in acts if a["character"]=="juno" and a["type"]=="run_to")["speed"]=run
    next(p for p in d["environments"][0]["props"] if p["id"]=="container")["friction"]=friction
    try:
        rt=SceneRuntime(ProjectSpec.model_validate(d), "rescue")
        res=rt.simulate()
        times=res.prop_times
        x=res.prop_tracks["container"][:,0]
        pre=[e.t for e in res.events if e.type=="push_lost" and e.character=="milo"]
        t0=pre[0] if pre else 3.4
        indices=(times>t0)&(times<7.5)
        rr=x[indices]
        peak=float(rr.max()) if len(rr) else -1000
        recoil=float(peak-rr[-1]) if len(rr) else 999
        vx=np.gradient(x,times)
        min_v=float(vx[indices].min()) if len(rr) else -1000
        types={e.type for e in res.events}
        needed={"push_lost","rope_snap","body_fall","pinned","notice","lift_start","lift_fail","pick_up","lever_place","lever_engage","crawl_start","freed","hand_grab","stood_up","fist_bump"}
        missing=needed-types
        boundaries={s["id"]: (s["start"],s["end"],s.get("exit_conditions",[])) for s in d["scenes"][0]["shots"]}
        missed_shots=[]
        for sid,(lo,hi,requirements) in boundaries.items():
            for v in requirements:
                event_name=v.split(":")[1].split("@")[0]
                if not any(e.type==event_name and lo<=e.t<=hi for e in res.events):
                    missed_shots.append(sid+":"+event_name)
        juno=res.controllers["juno"].records
        push=next((s for s in res.controllers["milo"].segments if s.kind=="push"),None)
        push_safe=not push or all(abs(record.pos[0]-float(x[np.argmin(abs(times-record.t))]))>60 for record in juno if push.t0<=record.t<=min(push.t1,3.4))
        print(f"CASE start={start:4} target={target:4} run={run:3} fr={friction:.3f}: x_peak={peak:.1f} recoil={recoil:.1f} min_v={min_v:.1f} all_events={not missing} shot_miss={missed_shots} safe={push_safe}",flush=True)
    except Exception as ex:
        print(f"CASE start={start} target={target} run={run} fr={friction}: ERROR {type(ex).__name__} {ex}",flush=True)
