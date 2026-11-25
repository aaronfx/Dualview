"""P1–P5 native benchmark production. No generated raster animation or fake physics."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from copy import deepcopy
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.autochoreo import Objective
from apex.scene.ensemble_direction import Partner,direct_ensemble
from apex.scene.film_staging import BeatShot,event_shots,duration_for_payoff
from apex.scene.goals import matches
from apex.qa.actor_pacing import audit_character
from apex.qa.visual_prop_audit import inspect_visual_props
from build_impossible_crossing import world as crossing_world,build as crossing_build

HERE=Path(__file__).resolve().parent


def art(raw):
    out=deepcopy(raw)
    for c in out['characters']:
        s=c.setdefault('style',{});s.update(visual_profile='apex_ink',performance_profile='continuous',has_scarf=False)
    for env in out['environments']:
        bd=env.get('backdrop')
        if bd and bd['kind']=='tower':bd['art_profile']='industrial_depth'
        if env.get('room',{}).get('style','box')=='box':env.setdefault('room',{})['grid_alpha']=.15
    out.update(width=1920,height=1080)
    return out


def A(actor,typ,**kw):return dict(character=actor,type=typ,**kw)


def relay_world(width=2100):
    # Original relay premise: courier must recover a live core beyond a barrier;
    # a teammate cooperates to unlock a two-person emergency door. All physical
    # geometry derives from the native obstacle benchmark. No fictional bridge
    # switch is animated independently of native world state.
    p=art(crossing_world(duration=24.0));p.update(id='the_relay',title='The Relay — emergency extraction')
    p['characters'].append(dict(id='pell',name='PELL',strength=47000,
        proportions=dict(spine=28,chest=26,head=25,thigh=44,shin=42),
        style=dict(visual_profile='apex_ink',performance_profile='continuous',body_color='#59d6ed',far_color='#2e8399',glow_color='#76e4f4',has_scarf=False,limb_width=7.5,cadence_scale=1.06)))
    e=p['environments'][0];e['id']='relay_station';e['room'].update(width=width,style='open',grid_alpha=.12)
    # A real floor platform supplies an authored visual floor at the native
    # room floor y=0; its top is exactly the physical floor, never a fake bridge.
    e['obstacles'][0].update(style='girder',color='#536d7f')
    e['backdrop']=dict(kind='tower',art_profile='industrial_depth',seed=42,weather='motes',weather_amount=.28,
        sky=['#080e19','#1b3040','#304853'],fog='#20313b')
    # Open rooms don't draw their implicit ground. A platform top at y=0 is
    # technically within the room floor; native rendering must show support.
    # Use a native solid floor beam rather than painted set dressing.
    # Existing implicit floor remains the contact authority. A girder below
    # its surface is drawn through native World without changing the floor plane.
    e['obstacles'].append(dict(id='station_floor',kind='beam',center=[0,-25],size=[width,50],style='girder',color='#455a66'))
    e['exits']=[dict(id='airlock',surface='wall_right',s=100,width=210,sealed=True,unlock_on='together:iko,pell',open_radius=280)]
    sc=p['scenes'][0];sc.update(id='relay',environment=e['id'],title='Emergency extraction',goals=['notice@iko','pick_up@iko[prop=spark]','exit_together','exit_reached@iko','exit_reached@pell'])
    sc['placements'][0]['z']=0
    sc['placements'].append(dict(character='pell',x=620,facing=-1,z=45))
    sc['actions']=[A('iko','idle',duration=.5),A('pell','idle',duration=.5)]
    sc['shots']=[dict(id='rehearsal',kind='wide',start=0,end=sc['duration'],camera=dict(mode='follow',target='iko',view_height=780,offset=[75,40],include=['char:pell']))]
    return p


def relay():
    raw=relay_world();sc=raw['scenes'][0];sid=sc['id'];right=raw['environments'][0]['room']['width']/2
    obj=Objective(sid,'iko','barrier','spark',max_trial_seconds=24,max_jump_apex=210,movable_prop_id='crate',pacing='active')
    partner=Partner('pell','pick_up@iko[prop=spark]',(
        A('pell','act',clip='wave_on',emotion='joyful',duration=.65),
        A('pell','walk_to',target_x=right-165,speed=230,lane=40),
        A('pell','wait_for',until='event:exit_together'),
        A('pell','wait_for',until='event:exit_reached@iko'),
        A('pell','reach_exit',target='exit:airlock',speed=220),))
    finish=(A('iko','run_to',target_x=right-110,speed=320,lane=-35),
            A('iko','wait_for',until='event:exit_together'),
            A('iko','reach_exit',target='exit:airlock',speed=210))
    winner,trace=direct_ensemble(raw,obj,(partner,),finish)
    rt=SceneRuntime(winner,sid);sim=rt.simulate();data=winner.model_dump(mode='json');sc=data['scenes'][0]
    last=next(e.t for e in sim.events if matches('exit_reached@pell',e));d=duration_for_payoff(last,tail=.8,maximum=24)
    sc['duration']=d
    # Event-derived shot boundaries. If cuts are too close, fail with evidence
    # instead of delaying an actor to accommodate a camera.
    sc['shots']=event_shots(sim.events,d,[
        BeatShot('approach','tracking',dict(mode='follow',target='iko',view_height=580,offset=[80,45]),description='Courier observes and clears the station barrier.'),
        BeatShot('core','medium',dict(mode='follow',target='iko',view_height=430,offset=[55,30]),'pick_up@iko[prop=spark]',-.20,'Core retrieved, partner responds.'),
        BeatShot('together','wide',dict(mode='static',center=[right-165,140],view_height=390,include=['char:iko','char:pell']),'exit_together',-.20,'Both actors reach the sealed airlock.'),
    ])
    sc['shots'][-1]['fade_out']=.5
    final=ProjectSpec.model_validate(data)
    from apex.ai.director import StoryDirector
    StoryDirector._dry_run(final)
    trace['selected_scene_duration']=d
    return final,trace


def write(project,path):
    p=ProjectSpec.model_validate(project);path.write_text(p.model_dump_json(indent=2,exclude_defaults=True),encoding='utf-8')


def evidence(p,path):
    rt=SceneRuntime(p,p.scenes[0].id);sim=rt.simulate()
    report=dict(events=[dict(t=e.t,type=e.type,character=e.character,data=e.data) for e in sim.events],
                pacing=[audit_character(sim,c).to_dict() for c in sim.controllers],
                visual_prop_warnings=inspect_visual_props(rt),
                controller_violations={c:q.violation for c,q in sim.controllers.items() if q.violation})
    path.write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    if report['controller_violations']:raise RuntimeError('native controller violation; see '+str(path))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('out',type=Path);ap.add_argument('--case',choices=['relay','crossing','rescue','combat','core','math'],required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if a.case=='relay':
        p,trace=relay();write(p,a.out/'relay.json');(a.out/'relay.plan.json').write_text(json.dumps(trace,indent=2,default=str),encoding='utf-8');evidence(p,a.out/'relay.evidence.json');return
    if a.case=='crossing':p,trace=crossing_build();raw=p.model_dump(mode='json');(a.out/'crossing.plan.json').write_text(json.dumps(trace.report(),indent=2),encoding='utf-8')
    else:
        names={'rescue':'the_rescue.json','combat':'first_exchange.json','core':'core_run.json'}
        if a.case=='math':
            # Prefer the newer native semantic-transposition builder if installed.
            import runpy
            newer=HERE/'build_semantic_transposition.py'
            if newer.exists():raw=runpy.run_path(str(newer))['project'](2,5,'add')
            else:raise RuntimeError('semantic-transposition branch not integrated; do not substitute old throw-away algebra')
        else:raw=json.loads((HERE/names[a.case]).read_text(encoding='utf-8'))
    raw.update(width=1920,height=1080);write(raw,a.out/f'{a.case}_baseline.json');p=ProjectSpec.model_validate(art(raw));write(p,a.out/f'{a.case}_upgraded.json')
    evidence(p,a.out/f'{a.case}.evidence.json')

if __name__=='__main__':main()
