"""Character intent selection is deterministic and never overrides physics."""
import pytest

from apex.ai.character_brain import CharacterBrain, Intent, Perception, Personality


def test_danger_preempts_curiosity_and_help():
    brain = CharacterBrain(Personality(curiosity=1, empathy=1))
    assert brain.choose(Perception(danger=0.9, novelty=1, ally_needs_help=True)) == Intent.EVADE


def test_recovery_has_first_priority():
    brain = CharacterBrain(Personality())
    assert brain.choose(Perception(recovering=True, danger=1)) == Intent.RECOVER


def test_personality_changes_response():
    bold = CharacterBrain(Personality(courage=0.9, curiosity=0.9))
    cautious = CharacterBrain(Personality(courage=0.1, curiosity=0.1))
    stimulus = Perception(danger=0.5, novelty=0.8, goal_visible=True)
    assert bold.choose(stimulus) == Intent.EXPLORE
    assert cautious.choose(stimulus) == Intent.EVADE


def test_help_when_safe():
    brain = CharacterBrain(Personality(empathy=0.9))
    assert brain.choose(Perception(ally_needs_help=True)) == Intent.HELP


def test_goal_and_memory_are_repeatable():
    brain = CharacterBrain(Personality(courage=0.7))
    for _ in range(3):
        assert brain.choose(Perception(goal_visible=True, danger=0.2)) == Intent.APPROACH
    assert brain.snapshot() == {"approach": 3}
    snapshot = brain.snapshot()
    snapshot["approach"] = 99
    assert brain.snapshot()["approach"] == 3


@pytest.mark.parametrize("kwargs", [{"curiosity": -0.1}, {"courage": 1.01}, {"empathy": -1}])
def test_invalid_personality(kwargs):
    with pytest.raises(ValueError):
        Personality(**kwargs)


@pytest.mark.parametrize("kwargs", [{"danger": -0.1}, {"novelty": 1.1}])
def test_invalid_perception(kwargs):
    with pytest.raises(ValueError):
        Perception(**kwargs)
