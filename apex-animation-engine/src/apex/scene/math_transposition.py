"""Ordered proof-carrying transitions for additive equations.

The supported initial domain is variable +/- nonnegative integer = integer.
Reject other syntax rather than pretend it has a valid physical choreography.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from .math_semantics import Term, ProofResult, verify_rewrite


def _raw(t: Term) -> dict[str, Any]:
    if t.op in ("int", "var"):
        return {"op": t.op, "value": t.value}
    return {"op": t.op, "args": [_raw(a) for a in t.args]}


def _binary(op: str, a: Term, b: Term) -> Term:
    return Term(op, (a, b))


@dataclass(frozen=True)
class SignedTerm:
    id: str
    value: int
    side: str
    sign: str

    @property
    def text(self) -> str:
        return self.sign + str(abs(self.value))


@dataclass(frozen=True)
class AdditiveTransposition:
    before: Term
    intermediate: Term
    solved: Term
    source: SignedTerm
    destination: SignedTerm
    rhs_before: int
    result: int
    transfer_proof: ProofResult
    evaluation_proof: ProofResult

    @property
    def expression_text(self) -> str:
        return str(self.rhs_before) + self.destination.text


def plan_additive_transposition(raw: Mapping[str, Any]) -> AdditiveTransposition:
    before = Term.parse(raw)
    if before.op != "eq":
        raise ValueError("expected an equation")
    left, right = before.args
    if left.op not in ("add", "sub") or right.op != "int":
        raise ValueError("expected variable +/- integer = integer")
    variable, magnitude = left.args
    if variable.op != "var" or magnitude.op != "int" or magnitude.value < 0:
        raise ValueError("expected variable +/- nonnegative integer = integer")
    n, c = int(magnitude.value), int(right.value)
    sign = "+" if left.op == "add" else "-"
    inverse = "-" if sign == "+" else "+"
    value = n if sign == "+" else -n
    source = SignedTerm("transfer_term", value, "left", sign)
    destination = SignedTerm(source.id, -value, "right", inverse)
    intermediate = _binary("eq", variable,
                           _binary("sub" if inverse == "-" else "add", right, magnitude))
    result = c - value
    solved = _binary("eq", variable, Term("int", value=result))
    transfer_proof = verify_rewrite(_raw(before), _raw(intermediate))
    evaluation_proof = verify_rewrite(_raw(intermediate), _raw(solved))
    if not transfer_proof.valid or not evaluation_proof.valid:
        raise ValueError("unproved mathematical transition")
    return AdditiveTransposition(before, intermediate, solved, source, destination,
                                 c, result, transfer_proof, evaluation_proof)
