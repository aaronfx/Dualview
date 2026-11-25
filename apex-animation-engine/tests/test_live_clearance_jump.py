"""Live-bound jump planning tests; native animation proof is a separate gate."""
from types import SimpleNamespace
from apex.scene.route_planner import check_jump, select_clearance_jump
from apex.scene.structures import Block

def _env():
    return SimpleNamespace(gravity=(0,-1568), room=SimpleNamespace(width=2200,height=800), obstacles=[])

def test_fallen_character_arc():
    body = Block("char:pell",-85,85,0,42)
    v = select_clearance_jump(_env(),(-180,0),(180,0),live_bounds=(body,))
    assert v.feasible
    assert all(y >= 42 for x,y in v.plan.samples if -110 < x < 110)

def test_immovable_object_arc():
    box = Block("prop:heavy",-45,45,0,95)
    assert select_clearance_jump(_env(),(-170,0),(170,0),live_bounds=(box,)).feasible

def test_impossible_barrier_and_occupied_landing():
    for b in (Block("tall",-45,45,0,500), Block("landing",150,205,0,60)):
        assert not select_clearance_jump(_env(),(-180,0),(180,0),live_bounds=(b,)).feasible

def test_bad_live_geometry_rejected():
    assert not check_jump(_env(),(-180,0),(180,0),horizontal_speed=300,
                          live_bounds=(Block("invalid",10,-10,0,50),)).feasible
