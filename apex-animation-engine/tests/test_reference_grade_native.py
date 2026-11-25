"""Native execution contract. No mocks of SceneRuntime or Skia."""
from apex.scene.schema import CharacterStyle,ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.film_staging import event_shots,BeatShot
from apex.scene.ensemble_direction import Partner
from apex.motion.controller import Event
from apex.qa.visual_prop_audit import inspect_visual_props
from apex.qa.transitions import scene
import pytest


def test_continuous_is_opt_in():
    assert CharacterStyle().performance_profile=='legacy'
    assert CharacterStyle(performance_profile='continuous').performance_profile=='continuous'


def test_native_event_cut_and_rejection():
    a=BeatShot('a','wide',{'mode':'static','center':[0,0]})
    b=BeatShot('b','medium',{'mode':'static','center':[0,0]},'pick_up@kai[prop=core]')
    ev=[Event(1.,'pick_up','kai',{'prop':'core'})]
    shots=event_shots(ev,3.,[a,b]);assert shots[0]['end']==shots[1]['start']==1.
    with pytest.raises(ValueError):event_shots([],3.,[a,b])


def test_native_partner_actions_validate():
    p=Partner('rho','pick_up@kai[prop=core]',({'character':'rho','type':'act','clip':'cheer'},))
    assert p.compile()[0]['until']=='event:pick_up@kai[prop=core]'


def test_style_does_not_change_physics_events():
    raw=scene([dict(character='kai',type='run_to',target_x=-520,speed=200),dict(character='kai',type='run_to',target_x=-650,speed=200)], [dict(character='rho',type='idle',duration=4.)],dur=4.)
    baseline=ProjectSpec.model_validate(raw);a=SceneRuntime(baseline,'s').simulate()
    raw['characters'][0].setdefault('style',{}).update(visual_profile='apex_ink',performance_profile='continuous')
    updated=ProjectSpec.model_validate(raw);rt=SceneRuntime(updated,'s');b=rt.simulate()
    assert [(e.t,e.type,e.character) for e in a.events]==[(e.t,e.type,e.character) for e in b.events]
    for cid in a.controllers:
        assert [r.pos for r in a.controllers[cid].records]==[r.pos for r in b.controllers[cid].records]
    assert isinstance(inspect_visual_props(rt),list)
