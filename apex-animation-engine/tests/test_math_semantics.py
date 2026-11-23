import pytest
from apex.scene.math_semantics import Term, validate_beat, verify_rewrite


def I(v): return {"op": "int", "value": v}
def V(v): return {"op": "var", "value": v}
def E(op, a, b): return {"op": op, "args": [a, b]}


def test_arithmetic_rewrite_is_verified():
    assert verify_rewrite(E("add", I(2), I(3)), I(5)).valid
    assert not verify_rewrite(E("add", I(2), I(3)), I(6)).valid


def test_symbolic_algebra_rewrite_is_verified():
    assert verify_rewrite(E("add", V("x"), V("x")), E("mul", I(2), V("x"))).valid
    assert not verify_rewrite(E("pow", V("x"), I(2)), V("x")).valid


def test_equation_solution_sets_not_just_matching_text():
    eq1 = E("eq", E("add", V("x"), I(2)), I(5))
    eq2 = E("eq", V("x"), I(3))
    eq_wrong = E("eq", V("x"), I(4))
    assert verify_rewrite(eq1, eq2).valid
    assert not verify_rewrite(eq1, eq_wrong).valid
    assert not verify_rewrite(E("eq", E("pow", V("x"), I(2)), I(4)), E("eq", V("x"), I(2))).valid


def test_rejects_executable_or_unbounded_payloads():
    for data in ({"op": "var", "value": "__import__"},
                 {"op": "int", "value": 10**40},
                 E("div", V("x"), V("x")),
                 E("pow", V("x"), I(500))):
        with pytest.raises(ValueError): Term.parse(data)
    with pytest.raises(ValueError): Term.parse({"op": "int", "value": 2, "attack": "bad"})
    deep = I(1)
    for _ in range(20): deep = E("add", deep, I(1))
    with pytest.raises(ValueError): Term.parse(deep)


def test_physical_actions_do_not_claim_mathematical_equivalence():
    assert validate_beat({"kind": "physical", "action": "throw", "target": "plus"}).kind == "physical"
    with pytest.raises(ValueError): validate_beat({"kind": "physical", "action": "run_python"})


def test_no_equation_expression_type_confusion():
    result = verify_rewrite(E("eq", V("x"), I(3)), V("x"))
    assert not result.valid and result.kind == "type_mismatch"
