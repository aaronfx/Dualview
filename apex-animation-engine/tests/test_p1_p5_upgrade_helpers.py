from types import SimpleNamespace
from math import dist
from apex.render.ink_geometry import cubic_chain
from apex.scene.performance_upgrade import fuse_notice_travel,strict_events


def test_curves_interpolate_all_joints_and_bound_handles():
    p=[(0,0),(10,1),(7,8),(7,8),(0,12)]
    segments=cubic_chain(p)
    assert len(segments)==len(p)-1
    for i,(a,b,c,d) in enumerate(segments):
        assert a==p[i] and d==p[i+1]
        assert dist(a,b)<=.18*dist(a,d)+1e-9
        assert dist(c,d)<=.18*dist(a,d)+1e-9


def test_sharp_fold_has_no_loop_handles():
    left,right=cubic_chain([(0,0),(10,0),(0,0)])
    assert left[2]==left[3]==right[0]==right[1]


def test_matching_notice_fuses_without_changing_other_actors():
    a=[{'character':'a','type':'notice','target':'char:b'},
       {'character':'b','type':'wait_for','until':'event:notice@a'},
       {'character':'a','type':'run_to','target':'char:b','speed':350},
       {'character':'a','type':'pick_up','target':'prop:tool'}]
    out=fuse_notice_travel(a)
    assert out[0]==a[1] and out[2]==a[3]
    assert out[1]['notice_while_moving'] and len(a)==4
    assert 'notice_while_moving' not in a[2]


def test_different_target_and_intervening_action_are_not_fused():
    a=[{'character':'a','type':'notice','target':'prop:p'},
       {'character':'a','type':'act','clip':'shock'},
       {'character':'a','type':'run_to','target':'prop:p'}]
    assert fuse_notice_travel(a)==a
    b=[a[0],{'character':'a','type':'run_to','target':'char:b'}]
    assert fuse_notice_travel(b)==b


def test_goals_cannot_reuse_events_or_invert_causality():
    ev=[SimpleNamespace(t=2,type='grab'),SimpleNamespace(t=1,type='notice')]
    match=lambda goal,e: goal==e.type
    assert strict_events(['notice','grab'],ev,match)==([('notice',1.),('grab',2.)],None)
    assert strict_events(['grab','grab'],ev,match)[1]=='grab'
    assert strict_events(['grab','notice'],ev,match)[1]=='notice'
