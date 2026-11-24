"""The review pipeline additions: the contact-sheet frame schedule (1 s grid + dense around key events), the mandatory
visual-review gate, and the pairwise context matrix's coverage."""
import json
import math
import os

from apex.qa.media import review_frame_times
from apex.qa.review import CRITERIA, review_gate, review_status
from apex.qa.transitions import FACTORS, covers_all_pairs, pairwise


def test_frame_schedule_has_second_grid_and_dense_frames_around_events():
    dur, fps = 10.0, 24
    times, is_dense = review_frame_times(dur, key_times=[5.0], fps=fps)
    # the whole-film one-second grid is present
    for s in range(int(dur)):
        assert any(abs(t - s) < 1e-6 for t in times), f"missing grid frame at {s}s"
    # extra high-frequency frames cluster around the event at 5 s, finer than the 1 s grid
    near = [t for t, d in zip(times, is_dense) if d and abs(t - 5.0) <= 0.4 + 1e-6]
    assert len(near) >= 4, near
    gaps = [b - a for a, b in zip(near, near[1:])]
    assert gaps and max(gaps) <= 2.0 / fps + 2e-3, "dense frames are not at (near) frame rate"
    assert times == sorted(times) and len(times) == len(set(times)), "times must be sorted and unique"


def test_no_events_is_just_the_grid():
    times, is_dense = review_frame_times(5.0, key_times=[], fps=24)
    assert not any(is_dense)
    assert times == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_review_gate_blocks_until_a_human_has_reviewed(tmp_path):
    out = str(tmp_path / "r")
    os.makedirs(out)
    # nothing reviewed yet -> not deliverable (technical QA passing is not enough)
    g = review_gate(out)
    assert g["deliverable"] is False and not g["status"]["reviewed"]
    # a partial sheet (some criteria unscored) still does not count
    rev = os.path.join(out, "reviewers")
    os.makedirs(rev)
    partial = {"scores": {k: (7 if i == 0 else None) for i, (k, _, _) in enumerate(CRITERIA)}, "notes": {}}
    with open(os.path.join(rev, "a.json"), "w") as fh:
        json.dump(partial, fh)
    assert review_gate(out)["deliverable"] is False
    # a completed sheet -> deliverable (the scores are advisory, never an automatic quality claim)
    full = {"scores": {k: 7 for k, _, _ in CRITERIA}, "notes": {}}
    with open(os.path.join(rev, "b.json"), "w") as fh:
        json.dump(full, fh)
    g = review_gate(out)
    assert g["deliverable"] is True and g["status"]["reviewers_complete"] == 1


def test_pairwise_covers_every_factor_pair_in_far_fewer_scenes():
    rows = pairwise(FACTORS)
    assert covers_all_pairs(FACTORS, rows), "the covering array misses some factor-level pair"
    full = math.prod(len(v) for v in FACTORS.values())
    assert len(rows) < full / 3, f"{len(rows)} rows is not a meaningful reduction from {full}"
    # deterministic
    assert [r for r in pairwise(FACTORS)] == rows
