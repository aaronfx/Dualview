import math

from apex.core.mathx import damped_spring, lerp_angle, wrap_angle
from apex.core.timeline import Key, Track


def test_wrap_and_lerp_angle_shortest_arc():
    assert abs(wrap_angle(3 * math.pi) - math.pi) < 1e-9
    a = lerp_angle(math.radians(170), math.radians(-170), 0.5)
    assert abs(abs(wrap_angle(a)) - math.pi) < 1e-9  # goes through 180, not through 0


def test_damped_spring_converges_and_starts_at_initial_state():
    x0, v0 = damped_spring(10.0, -5.0, 0.0, 9.0, 0.5, 0.0)
    assert (x0, v0) == (10.0, -5.0)
    x, v = damped_spring(10.0, -5.0, 0.0, 9.0, 0.5, 3.0)
    assert abs(x) < 1e-3 and abs(v) < 1e-2


def test_track_eases_and_holds():
    tr = Track.of((0.0, 0.0, "linear"), (1.0, 10.0))
    assert tr(-1) == 0 and tr(0.5) == 5 and tr(2) == 10
