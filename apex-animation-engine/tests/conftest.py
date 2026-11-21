import json
from pathlib import Path

import pytest

from apex.scene.schema import ProjectSpec

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> ProjectSpec:
    return ProjectSpec.model_validate(json.loads((ROOT / "examples" / name).read_text()))


@pytest.fixture(scope="session")
def motion_project():
    return load("motion_test.json")


@pytest.fixture(scope="session")
def gravity_project():
    return load("gravity_switch_1b.json")


@pytest.fixture(scope="session")
def gravity_runtime(gravity_project):
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(gravity_project, "switch_and_fall")
    rt.simulate()
    return rt


@pytest.fixture(scope="session")
def motion_runtime(motion_project):
    from apex.scene.runtime import SceneRuntime
    rt = SceneRuntime(motion_project, "locomotion")
    rt.simulate()
    return rt
