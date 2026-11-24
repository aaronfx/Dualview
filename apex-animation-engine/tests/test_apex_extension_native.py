"""Native integration tests for the APEX Studio & EDU Foundation V2 extension.

The extension kit ships isolated modules; these tests prove each one's bridge against the *native* APEX engine, so a
capability can be marked verified with evidence. Pure-interface behaviour (planning search, acting curves, quality
checks, the capability gate) is also exercised here. Nothing re-implements engine behaviour — the bridges point at it.
"""
import json
import os

import pytest

from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene import structures

from apex_extension import world as ext_world
from apex_extension import math_world, planning, character, acting, quality, rig
from apex_extension.product_sdk import Capability, require
from apex_extension.registry import registry, VERIFIED, UNVERIFIED

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_example(fname, func="project"):
    import importlib.util
    spec = importlib.util.spec_from_file_location("ex", os.path.join(HERE, "examples", fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func)


def I(v):
    return {"op": "int", "value": v}


def V(v):
    return {"op": "var", "value": v}


def E(op, a, b):
    return {"op": op, "args": [a, b]}


# --------------------------------------------------------------------------- math_world <-> native math_stage
def test_math_world_matches_native():
    # the extension's exact rational arithmetic agrees with the native SymPy-proven transform
    eq = math_world.LinearEquation(1, 2, 5)              # 1*x + 2 = 5
    assert eq.solution == 3
    assert eq.subtract(2).solution == 3                 # balancing keeps the solution set
    sb, sa, proof = math_world.native_pair(E("eq", E("add", V("x"), I(2)), I(5)), E("eq", V("x"), I(3)), center=(0, 48))
    assert proof.valid and len(sb.glyphs) == 5 and len(sa.glyphs) == 3
    with pytest.raises(ValueError):                     # a false transform is refused natively
        math_world.native_pair(E("eq", E("add", V("x"), I(2)), I(5)), E("eq", V("x"), I(4)))


def test_fixed_glyph_morphs_upright_natively():
    # evidence for the fixed_glyph_morph capability: the balance scene's fixed 5 morphs to 3 and stays upright
    import math
    p = ProjectSpec.model_validate(_load_example("build_balance_equation.py")())
    res = SceneRuntime(p, "solve").simulate()
    morphs = [e.data["to"] for e in res.events if e.type == "morph"]
    assert "3" in morphs
    ang = res.prop_tracks["eqn_before_04"][-1][2]
    assert math.isfinite(ang) and abs(math.degrees(ang)) < 8     # upright, not tipped


# --------------------------------------------------------------------------- world.from_project <-> native structures
def test_world_from_project_matches_native():
    p = ProjectSpec.model_validate(_load_example("build_impossible_crossing.py", "world")())
    objs = ext_world.from_project(p, p.scenes[0].id)
    assert objs
    env = p.environment(p.scenes[0].environment)
    by_id = {o.id: o for o in objs}
    for ob in env.obstacles:
        l, r, b, t = structures.obstacle_bounds(env, ob.id)
        o = by_id[ob.id]
        assert o.x == pytest.approx((l + r) / 2) and o.y == pytest.approx((b + t) / 2)
        assert o.width == pytest.approx(r - l) and o.height == pytest.approx(t - b)
    # perception + affordances are deterministic and bounded
    near = ext_world.perceive(objs, 0, 0, 2000)
    assert near and ext_world.affordances(objs)


# --------------------------------------------------------------------------- character.native_brain <-> CharacterBrain
def test_character_brain_native():
    from apex.ai.character_brain import Personality, Perception, Intent
    brain = character.native_brain(Personality(curiosity=0.9))
    # appearance-independent: decisions come from perception + recorded outcomes, never visuals
    brain.record_outcome("spark", Intent.APPROACH, succeeded=False)
    brain.record_outcome("spark", Intent.APPROACH, succeeded=False)
    assert brain.failed_attempts[("spark", Intent.APPROACH)] == 2
    # the kit's affect/experience are also appearance-independent helpers
    aff = character.Affect()
    v, a = aff.update(reward=1.0, threat=0.0, dt=0.5)
    assert v > 0 and 0 <= a <= 1
    exp = character.Experience()
    exp.record("spark", "climb", True)
    assert exp.confidence("spark", "climb") > 0.5


def test_rig_is_appearance_independent():
    # the same semantic angles retarget onto different rigs (stick vs illustrated joint names) -> intelligence is
    # decoupled from appearance
    stick = rig.Rig((rig.Joint("root", None, (0, 0)), rig.Joint("arm", "root", (0, 10))),
                    {"shoulder": "arm"})
    toon = rig.Rig((rig.Joint("hips", None, (0, 0)), rig.Joint("upper_arm_L", "hips", (0, 12))),
                   {"shoulder": "upper_arm_L"})
    angles = {"shoulder": 0.5}
    assert stick.retarget(angles) == {"arm": 0.5}
    assert toon.retarget(angles) == {"upper_arm_L": 0.5}


# --------------------------------------------------------------------------- planning / acting / quality (interfaces)
def test_planning_symbolic_and_native_available():
    a = planning.Action("grab", frozenset({"near"}), frozenset({"held"}))
    b = planning.Action("approach", frozenset(), frozenset({"near"}))
    assert planning.plan({"start"}, {"held"}, [a, b]) == ("approach", "grab")
    assert callable(planning.native_search)   # native autochoreo.search bridge is importable


def test_acting_curve_has_anticipation_and_settle():
    curve = acting.performance_curve(1.0)
    vals = [v for _, v in curve]
    assert min(vals) < 0 and max(vals) >= 0.99 and abs(vals[-1]) < 0.05   # anticipation dip, full extent, settle


def test_quality_flags_teleport():
    good = quality.track_checks([(0, 0, 0), (0.1, 10, 0)], max_speed=200)
    bad = quality.track_checks([(0, 0, 0), (0.1, 1000, 0)], max_speed=200)
    assert not good and any(f.code == "speed" for f in bad)


# --------------------------------------------------------------------------- capability registry / gate
def test_registry_verified_entries_carry_evidence():
    be = registry()
    verified = [c for c in be.capabilities() if c.verified]
    assert verified and all(c.evidence for c in verified)              # product_sdk enforces this too
    names = {c.name for c in verified}
    require(be, {"autonomous_choreography", "math_equation_transform", "fixed_glyph_morph"})   # passes
    with pytest.raises(ValueError):
        require(be, {"dialogue_srt"})                                  # unverified -> gated out
    assert {c.name for c in UNVERIFIED}.isdisjoint(names)


def test_capability_requires_evidence():
    with pytest.raises(ValueError):
        Capability("x", verified=True)                                 # verified without evidence is refused
