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


# ---- other characters in the path: native body collision, no pass-through ----------------------------------------
def _two_char_scene(iko_x, pell_x, iko_target, pell_actions):
    def _actor(cid, color):
        return {"id": cid, "name": cid.upper(), "strength": 52000,
                "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
                "style": {"visual_profile": "apex_ink", "performance_profile": "continuous", "body_color": color,
                          "far_color": "#888", "glow_color": color, "has_scarf": False, "limb_width": 8.0}}
    return {"schema_version": "0.1", "id": "blk", "title": "Blocked", "fps": 24, "width": 1280, "height": 720,
            "seed": 7, "characters": [_actor("iko", "#ffd04e"), _actor("pell", "#59d6ed")],
            "environments": [{"id": "e", "room": {"width": 2200, "height": 800, "depth_back": 400,
                              "entry_door": False, "grid_spacing": 160, "grid_alpha": 0.1, "style": "open"},
                              "gravity": [0, -1568], "dust": 8,
                              "obstacles": [{"id": "ground", "kind": "platform", "style": "girder",
                                             "color": "#3b4b57", "center": [0, -32], "size": [2200, 64]}], "props": []}],
            "scenes": [{"id": "s", "title": "s", "environment": "e", "duration": 6.0,
                        "placements": [{"character": "iko", "x": iko_x, "facing": 1, "z": 0},
                                       {"character": "pell", "x": pell_x, "facing": -1, "z": 0}],
                        "actions": [{"character": "iko", "type": "run_to", "target_x": iko_target, "speed": 360}]
                                   + pell_actions, "goals": [],
                        "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
                        "shots": [{"id": "w", "kind": "wide", "start": 0, "end": 6.0,
                                   "camera": {"mode": "static", "center": [0, 200], "view_height": 700}}]}]}


def _min_same_lane_gap(sim):
    ri, rp = sim.controllers["iko"].records, sim.controllers["pell"].records
    n = min(len(ri), len(rp))
    return min(abs(ri[i].pos[0] - rp[i].pos[0]) for i in range(n)
              if abs(ri[i].pos[1] - rp[i].pos[1]) < 120)


def test_stationary_blocking_character_is_not_passed_through():
    """A character standing in the runner's path (same depth lane) blocks it — the runner stops at the body gap and
    never passes through (native body collision, body_block event)."""
    p = ProjectSpec.model_validate(_two_char_scene(-500, 100, 600, []))
    sim = SceneRuntime(p, "s").simulate()
    assert _min_same_lane_gap(sim) >= 24.0, "runner interpenetrated the blocking character"
    assert any(e.type == "body_block" for e in sim.events), "no body_block when path was blocked"


def test_converging_moving_characters_do_not_interpenetrate():
    """Two moving characters converging in the same lane never occupy the same screen position (no pass-through)."""
    p = ProjectSpec.model_validate(_two_char_scene(-500, 500, 400, [
        {"character": "pell", "type": "run_to", "target_x": -400, "speed": 360}]))
    sim = SceneRuntime(p, "s").simulate()
    assert _min_same_lane_gap(sim) >= 24.0, "two moving characters interpenetrated"
