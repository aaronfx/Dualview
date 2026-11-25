import json
from pathlib import Path

from apex.scene.schema import ProjectSpec
from apex.scene.presentation_export import export_scene


def test_native_export_contains_real_joint_motion():
    p = ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "bridge", "title": "Bridge", "fps": 24,
        "width": 640, "height": 360, "seed": 1,
        "characters": [{"id": "kai", "name": "Kai"}],
        "environments": [{"id": "e", "room": {"width": 1000, "height": 600,
                         "entry_door": False}}],
        "scenes": [{"id": "s", "environment": "e", "duration": 3,
                    "placements": [{"character": "kai", "x": -100}],
                    "actions": [{"character": "kai", "type": "walk_to", "target_x": 100}],
                    "shots": [{"id": "a", "start": 0, "end": 3,
                               "camera": {"mode": "follow", "target": "kai"}}]}]})
    data = export_scene(p, "s")
    json.dumps(data, allow_nan=False)
    assert data["version"] == 1 and len(data["frames"]) == 73
    assert data["frames"][0]["actors"]["kai"]["joints"] != data["frames"][-1]["actors"]["kai"]["joints"]
