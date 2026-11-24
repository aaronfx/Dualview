"""Compile bounded symbolic ASTs into actual APEX glyph geometry.

This bridges *mathematical meaning* and the existing Skia/Pymunk objects.
It does not fake equation transforms: a before/after change is a future
runtime event and must be proved and performed physically, not just cut to.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .math_semantics import Term, ProofResult, verify_rewrite
from .glyphs import canonical
from .schema import ObstacleSpec, PropSpec

# Existing "x" and multiplication "×" share geometry but keep distinct
# semantic roles and colors; the AI Director cannot silently conflate them.
_OP = {"add": "+", "sub": "-", "mul": "×", "div": "÷", "pow": "^", "eq": "="}
_PRECEDENCE = {"eq": 0, "add": 1, "sub": 1, "mul": 2, "div": 2, "pow": 3,
               "int": 4, "var": 4}
_VARIABLE_GLYPHS = frozenset("xzyabnie")
COLORS = {"number": "#f5f6ff", "variable": "#6bdffe",
          "operator": "#ffcc66", "group": "#a5b2ff"}


@dataclass(frozen=True)
class MathGlyph:
    id: str
    glyph: str
    role: str
    semantic: str
    x: float
    y: float
    size: tuple[float, float]
    color: str


@dataclass(frozen=True)
class MathStage:
    """Stable IDs and physical geometry for one mathematically grounded expression."""
    expression: Term
    glyphs: tuple[MathGlyph, ...]

    def objects(self, *, dynamic: bool = False, mass: float = 3.0):
        """Native APEX objects, not a drawing-only placeholder.

        Static glyphs are solid Obstacles that may be stood on where a flat
        top exists. Dynamic glyphs are real Pymunk props that can be thrown.
        """
        if mass <= 0:
            raise ValueError("mass must be positive")
        if dynamic:
            return [PropSpec(id=g.id, kind="glyph", glyph=g.glyph, position=(g.x, g.y),
                             size=g.size, color=g.color, mass=mass, friction=0.65)
                    for g in self.glyphs]
        return [ObstacleSpec(id=g.id, kind="glyph", glyph=g.glyph, center=(g.x, g.y),
                             size=g.size, color=g.color) for g in self.glyphs]


def _glyphs(term: Term, parent_prec: int = -1, right_of_nonassoc: bool = False) -> list[tuple[str, str, str]]:
    """Render in-order with necessary parentheses, preserving mathematical grouping."""
    if term.op == "int":
        val = str(term.value)
        return [(canonical(g), "number" if g != "-" else "operator", g) for g in val]
    if term.op == "var":
        name = str(term.value)
        if any(g not in _VARIABLE_GLYPHS for g in name):
            raise ValueError(f"math stage cannot yet render variable {name!r}; supported: {''.join(sorted(_VARIABLE_GLYPHS))}")
        return [(canonical(g), "variable", g) for g in name]
    prec = _PRECEDENCE[term.op]
    left, right = term.args
    left_tokens = _glyphs(left, prec, False)
    right_tokens = _glyphs(right, prec, term.op in ("sub", "div", "pow"))
    tokens = left_tokens + [(canonical(_OP[term.op]), "operator", term.op)] + right_tokens
    if prec < parent_prec or (right_of_nonassoc and prec == parent_prec):
        tokens = [("(", "group", "(")] + tokens + [(")", "group", ")")]
    return tokens


def compile_math_stage(raw: Mapping[str, Any] | Term, *, name: str = "math",
                       center: tuple[float, float] = (0.0, 300.0),
                       glyph_size: tuple[float, float] = (74.0, 96.0),
                       gap: float = 95.0, max_width: float = 1700.0) -> MathStage:
    if not name or len(name) > 36 or not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("math stage name must be a short identifier")
    if glyph_size[0] <= 0 or glyph_size[1] <= 0 or gap < glyph_size[0] * 1.1:
        raise ValueError("math glyph sizes and gap must avoid initial overlap")
    expr = raw if isinstance(raw, Term) else Term.parse(raw)
    tokens = _glyphs(expr)
    if not 1 <= len(tokens) <= 48:
        raise ValueError("math expression exceeds the visual glyph budget (48)")
    width = (len(tokens)-1) * gap + glyph_size[0]
    if width > max_width:
        raise ValueError(f"math expression width {width:g} exceeds {max_width:g}; break into more shots")
    x0 = center[0] - (len(tokens)-1) * gap / 2
    entries = tuple(MathGlyph(id=f"{name}_{i:02d}", glyph=glyph, role=role, semantic=semantic,
                               x=x0 + i * gap, y=center[1], size=glyph_size, color=COLORS[role])
                    for i, (glyph, role, semantic) in enumerate(tokens))
    return MathStage(expr, entries)


def compile_proven_math_pair(before: Mapping[str, Any], after: Mapping[str, Any], *,
                             name: str = "math", **kwargs) -> tuple[MathStage, MathStage, ProofResult]:
    """Reject false math before allocating physical objects for an authored transition.

    NOTE: a proven pair does not itself animate an equation! The multi-token
    transformation must still be implemented as a simulation event and checked.
    """
    proof = verify_rewrite(before, after)
    if not proof.valid:
        raise ValueError(f"invalid math-world transformation: {proof.explanation}")
    return (compile_math_stage(before, name=f"{name}_before", **kwargs),
            compile_math_stage(after, name=f"{name}_after", **kwargs),
            proof)


@dataclass(frozen=True)
class BalancePlan:
    """How to turn a SymPy-proven equation rewrite into physical actions on the `before` glyphs.

    `remove` are glyph ids (terms) the character physically removes (throws off / knocks loose). `morph` are
    (glyph id, new glyph) pairs the engine morphs in place when the removal happens. The plan never spawns a new
    symbol — only removal and in-place value change — so the staged film and the proof stay honest.
    """
    before: MathStage
    after: MathStage
    proof: ProofResult
    remove: tuple[str, ...]
    morph: tuple[tuple[str, str], ...]


def _split_eq(stage: MathStage):
    toks = list(stage.glyphs)
    cut = next((i for i, g in enumerate(toks) if g.semantic == "eq"), None)
    if cut is None:
        raise ValueError("plan_balance needs an equation (a token with '=')")
    return toks[:cut], toks[cut + 1:]


def _side_plan(b_side, a_side):
    """Align one side of the equation: a common prefix stays; the rest of `before` is removed or morphed to match
    `after`. Adding a brand-new symbol that `before` does not have is not a physical balance and is refused."""
    lcp = 0
    while lcp < len(b_side) and lcp < len(a_side) and b_side[lcp].glyph == a_side[lcp].glyph:
        lcp += 1
    b_rest, a_rest = b_side[lcp:], a_side[lcp:]
    remove, morph = [], []
    for i, bg in enumerate(b_rest):
        if i < len(a_rest):
            if bg.glyph != a_rest[i].glyph:
                morph.append((bg.id, a_rest[i].glyph))
        else:
            remove.append(bg.id)
    if len(a_rest) > len(b_rest):
        raise NotImplementedError("physical balance can remove or change terms, not spawn new ones; "
                                  "stage this rewrite as more steps")
    return remove, morph


def plan_balance(before: Mapping[str, Any], after: Mapping[str, Any], *, name: str = "eqn", **layout) -> BalancePlan:
    """Prove an equation rewrite (SymPy) and compute the physical balance plan over the `before` glyphs.

    A false rewrite raises before any object is built. The returned plan says which term glyphs the character
    removes and which morph in place, so an authored film performs a *proven* transformation rather than cutting to
    a fake one. Supports the linear-balance pattern (cancel equal terms from both sides, change the constant)."""
    stage_b, stage_a, proof = compile_proven_math_pair(before, after, name=name, **layout)
    (bl, br), (al, ar) = _split_eq(stage_b), _split_eq(stage_a)
    rl, ml = _side_plan(bl, al)
    rr, mr = _side_plan(br, ar)
    return BalancePlan(stage_b, stage_a, proof, tuple(rl + rr), tuple(ml + mr))
