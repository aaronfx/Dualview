"""The balance capability: a character physically solves a proven equation (x + 2 = 5 -> x = 3).

Three guarantees:
1. a false rewrite is refused before any object is built (SymPy proof gate);
2. a true rewrite yields a physical plan (which terms to remove, which to morph) over the real glyph ids;
3. the authored film actually performs it in simulation — both terms are thrown off and the constant morphs, in order.
"""
import json
import os

import pytest

from apex.scene.math_stage import BalancePlan, plan_balance
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def I(v):
    return {"op": "int", "value": v}


def V(v):
    return {"op": "var", "value": v}


def E(op, a, b):
    return {"op": op, "args": [a, b]}


BEFORE = E("eq", E("add", V("x"), I(2)), I(5))   # x + 2 = 5
AFTER = E("eq", V("x"), I(3))                     # x = 3


def test_false_rewrite_is_refused_before_building():
    with pytest.raises(ValueError):
        plan_balance(BEFORE, E("eq", V("x"), I(4)), center=(0, 48))   # x + 2 = 5 -> x = 4 is false


def test_true_rewrite_gives_a_physical_plan():
    pl = plan_balance(BEFORE, AFTER, center=(0, 48))
    assert isinstance(pl, BalancePlan) and pl.proof.valid
    # before tokens: x(00) +(01) 2(02) =(03) 5(04); the + and 2 are removed, the 5 morphs to 3
    assert pl.remove == ("eqn_before_01", "eqn_before_02")
    assert pl.morph == (("eqn_before_04", "3"),)


def test_balance_never_spawns_a_new_symbol():
    # 2 = 2  ->  2 = 1 + 1 would need to add symbols on the right; a physical balance cannot spawn them
    with pytest.raises((NotImplementedError, ValueError)):
        plan_balance(E("eq", I(2), I(2)), E("eq", I(2), E("add", I(1), I(1))), center=(0, 48))


def test_authored_film_performs_the_proven_balance():
    """The committed builder renders a film in which the proven transformation really happens in physics."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    import importlib.util
    spec = importlib.util.spec_from_file_location("bbe", os.path.join(here, "examples", "build_balance_equation.py"))
    bbe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bbe)
    p = ProjectSpec.model_validate(bbe.project())
    rt = SceneRuntime(p, "solve")
    res = rt.simulate()
    throws = [e.data["prop"] for e in res.events if e.type == "throw"]
    morphs = [(e.data["prop"], e.data["to"]) for e in res.events if e.type == "morph"]
    assert "eqn_before_01" in throws and "eqn_before_02" in throws, throws   # + and 2 removed
    assert ("eqn_before_04", "3") in morphs, morphs                           # 5 -> 3
    # the morph happens after both removals (cause before effect)
    t_two = next(e.t for e in res.events if e.type == "throw" and e.data["prop"] == "eqn_before_02")
    t_morph = next(e.t for e in res.events if e.type == "morph" and e.data["prop"] == "eqn_before_04")
    assert t_morph >= t_two
    assert not [c.violation for c in res.controllers.values() if c.violation]
