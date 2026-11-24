"""Generalisable linear-equation solver and verified solve plan (`a*x + b = c`).

The autonomous equation film is generated from this plan — the physical staging is never hardcoded per equation. Each
step isolates x by the same operation applied to *both sides* (subtract a constant, divide by the coefficient), and each
step is checked two ways: exact rational arithmetic preserves the solution, and `math_semantics.verify_rewrite` (SymPy)
proves the before/after equations are equivalent. A step that fails either check is refused before anything is staged.

This is the engine authority for "why subtracting the same amount from both sides keeps the equation balanced": every
step keeps `left value == right value`, so a balance indicator driven by the two sides stays level.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from .math_semantics import verify_rewrite


def _frac(v) -> Fraction:
    return v if isinstance(v, Fraction) else Fraction(v)


@dataclass(frozen=True)
class Equation:
    """A linear equation `a*x + b = c` with exact rational coefficients."""
    a: Fraction
    b: Fraction
    c: Fraction

    def __post_init__(self):
        object.__setattr__(self, "a", _frac(self.a))
        object.__setattr__(self, "b", _frac(self.b))
        object.__setattr__(self, "c", _frac(self.c))
        if self.a == 0:
            raise ValueError("a == 0 is not a linear equation in x")

    @property
    def solution(self) -> Fraction:
        return (self.c - self.b) / self.a

    @property
    def lhs_value(self) -> Fraction:
        """The numeric value of the left side at the solution (equals the right side — that's what '=' means)."""
        return self.a * self.solution + self.b

    def ast(self) -> dict[str, Any]:
        """The bounded AST (for math_stage rendering and SymPy verification). Integers only (the supported glyph set)."""
        def I(v: Fraction):
            if v.denominator != 1:
                raise ValueError(f"only integer coefficients are renderable as glyphs (got {v})")
            return {"op": "int", "value": int(v)}

        x = {"op": "var", "value": "x"}
        lhs = x if self.a == 1 else {"op": "mul", "args": [I(self.a), x]}
        if self.b != 0:
            lhs = {"op": "add", "args": [lhs, I(self.b)]}
        return {"op": "eq", "args": [lhs, I(self.c)]}


@dataclass(frozen=True)
class Step:
    """One balance-preserving operation applied to both sides."""
    op: str            # "subtract" | "divide"
    amount: Fraction   # the constant removed from both sides, or the divisor
    before: Equation
    after: Equation
    description: str


def solve_plan(a, b, c) -> tuple[list[Step], Fraction]:
    """The ordered, verified steps that isolate x in `a*x + b = c`, and the solution.

    1. if b != 0: subtract b from both sides  ->  a*x = c - b
    2. if a != 1: divide both sides by a      ->  x = (c - b) / a

    Every step is proven equivalent by SymPy and by exact arithmetic (same solution), or it raises.
    """
    eq = Equation(a, b, c)
    sol = eq.solution
    steps: list[Step] = []

    if eq.b != 0:
        nxt = Equation(eq.a, Fraction(0), eq.c - eq.b)
        _check(eq, nxt)
        phrase = f"add {abs(eq.b)} to both sides" if eq.b < 0 else f"subtract {eq.b} from both sides"
        steps.append(Step("subtract", eq.b, eq, nxt, phrase))
        eq = nxt

    if eq.a != 1:
        nxt = Equation(Fraction(1), Fraction(0), eq.c / eq.a)
        _check(eq, nxt)
        steps.append(Step("divide", eq.a, eq, nxt,
                          f"divide both sides by {eq.a}"))
        eq = nxt

    if eq.solution != sol or eq.a != 1 or eq.b != 0:
        raise ValueError("solve plan did not isolate x correctly")
    return steps, sol


def _check(before: Equation, after: Equation) -> None:
    if before.solution != after.solution:
        raise ValueError("step changed the solution set")
    proof = verify_rewrite(before.ast(), after.ast())
    if not proof.valid:
        raise ValueError(f"step is not a proven equivalence: {proof.explanation}")
