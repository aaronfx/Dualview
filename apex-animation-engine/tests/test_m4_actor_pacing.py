"""M4 acceptance: run-to-grab continuity and bored-actor diagnostics."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from apex.qa.actor_pacing import audit_character
from apex.scene.runtime import SceneRuntime


def _scene(segments, records, duration=4.0):
    return SimpleNamespace(
        duration=duration,
        controllers={"iko": SimpleNamespace(segments=segments, records=records)})


def _seg(kind, a, b, data=None):
    return SimpleNamespace(kind=kind, t0=a, t1=b, data=data or {})


def _rec(t, x, y=80):
    return SimpleNamespace(t=t, pos=(x, y))


def test_detect_unmotivated_idle_but_not_intentional_acting():
    intervals = [_seg("idle", 0.0, 0.9),
                 _seg("idle", 0.9, 2.0, {"act": "cheer"}),
                 _seg("loco", 2.0, 4.0)]
    records = [_rec(2.0 + i * 0.05, i * 12.5) for i in range(41)]
    report = audit_character(_scene(intervals, records), "iko")
    assert not report.passed
    assert abs(report.wasted_seconds - 0.9) < 0.01
    assert report.deliberate_seconds >= 1.0
    assert report.windows[0].category == "unwarranted_idle"
    assert report.windows[1].category == "deliberate_performance"
    assert report.windows[1].counted is False


def test_stationary_moving_action_is_flagged_without_penalizing_foot_plants():
    intervals = [_seg("loco", 0.0, 2.0)]
    records = ([_rec(i * 0.05, 0) for i in range(14)]
               + [_rec(0.7 + i * 0.05, 20 * i) for i in range(27)])
    report = audit_character(_scene(intervals, records, duration=2), "iko", min_pause=0.40)
    assert any(w.category == "movement_stall" for w in report.windows)
    assert report.wasted_seconds >= 0.59


def test_short_preparations_are_not_mistaken_for_boredom():
    intervals = [_seg("idle", 0, 0.22), _seg("climb", 0.22, 1.65), _seg("idle", 1.65, 1.85, {"settle": True})]
    # Constant 0.18 s during a valid grab, then continuing vertical climb.
    records = [_rec(0.22 + i * 0.02, 0, 80 if i < 9 else 80 + (i-8)*4) for i in range(72)]
    r = audit_character(_scene(intervals, records, duration=1.85), "iko")
    assert r.passed, r.to_dict()
    assert r.wasted_seconds == 0


def test_active_climb_uses_real_ledge_event_and_reaches_goal_without_extra_walk():
    path = Path(__file__).resolve().parents[1] / "examples" / "build_impossible_crossing.py"
    spec = importlib.util.spec_from_file_location("m4_benchmark", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    film, plan = module.build()
    assert plan.chosen == "climb_then_drop"
    scene = film.scenes[0]
    climb_action = next(a for a in scene.actions if a.type == "climb")
    assert 1.0 < climb_action.tempo <= 1.35
    result = SceneRuntime(film, "cross").simulate(physics_only=True)
    events = [e for e in result.events if e.character == "iko"]
    climb = next(e for e in events if e.type == "climb_start")
    grab = next(e for e in events if e.type == "ledge_grab")
    top = next(e for e in events if e.type == "climbed")
    jump = next(e for e in events if e.type == "takeoff")
    pick = next(e for e in events if e.type == "pick_up" and e.data.get("prop") == "spark")
    assert climb.t < grab.t < top.t < jump.t < pick.t
    assert top.t - climb.t < 1.5
    assert jump.t - top.t < 0.45
    # One direct arrival at the planned grab coordinate, not another hidden
    # low-speed walk from a generic approximation of the obstacle's edge.
    climb_segment = next(s for s in result.controllers["iko"].segments if s.kind == "climb")
    assert abs(climb_segment.t0 - climb.t) < 0.025
    report = audit_character(result, "iko", min_pause=0.38, max_waste=0.65)
    assert report.passed, report.to_dict()
