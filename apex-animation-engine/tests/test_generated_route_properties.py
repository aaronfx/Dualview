"""Generated lane tests exercise the actual native controller algorithm."""
from types import SimpleNamespace
from hypothesis import given, settings, strategies as st
from apex.motion.acrobatics import AcroMixin, ROOM_LANE


class LaneHarness(AcroMixin):
    def __init__(self, z, half):
        self.z = z
        self.carrying = "load"
        self.props = {"load": SimpleNamespace(depth=half*2)}


@given(z=st.integers(-60,60), half=st.integers(14,45),
       bands=st.lists(st.tuples(st.integers(-60,60),st.integers(1,80)), max_size=8))
@settings(max_examples=150, deadline=None)
def test_native_lane_never_returns_overlapping_clearance(z, half, bands):
    controller = LaneHarness(z, half)
    blockers = [(str(i), center, depth) for i,(center,depth) in enumerate(bands)]
    lane = controller._free_lane(blockers)
    if lane is not None:
        assert -ROOM_LANE <= lane <= ROOM_LANE
        assert all(abs(lane-center) >= depth+half+3 for center,depth in bands)
    assert lane == controller._free_lane(blockers)
