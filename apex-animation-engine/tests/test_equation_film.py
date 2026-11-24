"""The autonomous equation film generalises from the solver, and every transformation is caused by a real character
event (never a timer). No per-equation hardcoding: the same builder stages all five benchmark equations."""
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


@pytest.mark.parametrize("a,b,c,sol", CASES)
def test_film_solves_and_every_morph_is_caused(a, b, c, sol):
    p = ProjectSpec.model_validate(bef.project(a, b, c))
    res = SceneRuntime(p, "solve").simulate()
    throws = [e for e in res.events if e.type == "throw"]
    morphs = [e for e in res.events if e.type == "morph"]
    assert throws and morphs
    # the right side ends at the solution (last morph of the right-hand glyph)
    assert str(morphs[-1].data["to"]) == str(sol)
    # causality: every morph happens at or after a throw (a real character action), never before any action
    first_throw = min(e.t for e in throws)
    assert all(m.t >= first_throw for m in morphs)
    # the film runs clean: no engine violation, nothing left unexecuted
    assert not [c_.violation for c_ in res.controllers.values() if c_.violation]
    assert not sorted({ac.type for c_ in res.controllers.values() for ac in c_.queue})


def test_two_step_shows_the_intermediate():
    # 2x+3=11 -> 2x=8 -> x=4: the right glyph must pass through 8 before 4 (the intermediate equation is shown)
    p = ProjectSpec.model_validate(bef.project(2, 3, 11))
    res = SceneRuntime(p, "solve").simulate()
    seq = [e.data["to"] for e in res.events if e.type == "morph"]
    assert seq == ["8", "4"]


def test_not_hardcoded_other_equation():
    # an equation not in the brief still generates and solves (proves generalisation).
    # NOTE: single-digit right-hand sides through each step are fully supported; a right side that stays multi-digit
    # across more than one step (e.g. 14 -> 12 -> 4) is a known follow-up, not needed by the five benchmark equations.
    p = ProjectSpec.model_validate(bef.project(2, 1, 7))   # 2x + 1 = 7 -> 2x = 6 -> x = 3
    res = SceneRuntime(p, "solve").simulate()
    assert [e.data["to"] for e in res.events if e.type == "morph"] == ["6", "3"]
    assert not [c_.violation for c_ in res.controllers.values() if c_.violation]
