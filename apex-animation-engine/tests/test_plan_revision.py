"""D10.4 partial-response handling — a tiny targeted correction patches the preserved validated plan instead of
replacing the whole project (reproduces Failure 3). Invalid patches are rejected and the previous revision kept."""
import pytest

from apex.ai.plan_revision import PlanRevision
from apex.ai.plan_compiler import CompileError


def _scene():
    return {
        "schema_version": "0.1", "id": "s", "title": "s", "fps": 24, "width": 1280, "height": 720, "seed": 1,
        "characters": [{"id": "iko", "name": "IKO"}],
        "environments": [{"id": "e", "room": {"width": 2000, "height": 900, "entry_door": False},
                          "props": [{"id": "core", "kind": "glyph", "glyph": "8", "position": [200, 60],
                                     "size": [70, 90], "mass": 2, "solid": True}], "obstacles": [], "exits": []}],
        "scenes": [{"id": "s", "environment": "e", "duration": 10.0,
                    "placements": [{"character": "iko", "x": -300, "facing": 1}], "actions": [], "goals": [],
                    "shots": [{"id": "sh", "start": 0, "end": 10.0,
                               "camera": {"mode": "follow", "target": "iko", "view_height": 700}}]}],
    }


FULL = [{"character": "iko", "type": "run_to", "target_x": 100},
        {"character": "iko", "type": "notice", "target": "prop:core"},
        {"character": "iko", "type": "pick_up", "target": "prop:core"},
        {"character": "iko", "type": "act", "clip": "cheer"}]


def test_tiny_patch_preserves_the_other_validated_actions():
    rev = PlanRevision(_scene(), "s")
    rev.set_full(FULL)
    assert len(rev.actions) == 4
    # a 1-action correction (fix the pick_up target) must NOT wipe the other three validated actions (Failure 3)
    rev.patch({"op": "update", "index": 2, "fields": {"target": "core"}})   # bare name; compiler re-namespaces it
    acts = rev.actions
    assert len(acts) == 4                                   # all four preserved, not replaced by the single patch
    assert acts[2]["target"] == "prop:core"                # the one targeted action was corrected
    assert acts[0]["type"] == "run_to" and acts[3]["clip"] == "cheer"
    assert [r.source for r in rev.history] == ["full", "patch"]


def test_invalid_patch_is_rejected_and_previous_revision_preserved():
    rev = PlanRevision(_scene(), "s")
    rev.set_full(FULL)
    before = rev.actions
    with pytest.raises(CompileError):
        rev.patch({"op": "update", "index": 2, "fields": {"target": "prop:ghost"}})   # unknown reference
    assert rev.actions == before                            # unchanged; previous revision preserved
    assert rev.history[-1].source == "rejected"


def test_insert_and_delete_ops_keep_the_rest():
    rev = PlanRevision(_scene(), "s")
    rev.set_full(FULL)
    rev.patch([{"op": "insert", "index": 1, "action": {"character": "iko", "type": "idle", "duration": 0.5}},
               {"op": "delete", "index": 4}])               # insert shifts cheer to index 4, then delete it
    acts = rev.actions
    assert [a["type"] for a in acts] == ["run_to", "idle", "notice", "pick_up"]


def test_patch_before_full_is_refused():
    rev = PlanRevision(_scene(), "s")
    with pytest.raises(CompileError):
        rev.patch({"op": "delete", "index": 0})
