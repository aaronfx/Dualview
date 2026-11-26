"""Safe, deterministic mathematics semantics for APEX's future Math World.

The model deliberately distinguishes mathematical truth from visual choreography.
No free-form mathematical expression is evaluated as Python code.
This is an isolated foundation module; it does not yet drive the renderer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

_ALLOWED = {"int": 0, "var": 0, "add": 2, "sub": 2, "mul": 2, "div": 2, "pow": 2, "eq": 2}
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\Z")
MAX_DEPTH = 12
MAX_NODES = 80
MAX_INTEGER = 100_000
MAX_EXPONENT = 5


@dataclass(frozen=True)
class Term:
    """A bounded syntax tree supplied by the AI Director, not executable source."""
    op: str
    args: tuple["Term", ...] = ()
    value: int | str | None = None

    @classmethod
    def parse(cls, raw: Mapping[str, Any], *, _depth: int = 0, _budget: list[int] | None = None) -> "Term":
        if _budget is None:
            _budget = [MAX_NODES]
        if not isinstance(raw, Mapping) or _depth >= MAX_DEPTH or _budget[0] <= 0:
            raise ValueError("invalid or oversized math expression")
        _budget[0] -= 1
        if set(raw) - {"op", "args", "value"}:
            raise ValueError("unknown math expression keys")
        op = raw.get("op")
        if not isinstance(op, str) or op not in _ALLOWED:
            raise ValueError(f"unsupported math operator: {op!r}")
        if op in ("int", "var"):
            if "args" in raw and raw["args"]:
                raise ValueError("literal and variable cannot have children")
            val = raw.get("value")
            if op == "int" and (type(val) is not int or abs(val) > MAX_INTEGER):
                raise ValueError("integer literal must be bounded")
            if op == "var" and (not isinstance(val, str) or not _NAME.fullmatch(val)):
                raise ValueError("invalid variable name")
            return cls(op, (), val)
        if "value" in raw:
            raise ValueError("only literal and variable may have values")
        parts = raw.get("args")
        if not isinstance(parts, list) or len(parts) != _ALLOWED[op]:
            raise ValueError(f"operator {op} needs {_ALLOWED[op]} operands")
        if op == "eq" and _depth != 0:
            raise ValueError("an equation can only occur at the root")
        children = tuple(cls.parse(c, _depth=_depth + 1, _budget=_budget) for c in parts)
        if op == "div" and (children[1].op != "int" or children[1].value == 0):
            raise ValueError("only nonzero constant divisors are supported initially")
        if op == "pow" and (children[1].op != "int" or not 0 <= children[1].value <= MAX_EXPONENT):
            raise ValueError("only small nonnegative integer powers are supported initially")
        return cls(op, children)

    def variables(self) -> set[str]:
        if self.op == "var":
            return {str(self.value)}
        return set().union(*(c.variables() for c in self.args)) if self.args else set()

    def to_sympy(self):
        """Convert a restricted AST without eval, parsing of arbitrary strings or code execution."""
        import sympy as sp
        if self.op == "int":
            return sp.Integer(self.value)
        if self.op == "var":
            return sp.Symbol(self.value, real=True)
        a, b = (arg.to_sympy() for arg in self.args)
        if self.op == "add": return a + b
        if self.op == "sub": return a - b
        if self.op == "mul": return a * b
        if self.op == "div": return a / b
        if self.op == "pow": return a ** b
        if self.op == "eq": return sp.Eq(a, b, evaluate=False)
        raise AssertionError(self.op)


@dataclass(frozen=True)
class ProofResult:
    valid: bool
    kind: str
    explanation: str


def verify_rewrite(before: Mapping[str, Any], after: Mapping[str, Any]) -> ProofResult:
    """Verify expression identity or equality of one-variable real solution sets.

    The supported domain is polynomial expressions and constant denominators.
    A physical fight beat is not a rewrite and should never be validated as one.
    """
    import sympy as sp
    a, b = Term.parse(before), Term.parse(after)
    if (a.op == "eq") != (b.op == "eq"):
        return ProofResult(False, "type_mismatch", "an equation cannot become a bare expression")
    vars_ = sorted(a.variables() | b.variables())
    if a.op != "eq":
        ok = sp.simplify(a.to_sympy() - b.to_sympy()) == 0
        return ProofResult(bool(ok), "identity", "same expression" if ok else "different expressions")
    if len(vars_) > 1:
        return ProofResult(False, "unsupported", "equation verification currently supports one variable")
    la, ra = (x.to_sympy() for x in a.args)
    lb, rb = (x.to_sympy() for x in b.args)
    if not vars_:
        ok = bool((la - ra == 0) == (lb - rb == 0))
        return ProofResult(ok, "equation", "same truth value" if ok else "different truth values")
    var = sp.Symbol(vars_[0], real=True)
    sol_a = sp.solveset(la - ra, var, domain=sp.S.Reals)
    sol_b = sp.solveset(lb - rb, var, domain=sp.S.Reals)
    ok = sol_a == sol_b
    return ProofResult(bool(ok), "equation", "same real solution set" if ok else "different real solution sets")


def validate_beat(beat: Mapping[str, Any]) -> ProofResult:
    """Require mathematical proof only for semantic rewrites, not physical story actions."""
    if beat.get("kind") == "physical":
        if beat.get("action") not in {"grab", "throw", "ride", "push", "strike", "break", "climb", "dodge"}:
            raise ValueError("unsupported physical interaction")
        return ProofResult(True, "physical", "story event; no mathematical truth claim")
    if beat.get("kind") != "rewrite":
        raise ValueError("beat kind must be physical or rewrite")
    return verify_rewrite(beat["before"], beat["after"])
