"""Physical math-stage tests: glyphs are real APEX obstacles or rigid-body props."""
import pytest
from apex.scene import glyphs
from apex.scene.math_stage import compile_math_stage, compile_proven_math_pair
from apex.scene.schema import ObstacleSpec, PropSpec


def I(v): return {"op": "int", "value": v}
def V(v): return {"op": "var", "value": v}
def E(op, a, b): return {"op": op, "args": [a, b]}


def test_equation_builds_real_standable_and_dynamic_glyph_objects():
    raw = E("eq", E("add", V("x"), I(2)), I(5))
    stage = compile_math_stage(raw, name="gate")
    assert [g.semantic for g in stage.glyphs] == ["x", "add", "2", "eq", "5"]
    assert len({g.id for g in stage.glyphs}) == len(stage.glyphs)
    static = stage.objects()
    dynamic = stage.objects(dynamic=True)
    assert all(isinstance(x, ObstacleSpec) and x.kind == "glyph" for x in static)
    assert all(isinstance(x, PropSpec) and x.kind == "glyph" for x in dynamic)
    assert all(glyphs.segments(x.glyph, x.size) for x in static)
    assert len({x.center for x in static}) == len(static)


def test_variable_x_and_multiplication_are_semantically_distinct():
    stage = compile_math_stage(E("mul", V("x"), I(2)), name="multiplication")
    assert [g.role for g in stage.glyphs] == ["variable", "operator", "number"]
    assert stage.glyphs[0].semantic == "x" and stage.glyphs[1].semantic == "mul"
    assert stage.glyphs[0].color != stage.glyphs[1].color


def test_subtraction_preserves_grouping_and_exponents_have_contours():
    stage = compile_math_stage(E("sub", V("x"), E("sub", I(3), I(2))))
    assert [g.semantic for g in stage.glyphs] == ["x", "sub", "(", "3", "sub", "2", ")"]
    powered = compile_math_stage(E("pow", V("x"), I(2)))
    assert len(powered.glyphs) == 3
    assert powered.glyphs[1].glyph == "^"


def test_refuses_invalid_mathematical_changes():
    first = E("eq", E("add", V("x"), I(2)), I(5))
    ok = E("eq", V("x"), I(3))
    a, b, proof = compile_proven_math_pair(first, ok, name="balance")
    assert proof.valid and len(a.glyphs) == 5 and len(b.glyphs) == 3
    with pytest.raises(ValueError):
        compile_proven_math_pair(first, E("eq", V("x"), I(4)))


def test_unrenderable_variables_overlap_and_oversized_layout_fail_closed():
    with pytest.raises(ValueError, match="cannot yet render variable"):
        compile_math_stage(V("theta"))
    with pytest.raises(ValueError, match="overlap"):
        compile_math_stage(I(2), glyph_size=(100, 100), gap=100)
    with pytest.raises(ValueError, match="width"):
        compile_math_stage(I(12345), max_width=300)


def test_new_mathematical_symbols_have_valid_physical_strokes():
    for sym in ("(", ")", "[", "]", "a", "b", "y", "z", "e", "n", "i", "∑", "∫", "∞", "→", "^"):
        assert glyphs.canonical(sym) == sym
        assert glyphs.segments(sym, (64, 92))
        assert glyphs.extent(sym, (64, 92), 8)[2] > glyphs.extent(sym, (64, 92), 8)[0]
