"""Build native P1-P5 acceptance candidates from existing APEX stories.

Do not substitute this for the requested new original acceptance movie.
Run the baseline first; reuse native rescue and core-run production systems.
"""
from __future__ import annotations
import argparse,json,runpy
from pathlib import Path
from copy import deepcopy
from apex.scene.schema import ProjectSpec
from apex.scene.performance_upgrade import fuse_notice_travel,rehearse

HERE=Path(__file__).resolve().parent


def art(raw):
    out=deepcopy(raw)
    for char in out['characters']:
        st=char.setdefault('style',{})
        st.update(visual_profile='apex_ink',performance_profile='continuous',has_scarf=False)
    for env in out['environments']:
        bd=env.get('backdrop')
        if bd and bd['kind']=='tower':
            bd['art_profile']='industrial_depth'
        if env.get('room',{}).get('style','box')=='box':
            env.setdefault('room',{})['grid_alpha']=.18
    return out


def save(p,path):
    path.write_text(ProjectSpec.model_validate(p).model_dump_json(indent=2,exclude_defaults=True),encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('out',type=Path);p.add_argument('--search',action='store_true');args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    # Existing canonical production JSON supplies its authored shot timing.
    rescue=json.loads((HERE/'the_rescue.json').read_text(encoding='utf-8'))
    save(rescue,args.out/'rescue_baseline.json'); save(art(rescue),args.out/'rescue_ink.json')
    core=json.loads((HERE/'core_run.json').read_text(encoding='utf-8'))
    save(art(core),args.out/'core_run_ink.json')
    if args.search:
        # The source builder supplies event-derived cuts. Never reuse old
        # cuts for a plan whose action timing has changed.
        source=runpy.run_path(str(HERE/'build_rescue.py'))
        raw=art(source['project']()); sc=raw['scenes'][0]; a=sc['actions']
        winner,trace=rehearse(raw,sc['id'],[('original',a),('moving_notice',fuse_notice_travel(a))])
        raw=winner.model_dump(mode='json'); ev,_=source['event_times'](raw)
        raw['scenes'][0]['shots']=source['shots_from'](ev,raw['scenes'][0]['duration'])
        save(raw,args.out/'rescue_rehearsed.json')
        (args.out/'rehearsal.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')

if __name__=='__main__':main()
