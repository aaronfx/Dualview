"""Native prop compilation for proof-carrying signed terms.

All strokes in a signed term belong to one native PropSpec. This is not yet
an authenticated runtime equation rewrite.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .glyphs import canonical
from .math_transposition import AdditiveTransposition, plan_additive_transposition
from .schema import PropSpec, MorphSpec, MathTransferSpec


@dataclass(frozen=True)
class TranspositionStage:
    plan: AdditiveTransposition
    props: tuple[PropSpec, ...]
    term_id: str
    destination: tuple[float, float]


def compile_transposition_stage(raw: Mapping[str, Any], *, name: str = "transpose",
                                center: tuple[float, float] = (0.0, 65.0),
                                glyph_width: float = 54.0, height: float = 86.0,
                                gap: float = 26.0) -> TranspositionStage:
    if not name or not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError("invalid stage identifier")
    if min(glyph_width, height, gap) <= 0:
        raise ValueError("positive layout dimensions required")
    plan = plan_additive_transposition(raw)
    variable = str(plan.before.args[0].args[0].value)
    if len(variable) != 1 or variable not in "xzyabnie":
        raise ValueError("variable has no native glyph")
    tokens = (("variable", variable), ("term", plan.source.text),
              ("equals", "="), ("rhs", str(plan.rhs_before)))
    widths = [len(token) * glyph_width for _, token in tokens]
    term_width = widths[1]
    total = sum(widths) + 3 * gap + term_width
    x = center[0] - total / 2
    props = []
    for (role, token), w in zip(tokens, widths):
        props.append(PropSpec(id=f"{name}_{role}", kind="glyph", glyph=canonical(token),
                              position=(x + w / 2, center[1]),
                              size=(0.82 * w if role == "rhs" and len(token) == 1 else w, height),
                              weight=0.15 * min(0.82 * glyph_width, height),
                              color="#6bdffe" if role == "variable" else
                                    "#ffcc66" if role == "term" else "#f5f6ff",
                              mass=2.4, solid=False, z=-52))
        x += w + (0 if role == "rhs" else gap)
    return TranspositionStage(plan, tuple(props), f"{name}_term", (x + term_width / 2, center[1]))

def compile_native_transfer(spec: MathTransferSpec) -> tuple[TranspositionStage, tuple[PropSpec, ...]]:
    """Compile the actual native morphs and a geometrically aligned RHS body.

    Its activation is controlled by MathTransferRuntime, not by authored time.
    """
    stage = compile_transposition_stage(spec.equation, name=spec.name, center=spec.center,
                                        glyph_width=spec.glyph_width, height=spec.height, gap=spec.gap)
    p = stage.plan
    props = list(stage.props)
    term, rhs = props[1], props[3]
    term = term.model_copy(update={"morphs": [MorphSpec(
        to=p.destination.text, on=f"math_crossed@{spec.actor}[prop={term.id}]", duration=0.36)]})
    props[1] = term
    expression = p.expression_text
    slots = max(len(expression), len(str(p.result)))
    width = len(expression) * spec.glyph_width
    # The numeric group occupies precisely the two operand positions at
    # the transfer checkpoint. The merge has no discontinuous glyph jump.
    rhs_cells = len(str(p.rhs_before))
    x0 = rhs.position[0] - rhs_cells * spec.glyph_width / 2
    if slots != len(expression):
        raise ValueError("result exceeds expression width")
    combined = PropSpec(id=f"{spec.name}_evaluation", kind="glyph", glyph=expression,
                        position=(x0 + width / 2, spec.center[1]), size=(width, spec.height),
                        weight=rhs.weight, color=rhs.color, mass=term.mass + rhs.mass,
                        solid=False, z=rhs.z,
                        morphs=[MorphSpec(to=f"@{slots}:{p.result}",
                                         on=f"math_evaluate@{spec.actor}[prop={spec.name}_evaluation]",
                                         duration=0.9)])
    props.append(combined)
    return stage, tuple(props)
