"""Regression tests for reusable, expressive physical gestures.

These checks protect the timing contract at the emitted fist-bump contact
event. They do not claim the shot has passed a subjective artistic review.
"""
import math

import pytest

from apex.motion.interaction import GESTURE_CONTACT, GESTURE_T
from apex.motion.interaction_anim import fist_bump_timing


def test_fist_bump_has_preparation_contact_and_recoil():
    assert fist_bump_timing(0) == (0, 0, 0)
    before = fist_bump_timing(0.20)
    assert before[1] > 0.75  # visible anticipation before the fist travels
    assert before[0] < 0.1
    at = fist_bump_timing(GESTURE_CONTACT)
    assert at[0] == pytest.approx(1.0)
    assert at[2] == 0.0
    after = fist_bump_timing(GESTURE_CONTACT + 0.22)
    assert 0 < after[0] < 1
    assert after[2] > 0.75  # the body visibly absorbs the bump
    end = fist_bump_timing(GESTURE_T)
    assert end[0] == pytest.approx(0.0)
    assert end[2] == pytest.approx(0.0)


def test_gesture_curve_is_bounded_and_has_no_contact_pop():
    previous = None
    for k in range(151):
        t = GESTURE_T * k / 150
        vals = fist_bump_timing(t)
        assert all(math.isfinite(x) and 0 <= x <= 1 for x in vals)
        if previous is not None:
            assert abs(vals[0] - previous[0]) < 0.15  # no sharp reach teleport at 100 Hz
        previous = vals


def test_gesture_curve_rejects_invalid_contact_time():
    with pytest.raises(ValueError):
        fist_bump_timing(0.1, 0.0)
