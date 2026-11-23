"""Route preflight checks real APEX obstacle bounds; simulation remains final authority."""
import pytest

from apex.scene.route_planner import check_jump
from apex.scene.schema import EnvironmentSpec


def env(**changes):
    obj = {"id": "test", "room": {"width": 1200, "height": 900, "entry_door": False},
           "gravity": [0, -1568], "dust": 0}
    obj.update(changes)
    return EnvironmentSpec.model_validate(obj)


def test_short_gap_reachable_with_clear_ceiling():
    r = check_jump(env(), (-150, 0), (150, 0), horizontal_speed=600, max_rise=150)
    assert r.feasible, r.reason
    assert r.plan.duration == pytest.approx(0.5)
    assert r.plan.vertical_speed == pytest.approx(392)
    assert r.plan.apex_y == pytest.approx(49)
    assert r.plan.samples[0] == pytest.approx((-150, 0))
    assert r.plan.samples[-1] == pytest.approx((150, 0))


def test_impossible_wide_gap_exceeds_physical_apex_budget():
    r = check_jump(env(), (-350, 0), (350, 0), horizontal_speed=350, max_rise=150)
    assert not r.feasible and "exceeds" in r.reason


def test_obstacle_is_derived_from_real_project_geometry():
    e = env(obstacles=[{"id": "tower", "kind": "platform", "center": [0, 120], "size": [90, 240]}])
    r = check_jump(e, (-150, 0), (150, 0), horizontal_speed=600, max_rise=150)
    assert not r.feasible and "tower" in r.reason


def test_room_ceiling_and_boundaries_cannot_be_ignored():
    small = env(room={"width": 700, "height": 200, "entry_door": False})
    r = check_jump(small, (-150, 0), (150, 0), horizontal_speed=600)
    assert not r.feasible and "ceiling" in r.reason
    r2 = check_jump(env(), (-590, 0), (590, 0), horizontal_speed=600, max_rise=2000,
                    max_launch_speed=2500)
    assert not r2.feasible


def test_rotated_gravity_must_use_full_physics_not_fake_arc():
    r = check_jump(env(gravity=[1568, 0]), (-150, 0), (150, 0), horizontal_speed=600)
    assert not r.feasible and "gravity" in r.reason


def test_wrong_facing_speed_is_rejected():
    assert not check_jump(env(), (-150, 0), (150, 0), horizontal_speed=-600).feasible
    assert not check_jump(env(), (-150, 0), (150, 0), horizontal_speed=0).feasible
