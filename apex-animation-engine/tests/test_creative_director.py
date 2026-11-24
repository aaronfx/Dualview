"""The live AI Director must understand and validate the three-reference contract."""
import pytest

from apex.ai.director import StoryDirector, system_prompt
from apex.scene.schema import ProjectSpec
from tests.test_creative_cli import minimal


def test_director_prompt_describes_causal_math_arcade_and_epic_contract():
    s = system_prompt()
    assert "OPTIONAL CREATIVE PLAN" in s
    assert "creative_plan" in s
    assert "FILM time" in s


def test_ai_dry_run_accepts_true_math_and_refuses_false_claims():
    StoryDirector._dry_run(ProjectSpec.model_validate(minimal(verified=True)))
    with pytest.raises(ValueError, match="creative plan contradicted"):
        StoryDirector._dry_run(ProjectSpec.model_validate(minimal(verified=False)))
