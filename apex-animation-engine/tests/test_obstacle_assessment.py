"""Universal obstacle assessment + movement selection.

The autonomous pipeline must ADAPT its movement to unfamiliar obstacle geometry, not have the geometry reshaped to
suit one tactic. These tests hold the obstacle dimensions FIXED (notably the hard 80-unit-wide pillars) and assert
that the engine, through the native autochoreo tactic search plus full-plan graze validation and dynamic
re-selection, independently chooses a tactic that clears every obstacle with NO structural penetration and NO
uncontrolled contact (graze), recovers the goal, and — when a crossing is physically impossible — STOPS honestly
rather than walking through.

The decisive defects these guard against (all were real on the 80-wide course):
  * a grazing hurdle accepted as a clearance (the airborne collision impulse that surfaced as a gravity_direction
    spike) — rejected now, because a graze is an uncontrolled body-vs-structure collision, not a clean clear;
  * a planted foot hanging past a too-narrow platform top (feet_on_tops) — avoided, because the engine climbs a
    tall narrow pillar instead of standing on it;
  * surface penetration during the crossing — guarded by the full technical gate below.
"""
import pytest

from apex.ai.obstacle_course import plan_course
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.goals import matches
from apex.qa.inspector import Inspector
from apex.render.pipeline import build_camera


def _run(obstacles, start_x, apex, width=3600.0):
    scene, report = plan_course(obstacles, start_x=start_x, width=width, max_jump_apex=apex)
    p = ProjectSpec.model_validate(scene)
    rt = SceneRuntime(p, "s")
    sim = rt.simulate()
    ins = Inspector(rt, build_camera(rt, p.width / p.height), p.fps, size=(p.width, p.height))
    ins.times = [i / p.fps for i in range(int(sim.duration * p.fps))]
    checks = {c.name: c for c in ins.run(check_determinism=False).checks}
    return scene, report, sim, checks


def _assert_clean_traversal(obstacles, start_x, apex):
    scene, report, sim, checks = _run(obstacles, start_x, apex)
    # native movement safety: no controller violation, and the whole technical gate holds (no penetration, no
    # teleporting joint, no bad landing, no graze concealed behind camera/offset tricks)
    assert not [c.violation for c in sim.controllers.values() if c.violation], "controller violation"
    assert not [e for e in sim.events if e.type == "graze"], "uncontrolled graze (not a clean clearance)"
    fails = [n for n, c in checks.items() if c.status == "FAIL"]
    assert not fails, f"technical QA failures: {fails}"
    # the actor really traversed (takeoffs/climbs) and recovered the core
    assert sum(1 for e in sim.events if e.type in ("takeoff", "climbed")) >= len(obstacles)
    assert any(matches("pick_up@iko[prop=core]", e) for e in sim.events), "core not recovered"
    return report


# ---- the preserved hard fixture: 80-unit-wide pillars of varied height -------------------------------------------
FIXTURES_80W = [
    ("three_tall_pillars", [{"id": "r1", "center": [-200, 65], "size": [80, 130]},
                            {"id": "r2", "center": [260, 100], "size": [80, 200]},
                            {"id": "r3", "center": [720, 80], "size": [80, 160]}], -660, 250.0),
    ("low_then_tall", [{"id": "r1", "center": [-120, 55], "size": [80, 110]},
                       {"id": "r2", "center": [420, 110], "size": [80, 220]}], -520, 300.0),
    ("four_mixed_heights", [{"id": "r1", "center": [-260, 75], "size": [80, 150]},
                            {"id": "r2", "center": [120, 60], "size": [80, 120]},
                            {"id": "r3", "center": [520, 95], "size": [80, 190]},
                            {"id": "r4", "center": [980, 70], "size": [80, 140]}], -700, 270.0),
]


@pytest.mark.parametrize("name,obstacles,start_x,apex", FIXTURES_80W)
def test_80wide_fixture_is_cleared_by_adaptation(name, obstacles, start_x, apex):
    """The 80-wide course is fixed; the engine must ADAPT (climb the tall/narrow pillars it cannot hurdle cleanly)
    and clear the whole course with no penetration and no graze."""
    report = _assert_clean_traversal(obstacles, start_x, apex)
    assert all(s["tactic"] for s in report["segments"])  # a native tactic was selected for every obstacle


# ---- the assessment picks the tactic that fits the geometry ------------------------------------------------------
def test_low_narrow_barrier_is_hurdled():
    report = _assert_clean_traversal([{"id": "o", "center": [0, 36], "size": [70, 72]}], -520, 260.0)
    assert "jump" in report["segments"][0]["tactic"]            # low enough to clear in flight


def test_tall_narrow_pillar_is_climbed():
    report = _assert_clean_traversal([{"id": "o", "center": [0, 130], "size": [80, 260]}], -560, 260.0)
    assert "climb" in report["segments"][0]["tactic"]          # too tall/narrow to hurdle without grazing


def test_tall_pillar_switches_from_graze_jump_to_climb():
    """Directly guards the reported defect: a pillar the engine would otherwise hurdle into (grazing it) is instead
    climbed, so no uncontrolled airborne contact occurs."""
    report = _assert_clean_traversal([{"id": "r2", "center": [420, 110], "size": [80, 220]}], -300, 300.0)
    assert "climb" in report["segments"][0]["tactic"]


# ---- honest stop when the crossing is physically impossible ------------------------------------------------------
def test_impossible_wall_stops_rather_than_passing_through():
    """A wall far too tall to climb or hurdle must raise (the Director stops / must reroute) — never a walk-through."""
    with pytest.raises(ValueError):
        plan_course([{"id": "w", "center": [0, 250], "size": [80, 500]}], start_x=-560, width=3200, max_jump_apex=300.0)
