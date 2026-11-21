"""Combat: strikes resolved in simulation (hit / blocked / whiff), reactions, physics-driven knockdowns, recovery."""
import json
import math

import pytest

from apex.scene.schema import ProjectSpec


def _fight(acts, duration=10.0, kai_x=-160.0, rho_x=40.0, strength=50000):
    return {
        "schema_version": "0.1", "id": "fight", "title": "Fight", "fps": 24, "seed": 4,
        "characters": [{"id": "kai", "name": "KAI", "strength": strength, "style": {"has_scarf": False}},
                       {"id": "rho", "name": "RHO", "style": {"has_scarf": False}}],
        "environments": [{"id": "dojo", "room": {"width": 1600, "height": 650}, "dust": 0}],
        "scenes": [{"id": "s", "environment": "dojo", "duration": duration,
                    "placements": [{"character": "kai", "x": kai_x, "facing": 1}, {"character": "rho", "x": rho_x, "facing": -1}],
                    "actions": acts,
                    "shots": [{"id": "w", "start": 0, "end": duration, "kind": "wide",
                               "camera": {"mode": "static", "center": [0, 200], "view_height": 760}}]}]}


def _run(acts, **kw):
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(ProjectSpec.model_validate(_fight(acts, **kw)), "s")
    rt.simulate()
    return rt


def _ev(rt, kind, who=None):
    return [e for e in rt.result.events if e.type == kind and (who is None or e.character == who)]


def test_strike_schema():
    from apex.scene.schema import ActionSpec
    with pytest.raises(ValueError):
        ActionSpec(type="strike", character="a", target="char:b")  # which move?
    with pytest.raises(ValueError):
        ActionSpec(type="strike", character="a", target="prop:x", move="jab")  # strikes target characters
    ActionSpec(type="dodge", character="a", dodge="duck")
    ActionSpec(type="wait_for", character="a", until="next:strike_start@b")


def test_outcomes_hit_block_duck_and_out_of_reach():
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "jab"},
               {"character": "kai", "type": "strike", "target": "char:rho", "move": "cross"},
               {"character": "kai", "type": "strike", "target": "char:rho", "move": "hook"},
               {"character": "rho", "type": "guard", "until": "next:blocked@kai"},              # blocks the jab
               {"character": "rho", "type": "wait_for", "until": "next:strike_start@kai"},
               {"character": "rho", "type": "dodge", "dodge": "duck"},                          # ducks the cross
               {"character": "rho", "type": "idle", "duration": 4}])                            # takes the hook
    out = [(e.type, e.data["move"]) for e in rt.result.events if e.type in ("hit", "blocked", "whiff")]
    assert out == [("blocked", "jab"), ("whiff", "cross"), ("hit", "hook")]
    assert _ev(rt, "block_hit", "rho") and _ev(rt, "evaded", "rho") and _ev(rt, "hurt", "rho")


def test_back_dodge_takes_the_target_out_of_reach():
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "front_kick"},
               {"character": "rho", "type": "wait_for", "until": "event:strike_start@kai"},
               {"character": "rho", "type": "dodge", "dodge": "back"}])
    assert [e.type for e in rt.result.events if e.type in ("hit", "whiff")] == ["whiff"]


def test_power_and_strength_choose_the_reaction():
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "jab", "power": 0.8},
               {"character": "kai", "type": "strike", "target": "char:rho", "move": "side_kick", "power": 1.3}])
    reactions = [e.data["reaction"] for e in _ev(rt, "hit", "kai")]
    assert reactions == ["flinch", "knockdown"]
    weak = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "side_kick", "power": 1.3}], strength=20000)
    assert _ev(weak, "hit", "kai")[0].data["reaction"] != "knockdown"  # a weaker fighter does not floor anyone with it


def test_knockdown_is_a_physics_fall_that_settles_and_gets_up():
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "side_kick", "power": 1.3},
               {"character": "rho", "type": "wait_for", "until": "event:knockdown@rho"},
               {"character": "rho", "type": "get_up"},
               {"character": "rho", "type": "guard", "duration": 1.0}], duration=9.0)
    kd, fall, settled, up = _ev(rt, "knockdown", "rho")[0], _ev(rt, "body_fall", "rho"), _ev(rt, "settled", "rho"), _ev(rt, "stood_up", "rho")
    assert fall and settled and up and kd.t < fall[0].t < settled[0].t < up[0].t
    c = rt.result.controllers["rho"]
    seg = next(s for s in c.segments if s.kind == "ragdoll")
    xs = [a[0] for _, a in seg.data["samples"]]
    assert xs[-1] - xs[0] > 40.0  # knocked back, away from the kicker (+x)
    assert settled[0].data["posture"] in ("prone", "supine")
    an = rt.result.animators["rho"]
    rig = rt.rigs["rho"]
    for t in (kd.t + 0.2, (fall[0].t + settled[0].t) / 2):  # the rig keeps its bone lengths during the fall
        j = rig.world_joints(an.pose_at(t))
        assert abs(math.dist(j["pelvis"], j["spine_mid"]) - rig.p.spine) < 1.0
        assert abs(math.dist(j["spine_mid"], j["neck_base"]) - rig.p.chest) < 1.0
        assert abs(math.dist(j["knee_n"], j["ankle_n"]) - rig.p.shin) < 1.0
        assert min(p[1] for p in j.values()) > -6.0  # nothing far below the floor


def test_knocked_down_fighter_gets_up_before_fighting_again():
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "sweep"},
               {"character": "kai", "type": "guard", "duration": 4},
               {"character": "rho", "type": "wait_for", "until": "event:knockdown@rho"},
               {"character": "rho", "type": "strike", "target": "char:kai", "move": "jab"}], duration=9.0)
    up, strike = _ev(rt, "stood_up", "rho"), _ev(rt, "strike_start", "rho")
    assert up and strike and up[0].t <= strike[0].t


def test_combat_scene_passes_qa():
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    rt = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "cross"},
               {"character": "kai", "type": "strike", "target": "char:rho", "move": "roundhouse", "power": 1.3},
               {"character": "kai", "type": "guard", "duration": 3},
               {"character": "rho", "type": "guard", "until": "next:blocked@kai"}], duration=7.0)
    rep = Inspector(rt, build_camera(rt, 16 / 9), 24).run(check_determinism=False)
    names = {c.name: c for c in rep.checks}
    assert names["strike_contact"].status == "PASS" and names["fighters_do_not_overlap"].status == "PASS"
    assert rep.passed, rep.summary()


def test_strike_distance_engages_from_further_out():
    near = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "jab"},
                 {"character": "rho", "type": "guard", "duration": 3}], duration=3.0)
    far = _run([{"character": "kai", "type": "strike", "target": "char:rho", "move": "jab", "distance": 116},
                {"character": "rho", "type": "guard", "duration": 3}], duration=3.0)
    gap = lambda rt: min(abs(a.s - b.s) for a, b in zip(rt.result.controllers["kai"].records, rt.result.controllers["rho"].records))
    assert gap(far) > gap(near) + 6.0
    assert _ev(far, "blocked") and not _ev(far, "whiff")  # still within reach: the guard stops it
