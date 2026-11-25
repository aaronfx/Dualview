"""Run native acceptance on fresh briefs; never count templates as AI success.

Usage: python examples/smart_director_acceptance.py briefs.json --out out/acceptance
Paid provider must be explicitly configured and approved. No default API use.
Each input is {"id": "...", "brief":"...", "required_goals":["..."]}.
The benchmark goals are independently authored and not inserted into the AI plan.
"""
import argparse,json,re
from pathlib import Path
from apex.ai.local_production import create_from_brief,run_production,atomic
from apex.scene.runtime import SceneRuntime
from apex.ai.smart_director import ordered_evidence

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("briefs",type=Path);parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--enable-paid-benchmark",action="store_true")
    a=parser.parse_args()
    if not a.enable_paid_benchmark:parser.error("Explicit paid benchmark flag required; uses existing spend controls")
    if a.out.exists() and any(a.out.iterdir()):parser.error("Use fresh benchmark directory")
    briefs=json.loads(a.briefs.read_text());a.out.mkdir(parents=True,exist_ok=True);rows=[]
    if not 1<=len(briefs)<=20:parser.error("1..20 independent briefs")
    for case in briefs:
        cid=case["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}",cid):raise ValueError("Invalid case id")
        row={"id":cid,"technical":False,"artistic":"pending"};d=a.out/cid
        try:
            p=create_from_brief(case["brief"],d,reason=f"Owner approved benchmark {cid}")
            events=[];offset=0.
            for s in p.scenes:
                sim=SceneRuntime(p,s.id,strict=False).simulate(physics_only=True)
                from types import SimpleNamespace
                events.extend(SimpleNamespace(t=e.t+offset,type=e.type,character=e.character,data=e.data) for e in sim.events)
                offset+=s.duration
            row["independent_goals"]=ordered_evidence(case["required_goals"],events,offset)
            report=run_production(d)
            row["technical"]=report["technical_pass"]
        except Exception as exc:row["error"]=f"{type(exc).__name__}: {exc}"
        rows.append(row);atomic(a.out/"acceptance.json",{"cases":rows,"technical_success":sum(x["technical"] for x in rows),
                 "attempted":len(rows),"artistic_success":"not measured"})
    return 0 if all(x["technical"] for x in rows) else 2
if __name__=="__main__":raise SystemExit(main())
