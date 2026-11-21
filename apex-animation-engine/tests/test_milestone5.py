"""Milestone 5: breakables, morphs, the diagram layer, composite creatures, set dressing and continuity."""
import math

import pytest

from apex.scene import glyphs
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def proj(props=(), acts=(), dur=3.0, extra_env=None, scene_extra=None, placements=None):
    env = {"id": "e", "room": {"width": 1700, "height": 900, "entry_door": False}, "dust": 0, "props": list(props)}
    env.update(extra_env or {})
    sc = {"id": "s", "environment": "e", "duration": dur, "placements": placements or [{"character": "kai", "x": -700}],
          "actions": list(acts), "shots": [{"id": "a", "start": 0, "end": dur, "camera": {"mode": "static", "center": [0, 300]}}]}
    sc.update(scene_extra or {})
    return ProjectSpec.model_validate({"schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360,
                                       "seed": 3, "characters": [{"id": "kai", "name": "KAI"}], "environments": [env], "scenes": [sc]})


def qa(p):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    rt = SceneRuntime(p, "s")
    res = rt.simulate()
    rep = Inspector(rt, build_camera(rt, p.width / p.height), p.fps).run(check_determinism=False)
    return rt, res, {c.name: c for c in rep.checks}


# ---------------------------------------------------------------- breakables
def test_glyph_pieces_cover_the_glyph():
    for g in ("+", "0", "8", "π"):
        pcs = glyphs.pieces(g)
        assert sum(len(p) - 1 for p in pcs) == sum(len(st) - 1 for st in glyphs.GLYPHS[g])
        assert glyphs.canonical(f"{g}#{len(pcs) - 1}")
    with pytest.raises(ValueError):
        glyphs.canonical("+#5")


def test_props_break_only_at_their_threshold_and_keep_their_momentum():
    hard = dict(kind="glyph", glyph="8", size=[60, 80], mass=4, angle=0.3, z=40, depth=20, breakable={"impulse": 2500})
    rt, res, ch = qa(proj([dict(hard, id="high", position=[0, 600]), dict(hard, id="low", position=[300, 150]),
                           {"id": "box", "kind": "crate", "position": [-300, 600], "size": [60, 60], "mass": 8, "z": 40, "depth": 20,
                            "breakable": {"impulse": 5000}}]))
    broke = {e.character for e in res.events if e.type == "break"}
    assert broke == {"high", "box"}  # the gentle drop does not break
    for name in ("breaks_at_threshold", "breaks_conserve_momentum", "breaks_continuous"):
        assert ch[name].status == "PASS", ch[name].details
    assert not res.alive("high", 2.9) and res.alive("high~0", 2.9) and res.alive("low", 2.9)
    shown = {p.id for p in rt.evaluate(2.9).props}
    assert "high" not in shown and "high~3" in shown and "box~0" in shown


# ---------------------------------------------------------------- morphs
def test_a_morph_conserves_motion_clears_the_floor_and_does_not_pop():
    rt, res, ch = qa(proj([{"id": "g", "kind": "glyph", "glyph": "-", "position": [0, 200], "size": [80, 80], "mass": 4, "z": 40,
                            "depth": 20, "angle": 0.2, "morphs": [{"to": "+", "at": 0.4, "duration": 0.5},
                                                                  {"to": "8", "at": 1.6, "duration": 0.5}]}]))
    m = res.morphs["g"]
    assert [x["to"] for x in m] == ["+", "8"] and all(x["t_swap"] for x in m)
    assert m[0]["nudge"][1] > 0  # the plus's vertical stroke would have been in the floor: it pushed itself up
    for name in ("morphs_conserve_motion", "morphs_hold_centre", "morphs_no_pop"):
        assert ch[name].status == "PASS", ch[name].details
    fs = rt.evaluate(0.65)
    assert next(p for p in fs.props if p.id == "g").morph is not None  # visibly blending


def test_a_morph_waits_while_a_character_is_in_the_way():
    p = proj([{"id": "g", "kind": "glyph", "glyph": "-", "position": [-640, 60], "size": [120, 120], "mass": 4, "z": 0, "depth": 20,
               "collide_characters": True, "morphs": [{"to": "+", "at": 0.2, "duration": 0.2}]}],
             acts=[{"character": "kai", "type": "idle", "duration": 1.0}, {"character": "kai", "type": "walk_to", "target_x": -350}],
             placements=[{"character": "kai", "x": -640}])
    res = SceneRuntime(p, "s", strict=False).simulate(physics_only=True)
    ev = [e.type for e in res.events if e.type.startswith("morph")]
    assert "morph_blocked" in ev and ev.index("morph_blocked") < ev.index("morph")
    swap = next(e for e in res.events if e.type == "morph")
    assert swap.t > 1.0  # it changed shape only once the character had walked away


# ---------------------------------------------------------------- diagrams
def test_every_number_on_screen_is_rederived_from_the_simulation():
    rows = ["          ", "          ", "          o     *         ", "          ", "          ", "          ",
            "1     ^         ######    "]
    p = ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360, "seed": 3,
        "characters": [{"id": "kai", "name": "KAI"}],
        "environments": [{"id": "e", "room": {"width": 1700, "height": 900, "entry_door": False}, "dust": 0,
                          "level": {"cell": 60, "origin": [-780, 0], "rows": rows}}],
        "scenes": [{"id": "s", "environment": "e", "duration": 6, "placements": [{"character": "kai", "at": "1"}],
                    "actions": [{"character": "kai", "type": "run_to", "target_x": 400}],
                    "diagrams": [{"id": "v", "kind": "velocity", "target": "char:kai", "t0": 0.3, "t1": 4.0},
                                 {"id": "dv", "kind": "impulse", "target": "char:kai", "t0": 0, "t1": 6, "duration": 0.8},
                                 {"id": "m", "kind": "measure", "target": "char:kai", "to": "point:0,0", "t0": 1, "t1": 3}],
                    "shots": [{"id": "a", "start": 0, "end": 6, "camera": {"mode": "follow", "target": "kai"}}]}]})
    rt, res, ch = qa(p)
    assert ch["diagrams_truthful"].status == "PASS", ch["diagrams_truthful"].details
    from apex.render.diagrams import Diagrams
    prims = Diagrams(rt).at(1.2)
    assert {x.src for x in prims} >= {"v", "dv", "m"}
    dv = next(x for x in prims if x.src == "dv")
    assert dv.text.startswith("Δv") and dv.value > 500  # the jump orb's velocity change, from its event


# ---------------------------------------------------------------- creatures
BUG = {"id": "bug", "body": "0", "size": [70, 46], "position": [-200, 95], "mass": 5, "z": 40,
       "parts": [{"glyph": "!", "size": [14, 52], "at": [-20, -14], "role": "leg", "phase": 0},
                 {"glyph": "!", "size": [14, 52], "at": [20, -14], "role": "leg", "phase": 3.14159},
                 {"glyph": "0", "size": [12, 12], "at": [22, 8], "role": "eye", "mass": 0.2}],
       "breaks": 3000}


def test_a_creature_walks_its_path_in_one_piece():
    cr = dict(BUG, path=[[0.5, -200], [3.5, 250]])
    rt, res, ch = qa(proj(dur=4.5, extra_env={"creatures": [cr]}))
    assert abs(res.prop_tracks["bug.body"][-1, 0] - 250) < 15
    assert ch["creature_joints_hold"].status == "PASS" and ch["creature_follows_path"].status == "PASS"
    legs = [res.prop_tracks[f"bug.{k}"][int(2.0 * 240), 2] - res.prop_tracks["bug.body"][int(2.0 * 240), 2] for k in (0, 1)]
    assert legs[0] * legs[1] < 0  # walking: the legs swing in turn
    assert not [e for e in res.events if e.type == "creature_break"]


def test_a_hard_blow_tears_a_creature_apart():
    cr = dict(BUG, path=[[1.5, -200], [4.5, 250]])
    rock = {"id": "rock", "kind": "glyph", "glyph": "x", "position": [-195, 700], "size": [50, 50], "mass": 6, "z": 40, "depth": 20}
    rt, res, ch = qa(proj([rock], dur=3.0, extra_env={"creatures": [cr]}))
    brk = [e for e in res.events if e.type == "creature_break"]
    assert len(brk) == 1 and brk[0].data["impulse"] >= 3000
    assert ch["creature_breaks_at_threshold"].status == "PASS"
    assert all(res.prop_tracks[t][-1, 1] < 60 for t in ("bug.0", "bug.1", "bug.2"))  # the parts fell to the floor


# ---------------------------------------------------------------- presentation
def test_set_dressing_is_drawn_and_never_collides():
    deco = [{"kind": k, "x": 0, "y": 200} for k in ("window", "panel", "screen", "pipe", "lamp", "shelf")] + \
           [{"kind": "bench", "x": 0, "z": 100}]
    p = proj(extra_env={"decor": deco, "room": {"width": 1700, "height": 900, "entry_door": False, "grid_alpha": 0.3}},
             acts=[{"character": "kai", "type": "walk_to", "target_x": 300}], dur=9.0)
    res = SceneRuntime(p, "s").simulate(physics_only=True)
    assert abs(res.controllers["kai"].s - 300) < 2  # walked straight through the bench's depth: it is scenery
    from apex.render.skia_renderer import SkiaRenderer
    rt = SceneRuntime(p, "s")
    rt.simulate()
    from apex.camera.director import CameraState
    r = SkiaRenderer(320, 180, rt.env, {"kai": p.characters[0].style}, rt.rigs)
    img = r.render(rt.evaluate(1.0), CameraState(0, 300, 900, 0, "a"))
    assert img.shape == (180, 320, 4) and img[..., :3].std() > 5


def test_key_events_happen_on_screen():
    import json
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    for f in ("specimen", "orb_runner"):
        p = ProjectSpec.model_validate(json.load(open(f"examples/{f}.json")))
        rt = SceneRuntime(p, p.scenes[0].id)
        res = rt.simulate()
        ins = Inspector(rt, build_camera(rt, p.width / p.height), p.fps, size=(p.width, p.height))
        ins.times = [i / p.fps for i in range(int(res.duration * p.fps))]
        c = ins.check_causes_on_screen()[0]
        assert c.status == "PASS", (f, c.details)
