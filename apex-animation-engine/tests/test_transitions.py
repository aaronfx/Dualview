"""Hand-overs between scripted moves and dynamic physics, judged by the same technical checks as a film.

Each chain (flips, rolls, combat, ragdoll impacts, recovery, carrying, climbing) runs in one shared arena with no
per-scenario tuning; see apex.qa.transitions.
"""
import pytest

from apex.qa import transitions


@pytest.mark.parametrize("name", list(transitions.SCENARIOS))
def test_transition_chain(name):
    out = transitions.run(name)
    assert out["ok"], (out["failed_checks"], out["violations"], out["left"])
