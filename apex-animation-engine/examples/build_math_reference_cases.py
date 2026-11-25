"""Render each exact signed-term acceptance case in both native styles."""
import argparse,json,runpy
from pathlib import Path
from apex.scene.schema import ProjectSpec
from apex.scene.math_rehearsal import rehearse,verify
from build_reference_grade import art

CASES={'math_add_2_5':(2,5,'add'),'math_add_4_9':(4,9,'add'),'math_sub_4_9':(4,9,'sub')}

def main():
    p=argparse.ArgumentParser();p.add_argument('out',type=Path);p.add_argument('--case',choices=CASES,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    base=runpy.run_path(str(Path(__file__).with_name('build_semantic_transposition.py')))['_base_project'](*CASES[a.case])
    selected,trace=rehearse(base);selected.update(width=1920,height=1080)
    upgraded=art(selected)
    # Math world is minimalist. No industrial background added to a lesson.
    for label,raw in [('baseline',selected),('upgraded',upgraded)]:
        proof=verify(raw);stem=a.case+'_'+label
        (a.out/(stem+'.json')).write_text(ProjectSpec.model_validate(raw).model_dump_json(indent=2,exclude_defaults=True),encoding='utf-8')
        (a.out/(stem+'.proof.json')).write_text(json.dumps(dict(rehearsal=trace,final=proof),indent=2),encoding='utf-8')
if __name__=='__main__':main()
