"""Director's Cut engine integration: story props, physical placement and film QA.

Run from apex-animation-engine with: PYTHONPATH=src pytest -q tests/test_directors_cut_engine.py
"""
import pytest

from apex.scene.schema import ProjectSpec, WorldPowerSpec
from apex.scene.runtime import SceneRuntime
from apex.qa.film import check_film
from apex.render.power import power_level_at
from apex.render.film import render_film


def _project(scenes, *, actors=("iko",), film_goals=()):
    return ProjectSpec.model_validate({
        "id": "continuity_probe",
        "title": "Continuity probe",
        "characters": [{"id": c, "name": c.upper()} for c in actors],
        "environments": [{
            "id": "lab",
            "room": {"width": 1200, "height": 700},
            "props": [{
                "id": "core", "kind": "glyph", "glyph": "0",
                "position": [28, 140], "size": [18, 18],
                "mass": 1.0, "weight": 3.0,
            }],
        }],
        "scenes": scenes,
        "film_goals": list(film_goals),
    })


def _scene(sid, owner_in, owner_out, actions, duration=2.0, restoration=None):
    s = {
        "id": sid, "environment": "lab", "duration": duration,
        "placements": [{"character": "iko", "x": 0}],
        "actions": actions,
        "shots": [{"id": f"shot_{sid}", "start": 0, "end": duration}],
        "story_props": [{"prop": "core", "owner_in": owner_in, "owner_out": owner_out}],
    }
    if restoration is not None:
        s["restoration"] = restoration
    return s


def _check(result, name):
    return next(c for c in result if c.name == name)


def test_carried_prop_starts_in_hands_and_is_physically_dropped():
    a = _scene("a", "iko", "iko", [{"character": "iko", "type": "idle", "duration": 0.5}], 1.0)
    b = _scene("b", "iko", "world", [
        {"character": "iko", "type": "idle", "duration": 0.3},
        {"character": "iko", "type": "drop_prop"},
    ], 1.5)
    proj = _project([a, b])
    res = SceneRuntime(proj, "b").simulate(physics_only=True)
    assert any(e.type == "carry_in" and e.data["prop"] == "core" for e in res.events)
    assert any(e.type == "prop_dropped" and e.data["prop"] == "core" for e in res.events)
    assert res.controllers["iko"].carrying is None
    assert _check(check_film(proj), "plot_prop_continuity").status == "PASS"


def test_film_rejects_unexplained_core_owner_jump():
    a = _scene("a", "world", "world", [{"character": "iko", "type": "idle", "duration": 0.6}], 1.0)
    b = _scene("b", "iko", "iko", [{"character": "iko", "type": "idle", "duration": 0.6}], 1.0)
    proj = _project([a, b])
    check = _check(check_film(proj), "plot_prop_continuity")
    assert check.status == "FAIL"
    assert "ownership jumps" in check.details


def test_world_power_responds_to_actual_events_only():
    from types import SimpleNamespace
    spec = WorldPowerSpec.model_validate({
        "initial": 0.2,
        "cues": [{"on": "core_restored@core", "level": 1.0, "fade": 1.0}],
    })
    event = SimpleNamespace(t=0.5, type="core_restored", character="core", data={"prop": "core"})
    assert power_level_at(spec, [], 3.0) == pytest.approx(0.2)
    assert power_level_at(spec, [event], 0.4) == pytest.approx(0.2)
    assert power_level_at(spec, [event], 1.0) == pytest.approx(0.6)
    assert power_level_at(spec, [event], 1.6) == pytest.approx(1.0)


def test_strict_film_refuses_to_run_without_qa(tmp_path):
    sc = _scene("a", "world", "world", [{"character": "iko", "type": "idle", "duration": 0.6}], 1.0)
    proj = _project([sc])
    with pytest.raises(ValueError, match="strict_qa requires QA"):
        render_film(proj, str(tmp_path / "should_not_exist.mp4"), qa=False, strict_qa=True)


def test_schema_rejects_illegal_place_target_and_unknown_prop_owner():
    a = _scene("a", "iko", "iko", [{"character": "iko", "type": "place_prop", "target": "char:iko"}])
    with pytest.raises(ValueError, match="place_prop.target"):
        _project([a])
    b = _scene("a", "ghost", "iko", [])
    with pytest.raises(ValueError, match="unknown story prop owner"):
        _project([b])


def test_narrative_goal_requires_a_simulated_event():
    a = _scene("a", "iko", "iko", [{"character": "iko", "type": "idle", "duration": 0.5}], 1.0)
    proj = _project([a], film_goals=[{"scene": "a", "event": "core_restored@core"}])
    assert _check(check_film(proj), "narrative_event_chain").status == "FAIL"
