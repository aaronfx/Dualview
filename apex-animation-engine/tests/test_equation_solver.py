"""The generalisable linear-equation solver: correct solutions, verified balance-preserving steps, no hardcoding."""
from fractions import Fraction

import pytest

from apex.scene.equation_solver import Equation, solve_plan

CASES = [
    ((1, 2, 5), 3, ["subtract 2 from both sides"]),
    ((1, 4, 9), 5, ["subtract 4 from both sides"]),
    ((2, 0, 8), 4, ["divide both sides by 2"]),
    ((2, 3, 11), 4, ["subtract 3 from both sides", "divide both sides by 2"]),
    ((1, -3, 4), 7, ["add 3 to both sides"]),
]


@pytest.mark.parametrize("coeffs,sol,descs", CASES)
def test_solves_and_isolates_x(coeffs, sol, descs):
    steps, s = solve_plan(*coeffs)
    assert s == sol
    assert [st.description for st in steps] == descs
    # the final step leaves x = sol (a == 1, b == 0)
    last = steps[-1].after
    assert last.a == 1 and last.b == 0 and last.c == sol


@pytest.mark.parametrize("coeffs,sol,_d", CASES)
def test_every_step_preserves_the_solution(coeffs, sol, _d):
    steps, _ = solve_plan(*coeffs)
    for st in steps:
        assert st.before.solution == st.after.solution == sol   # exact arithmetic
        # and the two sides stay equal in value (the balance stays level)
        assert st.before.lhs_value == st.before.c
        assert st.after.lhs_value == st.after.c


def test_both_sides_change_together_each_step():
    # 2x+3=11: step 1 subtracts 3 from BOTH sides (b and c both drop by 3); step 2 divides BOTH by 2
    steps, _ = solve_plan(2, 3, 11)
    s1 = steps[0]
    assert s1.before.b - s1.after.b == 3 and s1.before.c - s1.after.c == 3   # same amount off both sides
    s2 = steps[1]
    assert s2.before.a / s2.after.a == 2 and s2.before.c / s2.after.c == 2   # same divisor on both sides


def test_false_or_unsupported_is_refused():
    with pytest.raises(ValueError):
        Equation(0, 1, 2)                       # not linear in x
    with pytest.raises(ValueError):
        solve_plan(Fraction(1, 2), 0, 1)        # non-integer coefficient is not renderable as glyphs
