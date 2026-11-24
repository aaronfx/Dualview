import math

import pytest

from apex.physics.gravity import GravityField, GravityTransition
from apex.physics.world import PhysicsWorld, capsule_moment


def test_gravity_transition_rotates_vector_and_labels_states():
    g = GravityField((0, -1000))
    g.schedule(GravityTransition(1.0, 0.2, (1000, 0)))
    assert g.at(0.5) == (0, -1000) and g.state_label(0.5) == "G0"
    mid = g.at(1.1)
    assert abs(math.hypot(*mid) - 1000) < 1e-6 and mid[0] > 0 and mid[1] < 0
    assert g.at(2.0) == (1000, 0) and g.state_label(2.0) == "G1"
    with pytest.raises(ValueError):
        g.schedule(GravityTransition(1.1, 0.5, (0, 1000)))


def test_dynamic_body_accelerates_along_configured_gravity_and_reports_contact():
    w = PhysicsWorld((900.0, 0.0))
    w.add_static_segment("wall", (300, -500), (300, 500))
    w.add_capsule("c", (0, 0), (0, -40), (0, 40), 8, 70, kinematic=False)
    w.set_dynamic("c", (0, 0), 0, 70, capsule_moment(70, 80, 8))
    events = []
    for _ in range(240):
        events += w.step(1 / 240)
    st = w.state("c")
    assert abs(st.pos[1]) < 1e-6  # no vertical drift: gravity is purely +x
    hit = [e for e in events if e.a == "c" and e.b == "wall"]
    assert hit, "collision event expected"
    assert hit[0].normal[0] < -0.99 and hit[0].normal_speed > 300


def test_kinematic_body_ignores_gravity():
    w = PhysicsWorld((0, -1500))
    w.add_capsule("c", (0, 100), (0, -40), (0, 40), 8, 70, kinematic=True)
    for _ in range(100):
        w.step(1 / 240)
    assert w.state("c").pos == (0, 100)
