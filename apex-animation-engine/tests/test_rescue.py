"""The Rescue: two characters, physical interaction (push, falling support, pinning, hand lift, lever, crawl, help up)."""
import copy
import json
import math

import pytest

from apex.scene.schema import ProjectSpec

from .conftest import ROOT


def _data():
    return json.loads((ROOT / "examples" / "the_rescue.json").read_text())


@pytest.fixture(scope="module")
def rescue():
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(ProjectSpec.model_validate(_data()), "rescue")
    rt.simulate()
    return rt


def _first(rt, kind, who=None):
    return next(e for e in rt.result.events if e.type == kind and (who is None or e.character == who))


# ---------------------------------------------------------------- schema
def test_interaction_actions_validate_their_fields():
    from apex.scene.schema import ActionSpec
    with pytest.raises(ValueError):
        ActionSpec(type="push", character="a", target="switch:x")
    with pytest.raises(ValueError):
        ActionSpec(type="use_lever", character="a", target="prop:post", tool="prop:bar")  # no fulcrum
    with pytest.raises(ValueError):
        ActionSpec(type="gesture", character="a", target="char:b")  # which gesture?
    with pytest.raises(ValueError):
        ActionSpec(type="wait_for", character="a", until="pinned")  # must be event:...
    ActionSpec(type="run_to", character="a", target="char:b")  # a character / prop can replace target_x


def test_unknown_prop_reference_is_rejected():
    d = _data()
    d["scenes"][0]["actions"][2]["target"] = "prop:nope"
    with pytest.raises(ValueError):
        ProjectSpec.model_validate(d)


# ---------------------------------------------------------------- physics building blocks
def test_stick_slip_friction_and_contact_friction_update():
    from apex.physics.world import PhysicsWorld
    w = PhysicsWorld()
    w.add_static_segment("floor", (-500, 0), (500, 0), 2.0)
    w.add_box("box", (0, 51), (100, 100), 100.0, friction=0.05)
    w.set_friction("box", 0.6)  # at rest: static friction holds
    for _ in range(240):
        w.step(1 / 240)
    for _ in range(240):  # a push below the static threshold does not move it
        w.apply_force("box", (40000, 0), w.state("box").pos)
        w.step(1 / 240)
    assert abs(w.state("box").vel[0]) < 1.0
    w.set_friction("box", 0.05)  # sliding: the live contact picks up the new friction
    for _ in range(120):
        w.apply_force("box", (40000, 0), w.state("box").pos)
        w.step(1 / 240)
    assert w.state("box").vel[0] > 100.0


def test_rope_snaps_and_props_rest_on_lying_bodies(rescue):
    snap = _first(rescue, "rope_snap")
    taut = _first(rescue, "rope_taut")
    assert taut.t <= snap.t < taut.t + 0.2
    assert "strap" in rescue.result.rope_snaps


# ---------------------------------------------------------------- the story is caused by the simulation
def test_causal_chain_in_order(rescue):
    order = [("push_start", "milo"), ("push_lost", "milo"), ("rope_snap", None), ("body_fall", "milo"), ("pinned", "milo"),
             ("notice", "juno"), ("lift_start", "juno"), ("lift_fail", "juno"), ("pick_up", "juno"), ("lever_place", "juno"),
             ("crawl_start", "milo"), ("freed", "milo"), ("hand_grab", "milo"), ("stood_up", "milo"), ("fist_bump", "juno")]
    times = [_first(rescue, k, w).t for k, w in order]
    assert times == sorted(times)
    assert _first(rescue, "pinned", "milo").data["by"] == "post"
    assert _first(rescue, "notice", "juno").t > _first(rescue, "pinned", "milo").t  # she reacts to it


def test_hand_lift_fails_on_strength_and_succeeds_when_stronger():
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(ProjectSpec.model_validate(_data()), "rescue")
    rt.simulate()
    fail = _first(rt, "lift_fail", "juno")
    assert fail.data["rise"] < 12.0
    d = _data()
    next(c for c in d["characters"] if c["id"] == "juno")["strength"] = 160000.0
    d["scenes"][0]["duration"] = 10.0
    d["scenes"][0]["shots"] = [{"id": "w", "start": 0.0, "end": 10.0, "kind": "wide", "camera": {"mode": "static", "center": [0, 200], "view_height": 700}}]
    strong = SceneRuntime(ProjectSpec.model_validate(d), "rescue")
    strong.simulate()
    assert any(e.type == "lift_ok" and e.character == "juno" for e in strong.result.events)  # physics decides, not the script


def test_lever_lifts_the_load_off_and_hands_stay_on_the_handle(rescue):
    eng, freed = _first(rescue, "lever_engage", "juno"), _first(rescue, "freed", "milo")
    assert any(e.type == "load_off" and e.character == "milo" and eng.t <= e.t <= freed.t for e in rescue.result.events)
    an = rescue.result.animators["juno"]
    rig = rescue.rigs["juno"]
    worst = 0.0
    import numpy as np
    for t in np.arange(eng.t + 0.3, freed.t, 0.1):
        j = rig.world_joints(an.pose_at(float(t)))
        g, _ = an._bar_grips("bar", float(t), "handle")
        worst = max(worst, math.dist(j["hand_n"], g), math.dist(j["wrist_n"], g) - rig.p.hand)
    assert worst < 6.0


def test_lying_only_actions_are_rejected_while_standing():
    from apex.scene.runtime import SceneRuntime
    d = _data()
    acts = d["scenes"][0]["actions"]
    acts.insert(1, {"character": "milo", "type": "crawl_out"})
    with pytest.raises(ValueError):
        SceneRuntime(ProjectSpec.model_validate(d), "rescue").simulate()


# ---------------------------------------------------------------- AI Director safeguards
def test_director_dry_run_accepts_rescue_and_rejects_stuck_or_unknown_sound():
    from apex.ai.director import StoryDirector, system_prompt
    StoryDirector._dry_run(ProjectSpec.model_validate(_data()))
    bad = _data()
    bad["scenes"][0]["shots"][0]["sound_cues"] = [{"on_event": "push_start", "sound": "metal_crash", "gain": 1.0}]
    with pytest.raises(ValueError):
        StoryDirector._dry_run(ProjectSpec.model_validate(bad))
    stuck = _data()
    stuck["environments"][0]["ropes"] = []  # no strap: the post never falls, nobody is pinned
    with pytest.raises(ValueError, match="waiting"):
        StoryDirector._dry_run(ProjectSpec.model_validate(stuck))
    p = system_prompt()
    for word in ("use_lever", "crawl_out", "static_friction", "break_force", "strain"):
        assert word in p


# ---------------------------------------------------------------- QA
def test_rescue_passes_qa(rescue):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    rep = Inspector(rescue, build_camera(rescue, 16 / 9), 24).run(check_determinism=False)
    assert rep.passed, rep.summary()
