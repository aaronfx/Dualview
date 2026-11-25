"""Semantic transposition and native signed-term geometry contracts."""
import pytest
from apex.scene import glyphs
from apex.scene.math_transposition import plan_additive_transposition
from apex.scene.transposition_stage import compile_transposition_stage


def equation(op, n, c):
    return {"op": "eq", "args": [
        {"op": op, "args": [{"op": "var", "value": "x"}, {"op": "int", "value": n}]},
        {"op": "int", "value": c}]}


@pytest.mark.parametrize("op,n,c,source,destination,answer", [
    ("add", 2, 5, "+2", "-2", 3),
    ("add", 4, 9, "+4", "-4", 5),
    ("sub", 4, 9, "-4", "+4", 13),
    ("add", 12, 5, "+12", "-12", -7),
    ("sub", 12, -5, "-12", "+12", 7),
    ("add", 0, 5, "+0", "-0", 5),
])
def test_proved_intermediate(op, n, c, source, destination, answer):
    plan = plan_additive_transposition(equation(op, n, c))
    assert plan.source.text == source
    assert plan.destination.text == destination
    assert plan.source.id == plan.destination.id
    assert (plan.source.side, plan.destination.side) == ("left", "right")
    assert plan.source.value == -plan.destination.value
    assert plan.transfer_proof.valid and plan.evaluation_proof.valid
    assert plan.intermediate.args[1].op == ("sub" if op == "add" else "add")
    assert plan.intermediate.args[1].args[0].value == c
    assert plan.intermediate.args[1].args[1].value == n
    assert plan.result == answer == plan.solved.args[1].value


def test_reject_unsupported_equation():
    with pytest.raises(ValueError):
        plan_additive_transposition(equation("mul", 2, 5))
    with pytest.raises(ValueError):
        plan_additive_transposition(equation("add", -2, 5))


def test_one_native_prop_for_complete_signed_term():
    stage = compile_transposition_stage(equation("add", 12, 20))
    assert [p.glyph for p in stage.props] == ["x", "+12", "=", "20"]
    prop = next(p for p in stage.props if p.id == stage.term_id)
    assert prop.size[0] == 3 * 54
    assert stage.destination[0] > stage.props[-1].position[0]
    assert glyphs.canonical("-12") == "-12"
    assert len(glyphs.segments(prop.glyph, prop.size)) > len(glyphs.segments("+", (54, 86)))


def test_inverse_morph_preserves_digit_geometry():
    size = (108, 86)
    original = glyphs.strokes("+2", size)[2:]
    for u in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert glyphs.blend("+2", "-2", u, size)[-len(original):] == original
    assert glyphs.strokes("-2", size)[1:] == original
    assert glyphs.blend("+2", "-2", 1.0, size) == glyphs.strokes("-2", size)


def test_invalid_compound_glyphs():
    for bad in ("++2", "2x", "1+2+3", "1234567"):
        with pytest.raises(ValueError):
            glyphs.canonical(bad)


@pytest.mark.parametrize("n,c,op", [(2, 5, "add"), (4, 9, "add"), (4, 9, "sub")])
def test_native_transfer_and_intermediate_frame(n, c, op):
    import runpy
    from pathlib import Path
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    build = runpy.run_path(str(Path(__file__).parents[1] / "examples/build_semantic_transposition.py"))["project"]
    p = ProjectSpec.model_validate(build(n, c, op))
    runtime = SceneRuntime(p, "solve")
    res = runtime.simulate()
    events = res.events
    first = lambda typ: next(e for e in events if e.type == typ)
    picked, crossed, placed, evaluated = (first(x) for x in
                                            ("pick_up", "math_crossed", "math_transferred", "math_evaluate"))
    assert picked.t < crossed.t < placed.t < evaluated.t
    assert evaluated.t - placed.t >= 1.0
    assert not [e for e in events if e.type == "throw"]
    assert not [c.violation for c in res.controllers.values() if c.violation]
    plan = plan_additive_transposition(equation(op, n, c))
    middle = runtime.evaluate((placed.t + evaluated.t) / 2)
    glyphs_by_id = {p.id: p for p in middle.props}
    assert glyphs_by_id["transpose_term"].glyph == plan.destination.text
    assert glyphs_by_id["transpose_rhs"].glyph == str(c)
    assert glyphs_by_id["transpose_term"].pos[0] > glyphs_by_id["transpose_rhs"].pos[0]
    assert "transpose_evaluation" not in glyphs_by_id
    last = {p.id: p for p in runtime.evaluate(13.5).props}
    assert set(last) == {"transpose_variable", "transpose_equals", "transpose_evaluation"}
    assert last["transpose_evaluation"].glyph.split(":")[1] == str(plan.result)
