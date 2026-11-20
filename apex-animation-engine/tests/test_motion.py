import math

import numpy as np

from apex.motion.gait import Gait, GaitParams


def make_gait(v=150.0, dur=3.0):
    ts = np.linspace(0, dur, int(dur * 480) + 1)
    vs = np.minimum(v, ts * 400.0)
    ss = np.concatenate([[0], np.cumsum((vs[1:] + vs[:-1]) / 2 * np.diff(ts))])
    return Gait(ts, ss, vs, GaitParams(), 1.0, (9.0, -9.0), lead_leg=1)


def test_feet_do_not_move_during_stance():
    g = make_gait()
    for leg in (0, 1):
        for (a, b, s) in g.stance_intervals(leg):
            for t in np.linspace(a, b, 20):
                f = g.foot(float(t), leg)
                assert f.stance and abs(f.s - s) < 1e-9 and f.h == 0.0


def test_footfalls_alternate_and_advance():
    g = make_gait(400.0)
    legs = [f.leg for f in g.footfalls]
    assert all(a != b for a, b in zip(legs, legs[1:]))
    pos = [f.s for f in g.footfalls]
    assert all(b > a for a, b in zip(pos, pos[1:]))


def test_stance_is_centred_under_pelvis():
    g = make_gait(150.0, 4.0)
    for leg in (0, 1):
        for (a, b, s) in g.stance_intervals(leg)[2:]:
            if b >= g.t1 - 1e-6:  # interval truncated by the segment end
                continue
            mid = (a + b) / 2
            assert abs(s - float(np.interp(mid, g.times, g.s))) < 6.0


def test_run_has_flight_and_walk_has_double_support():
    p = GaitParams()
    assert p.stance_fraction(450) < 0.5 < p.stance_fraction(120)
