"""Native prop compilation for proof-carrying signed terms.

All strokes in a signed term belong to one native PropSpec. This is not yet
an authenticated runtime equation rewrite.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .glyphs import canonical
from .math_transposition import AdditiveTransposition, plan_additive_transposition
from .schema import PropSpec


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
    total = sum(widths) + 4 * gap + term_width
    x = center[0] - total / 2
    props = []
    for (role, token), w in zip(tokens, widths):
        props.append(PropSpec(id=f"{name}_{role}", kind="glyph", glyph=canonical(token),
                              position=(x + w / 2, center[1]), size=(w, height),
                              color="#6bdffe" if role == "variable" else
                                    "#ffcc66" if role == "term" else "#f5f6ff",
                              mass=2.4, solid=False, z=-52))
        x += w + gap
    return TranspositionStage(plan, tuple(props), f"{name}_term", (x + term_width / 2, center[1]))
