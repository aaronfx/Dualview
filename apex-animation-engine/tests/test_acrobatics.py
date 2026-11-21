"""Milestone 2: structures you can stand on, acrobatics, and symbols as physical objects."""
import math

import pytest

from apex.scene import glyphs
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

PLAT = {"id": "p1", "kind": "platform", "center": [-150, 90], "size": [260, 180]}
MINUS = {"id": "m1", "kind": "glyph", "glyph": "-", "center": [-480, 30], "size": [110, 40], "weight": 34}


def proj(acts, obstacles=(), props=(), dur=8.0, chars=("kai",), placements=None):
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360, "seed": 3,
        "characters": [{"id": c, "name": c.upper(), "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42}}
                       for c in chars],
        "environments": [{"id": "e", "room": {"width": 1800, "height": 900, "entry_door": False}, "obstacles": list(obstacles),
                          "props": list(props), "dust": 0}],
        "scenes": [{"id": "s", "environment": "e", "duration": dur,
                    "placements": placements or [{"character": "kai", "x": -700, "facing": 1}], "actions": acts,
                    "shots": [{"id": "a", "start": 0, "end": dur, "camera": {"mode": "follow", "target": "kai", "view_height": 600}}]}]})


def sim(p, strict=True):
    return SceneRuntime(p, "s", strict=strict).simulate(physics_only=True)


def first(r, etype, who="kai"):
    return next((e for e in r.events if e.type == etype and e.character == who), None)


def test_glyph_geometry():
    for g in glyphs.GLYPHS:
        segs = glyphs.segments(g, (100, 140))
        assert segs, g
        (cx, cy), masses = glyphs.mass_props(g, (100, 140), 14, 6.0)
        assert abs(sum(masses) - 6.0) < 1e-9 and abs(cx) < 60 and abs(cy) < 80
    assert len(glyphs.flat_tops("-", (120, 30), 30)) == 1
    assert len(glyphs.flat_tops("=", (120, 60), 16)) == 2
    top = glyphs.flat_tops("7", (200, 300), 30)  # the top bar of a 7 is standable
    assert len(top) == 1 and abs(top[0][2] - (150 + 15)) < 1e-6
    assert glyphs.canonical("×") == "x" and glyphs.canonical("−") == "-"
    with pytest.raises(ValueError):
        glyphs.canonical("@")


def test_walking_into_a_structure_is_an_error():
    with pytest.raises(ValueError, match="runs into structure 'p1'"):
        sim(proj([{"character": "kai", "type": "walk_to", "target_x": 0}], [PLAT]))


def test_jump_onto_a_platform_then_walk_off_the_end():
    r = sim(proj([{"character": "kai", "type": "walk_to", "target_x": -340},
                  {"character": "kai", "type": "jump_to", "target_x": -200, "height": 230, "onto": "obstacle:p1"},
                  {"character": "kai", "type": "walk_to", "target_x": 60}], [PLAT], dur=7))
    land = first(r, "impact")
    assert land.data["surface"] == "p1"
    off = first(r, "step_off")
    assert off is not None and off.data["surface"] == "p1" and off.t > land.t
    floor = next(e for e in r.events if e.type == "impact" and e.t > off.t)
    assert floor.data["surface"] == "floor"
    c = r.controllers["kai"]
    assert c.frame.tag == "floor" and abs(c.s - 60) < 1.0


def test_jump_too_low_for_the_rise_is_rejected():
    with pytest.raises(ValueError, match="cannot clear"):
        sim(proj([{"character": "kai", "type": "walk_to", "target_x": -340},
                  {"character": "kai", "type": "jump_to", "target_x": -200, "height": 120, "onto": "obstacle:p1"}], [PLAT]))


def test_vault_climb_flip_and_landing_roll():
    acts = [{"character": "kai", "type": "vault", "target": "obstacle:m1"},
            {"character": "kai", "type": "climb", "target": "obstacle:p1"},
            {"character": "kai", "type": "walk_to", "target_x": -60},
            {"character": "kai", "type": "jump_to", "target_x": 200, "height": 90, "flip": "front"},
            {"character": "kai", "type": "roll"}]
    r = sim(proj(acts, [PLAT, MINUS], dur=9))
    order = ["vault", "ledge_grab", "climbed", "flip", "roll_start", "roll_end"]
    ts = [first(r, k).t for k in order]
    assert ts == sorted(ts)
    assert first(r, "climbed").data["surface"] == "p1"
    land = next(e for e in r.events if e.type == "impact" and e.t > first(r, "flip").t)
    assert abs(land.t - first(r, "roll_start").t) < 1e-6  # the roll starts at touchdown
    c = r.controllers["kai"]
    rec = min(c.records, key=lambda x: abs(x.t - land.t))
    assert abs(math.atan2(math.sin(rec.angle), math.cos(rec.angle))) < 0.45  # came round to upright
    t_flip = first(r, "flip").t
    flight = [x.angle for x in c.records if t_flip <= x.t < land.t]
    assert flight[-1] - flight[0] < -5.0  # a front flip facing +x rotates clockwise (about -2 pi)


def test_vault_too_high_is_rejected():
    tall = {"id": "tall", "kind": "platform", "center": [-480, 60], "size": [110, 120]}
    with pytest.raises(ValueError, match="too high to vault"):
        sim(proj([{"character": "kai", "type": "vault", "target": "obstacle:tall"}], [tall]))


def test_wall_kick_back_flip():
    r = sim(proj([{"character": "kai", "type": "wall_kick", "target_x": 420, "flip": "back", "height": 80}], dur=6,
                 placements=[{"character": "kai", "x": 400, "facing": 1}]))
    assert len([e for e in r.events if e.type == "wall_contact"]) == 2
    kick = first(r, "wall_kick")
    land = next(e for e in r.events if e.type == "impact" and e.t > kick.t)
    assert land.data["surface"] == "floor"
    assert abs(r.controllers["kai"].s - 420) < 60


def _throw(rho_acts):
    props = [{"id": "plus", "kind": "glyph", "glyph": "+", "position": [-300, 30], "size": [56, 56], "mass": 6}]
    acts = [{"character": "kai", "type": "pick_up", "target": "prop:plus"},
            {"character": "kai", "type": "walk_to", "target_x": -150},
            {"character": "kai", "type": "throw", "target": "char:rho"}] + rho_acts
    return sim(proj(acts, (), props, dur=7, chars=("kai", "rho"),
                    placements=[{"character": "kai", "x": -500, "facing": 1}, {"character": "rho", "x": 300, "facing": -1}]))


def test_thrown_glyph_hits_or_is_blocked():
    r = _throw([{"character": "rho", "type": "idle", "duration": 6}])
    hit = first(r, "hit")
    assert hit is not None and hit.data["prop"] == "plus" and first(r, "hurt", "rho") is not None
    r = _throw([{"character": "rho", "type": "guard", "duration": 6}])
    assert first(r, "blocked") is not None and first(r, "block_hit", "rho") is not None and first(r, "hurt", "rho") is None


def test_weapon_swing_needs_a_carried_prop():
    two = dict(chars=("kai", "rho"), placements=[{"character": "kai", "x": -400, "facing": 1}, {"character": "rho", "x": 0, "facing": -1}])
    with pytest.raises(ValueError, match="carried prop"):
        sim(proj([{"character": "kai", "type": "strike", "target": "char:rho", "move": "swing_weapon"}], dur=4, **two))
    props = [{"id": "bar", "kind": "glyph", "glyph": "-", "position": [-300, 10], "size": [110, 20], "mass": 5, "weight": 14}]
    r = sim(proj([{"character": "kai", "type": "pick_up", "target": "prop:bar"},
                  {"character": "kai", "type": "strike", "target": "char:rho", "move": "swing_weapon"}], (), props, dur=6, **two))
    assert first(r, "hit").data["move"] == "swing_weapon"


def test_flying_kick_hits_and_can_be_stepped_out_of():
    two = dict(chars=("kai", "rho"), placements=[{"character": "kai", "x": -300, "facing": 1}, {"character": "rho", "x": 0, "facing": -1}])
    r = sim(proj([{"character": "kai", "type": "strike", "target": "char:rho", "move": "flying_kick"}], dur=4, **two))
    assert first(r, "hit") is not None
    r = sim(proj([{"character": "kai", "type": "strike", "target": "char:rho", "move": "flying_kick"},
                  {"character": "rho", "type": "wait_for", "until": "next:strike_start@kai"},
                  {"character": "rho", "type": "dodge", "dodge": "back"}], dur=4, **two))
    assert first(r, "whiff") is not None and first(r, "hit") is None
