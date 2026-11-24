"""The autonomous equation film generalises from the solver and teaches by TRANSPOSITION: each term glides across the
`=` (a real engine `transpose` move) and its operation inverts, so `x + 2 = 5` becomes `x = 5 - 2 = 3`. Every compute is
caused by that crossing, never by a timer. No per-equation hardcoding: the same builder stages all five benchmarks."""
import importlib.util
import os

import pytest

from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("bef", os.path.join(HERE, "examples", "build_equation_film.py"))
bef = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bef)

CASES = [(1, 2, 5, 3), (1, 4, 9, 5), (2, 0, 8, 4), (2, 3, 11, 4), (1, -3, 4, 7)]

# compute morphs land on a digit (the new right-hand value); flip morphs land on an operator as the term crosses.
_DIGITS = set("0123456789")


def _digit_morphs(res):
    return [e.data["to"] for e in res.events if e.type == "morph" and e.data["to"] in _DIGITS]


def _flip_morphs(res):
    return [e.data["to"] for e in res.events if e.type == "morph" and e.data["to"] not in _DIGITS]


@pytest.mark.parametrize("a,b,c,sol", CASES)
def test_film_solves_and_every_compute_is_caused_by_a_crossing(a, b, c, sol):
    p = ProjectSpec.model_validate(bef.project(a, b, c))
    res = SceneRuntime(p, "solve").simulate()
    transposes = [e for e in res.events if e.type == "transpose_start"]
    digit_morphs = [e for e in res.events if e.type == "morph" and e.data["to"] in _DIGITS]
    assert transposes and digit_morphs
    # the right side ends at the solution (last computed digit)
    assert digit_morphs[-1].data["to"] == str(sol)
    # causality: no term is computed before a term has crossed the = (a real engine transpose, not a timer)
    first_cross = min(e.t for e in transposes)
    assert all(m.t >= first_cross for m in digit_morphs)
    # every crossing operator inverts to a valid algebra sign
    assert set(_flip_morphs(res)) <= {"+", "-", "x", "÷"}
    # the film runs clean: no engine violation, nothing left unexecuted
    assert not [c_.violation for c_ in res.controllers.values() if c_.violation]
    assert not sorted({ac.type for c_ in res.controllers.values() for ac in c_.queue})


def test_plus_crosses_as_minus():
    # x + 2 = 5: the + must invert to - as it crosses (transposition, not discarding) before 5 computes to 3.
    p = ProjectSpec.model_validate(bef.project(1, 2, 5))
    res = SceneRuntime(p, "solve").simulate()
    assert "-" in _flip_morphs(res)          # the operator inverted on crossing
    assert _digit_morphs(res) == ["3"]        # 5 - 2 computed to 3


def test_coefficient_crosses_as_division():
    # 2x = 8: the multiply must invert to ÷ as the 2 crosses, giving x = 8 ÷ 2 = 4.
    p = ProjectSpec.model_validate(bef.project(2, 0, 8))
    res = SceneRuntime(p, "solve").simulate()
    assert "÷" in _flip_morphs(res)
    assert _digit_morphs(res) == ["4"]


def test_two_step_shows_the_intermediate():
    # 2x+3=11 -> 2x=8 -> x=4: the right side must pass through 8 before 4 (the intermediate equation is shown).
    p = ProjectSpec.model_validate(bef.project(2, 3, 11))
    res = SceneRuntime(p, "solve").simulate()
    assert _digit_morphs(res) == ["8", "4"]


def test_not_hardcoded_other_equation():
    # an equation not in the brief still generates and solves (proves generalisation).
    # NOTE: single-digit right-hand sides through each step are fully supported; a right side that stays multi-digit
    # across more than one step (e.g. 14 -> 12 -> 4) is a known follow-up, not needed by the five benchmark equations.
    p = ProjectSpec.model_validate(bef.project(2, 1, 7))   # 2x + 1 = 7 -> 2x = 6 -> x = 3
    res = SceneRuntime(p, "solve").simulate()
    assert _digit_morphs(res) == ["6", "3"]
    assert not [c_.violation for c_ in res.controllers.values() if c_.violation]
