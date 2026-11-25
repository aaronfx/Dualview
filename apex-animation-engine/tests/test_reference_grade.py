from types import SimpleNamespace as NS
from math import pi
from apex.motion.performance_profile import angle_mix,blend_travel_upper,can_blend_travel
from apex.scene.ensemble_direction import tune_actions
from apex.scene.film_staging import duration_for_payoff
from apex.qa.visual_prop_audit import inside_box
import pytest


def pose(a):
    return NS(root=(2,3),body_angle=1.,facing=1.,local={'spine':a,'thigh_n':a,'head':a},stretch={'shin_n':1.05},hip_twist=.2,eye=1.,head_facing=1.)


def test_upper_body_blend_preserves_native_root_and_legs():
    a,b=pose(0.),pose(1.);x=blend_travel_upper(a,b,.5)
    assert x.root==b.root and x.body_angle==b.body_angle and x.local['thigh_n']==1.
    assert x.stretch==b.stretch and x.hip_twist==b.hip_twist and x.local['head']==.5
    assert b.local['head']==1.


def test_contact_and_turn_guard():
    a=NS(kind='loco',frame='floor',data={});b=NS(kind='loco',frame='floor',data={})
    assert can_blend_travel(a,b,pose(0),pose(1))
    b.data['carry']='core';assert not can_blend_travel(a,b,pose(0),pose(1))
    b.data={};b.frame='wall';assert not can_blend_travel(a,b,pose(0),pose(1))


def test_wrap_short_arc():
    assert abs(angle_mix(pi-.1,-pi+.1,.5)-pi)<1e-8


def test_pace_only_tunes_authored_act_without_duration():
    a=[dict(character='a',type='act',clip='cheer'),dict(character='a',type='act',clip='cheer',duration=1.),dict(character='a',type='strike',tempo=1.)]
    b=tune_actions(a);assert b[0]['tempo']==1.3 and b[1:]==a[1:]
    assert tune_actions(a,'measured')==a and 'tempo' not in a[0]


def test_duration_is_frame_aligned_and_bounded():
    assert duration_for_payoff(2.,24,1.)==3.
    assert duration_for_payoff(2.01,24,1.)*24==73
    with pytest.raises(ValueError):duration_for_payoff(60.,maximum=60)


def test_oriented_box():
    assert inside_box((0,4),(0,0),(20,8),pi/2,1)
    assert not inside_box((4,0),(0,0),(20,8),pi/2,1)
