"""Presentation QA (issue 8) — reproduce the reported artistic defects as failing fixtures and prove the detectors
catch them, and that the corrected autonomous film passes. These checks never relax physical validation; they add
failing signals for staging/story defects a zero-violation run can still contain."""
import pytest

from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.qa.presentation_audit import (check_ground_consistency, check_character_overlap, check_inactivity,
                                        check_narrative_payoff, presentation_audit)

GROUND = {"id": "ground", "kind": "platform", "center": [0, -32], "size": [3000, 64], "style": "girder"}
CORE = {"id": "core", "kind": "glyph", "glyph": "8", "position": [200, 60], "size": [70, 90], "mass": 2, "solid": True}


def _proj(obstacles, placements, actions, chars=("iko",), dur=12.0, style="open", exits=None):
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "p", "title": "p", "fps": 24, "width": 1280, "height": 720, "seed": 1,
        "characters": [{"id": c, "name": c.upper()} for c in chars],
        "environments": [{"id": "e", "room": {"width": 3200, "height": 900, "entry_door": False, "style": style},
                          "props": [CORE], "obstacles": obstacles, "exits": exits or []}],
        "scenes": [{"id": "s", "environment": "e", "duration": dur, "placements": placements, "actions": actions,
                    "goals": [], "shots": [{"id": "sh", "start": 0, "end": dur,
                                            "camera": {"mode": "follow", "target": "iko", "view_height": 700}}]}]})


def _rt(p):
    rt = SceneRuntime(p, "s")
    return rt, rt.simulate()


# ---- issue 1: invisible ground -------------------------------------------------------------------------------
def test_ground_defect_open_room_with_no_platform_fails():
    p = _proj([], [{"character": "iko", "x": -400, "facing": 1}],
              [{"character": "iko", "type": "walk_to", "target_x": 900}])   # open room, no drawn ground
    assert check_ground_consistency(*_rt(p))["status"] == "FAIL"


def test_ground_fixed_full_span_platform_passes():
    p = _proj([GROUND], [{"character": "iko", "x": -400, "facing": 1}],
              [{"character": "iko", "type": "walk_to", "target_x": 900}])
    assert check_ground_consistency(*_rt(p))["status"] == "PASS"


def test_ground_closed_room_draws_its_floor():
    p = _proj([], [{"character": "iko", "x": -400, "facing": 1}],
              [{"character": "iko", "type": "walk_to", "target_x": 900}], style="box")
    assert check_ground_consistency(*_rt(p))["status"] == "PASS"


# ---- issue 2: visible character overlap ----------------------------------------------------------------------
def test_overlap_defect_same_screen_position_fails():
    # two bodies at the same screen x = silhouette penetration, whatever their depth lane
    p = _proj([GROUND], [{"character": "iko", "x": -100, "z": 0}, {"character": "pell", "x": -100, "z": 10}],
              [], chars=("iko", "pell"))
    assert check_character_overlap(*_rt(p))["status"] == "FAIL"


def test_overlap_depth_offset_is_not_credited():
    # a deep depth lane does NOT excuse occupying the same screen x — the hiding this regression relied on
    p = _proj([GROUND], [{"character": "iko", "x": -100, "z": 0}, {"character": "pell", "x": -100, "z": 60}],
              [], chars=("iko", "pell"))
    assert check_character_overlap(*_rt(p))["status"] == "FAIL"


def test_overlap_fixed_spatial_separation_passes():
    # genuinely separated in screen x (native same-lane body collision keeps characters apart) -> no penetration
    p = _proj([GROUND], [{"character": "iko", "x": -300, "z": 0}, {"character": "pell", "x": 300, "z": 0}],
              [], chars=("iko", "pell"))
    assert check_character_overlap(*_rt(p))["status"] == "PASS"


# ---- issue 3: excessive inactivity ---------------------------------------------------------------------------
def test_inactivity_defect_idle_partner_fails():
    p = _proj([GROUND], [{"character": "iko", "x": -400, "z": 0}, {"character": "pell", "x": 400, "z": 60}],
              [{"character": "iko", "type": "walk_to", "target_x": 600},
               {"character": "pell", "type": "idle", "duration": 10.0}], chars=("iko", "pell"), dur=12.0)
    assert check_inactivity(*_rt(p))["status"] == "FAIL"


def test_inactivity_fixed_active_partner_passes():
    # both characters perform meaningful beats throughout (no span over the 6s threshold)
    beats = lambda c: [{"character": c, "type": "act", "clip": k, "duration": 1.4}
                       for k in ("beckon", "peer_down", "reach_out", "cheer")]
    p = _proj([GROUND], [{"character": "iko", "x": -200, "z": 0}, {"character": "pell", "x": 300, "z": 60}],
              beats("iko") + beats("pell"), chars=("iko", "pell"), dur=6.5)
    assert check_inactivity(*_rt(p))["status"] == "PASS"


# ---- issue 7: narrative payoff -------------------------------------------------------------------------------
def test_payoff_defect_ends_on_movement_only_fails():
    p = _proj([GROUND], [{"character": "iko", "x": -400, "facing": 1}],
              [{"character": "iko", "type": "walk_to", "target_x": 900}], dur=6.0)
    assert check_narrative_payoff(*_rt(p))["status"] == "FAIL"


def test_payoff_fixed_closing_reaction_passes():
    p = _proj([GROUND], [{"character": "iko", "x": -200, "facing": 1}],
              [{"character": "iko", "type": "walk_to", "target_x": 150},
               {"character": "iko", "type": "act", "clip": "cheer", "emotion": "joyful", "duration": 1.3}], dur=6.0)
    assert check_narrative_payoff(*_rt(p))["status"] == "PASS"


# ---- corrected autonomous film passes the whole audit --------------------------------------------------------
def test_corrected_autonomous_film_passes_presentation_audit():
    from apex.ai.autonomous_film import film_from_brief
    raw, _ = film_from_brief("A lone courier scales a barrier, recovers the power core and escapes through the airlock.")
    p = ProjectSpec.model_validate(raw)
    rt = SceneRuntime(p, "film")
    sim = rt.simulate()
    assert not [c.violation for c in sim.controllers.values() if c.violation]   # physical validation intact
    assert all(c["status"] == "PASS" for c in presentation_audit(rt, sim))
