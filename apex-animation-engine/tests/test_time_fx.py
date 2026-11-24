"""Milestone 3: film time vs story time (hit-stop, slow motion), smears, film-time camera and screen effects."""
import numpy as np
import pytest

from apex.render.timewarp import Hold, Slow, TimeWarp, build_warp
from apex.scene.schema import SceneSpec, TimeFxSpec


def test_identity_warp_is_one_to_one():
    w = TimeWarp(10.0)
    assert w.is_identity() and abs(w.film_duration - 10.0) < 1e-9
    for t in (0.0, 3.3, 9.99):
        assert abs(w.sim_at(t) - t) < 1e-6 and abs(w.film_at(t) - t) < 1e-6


def test_hit_stop_holds_story_time_and_lengthens_the_film():
    w = TimeWarp(10.0, holds=[Hold(2.0, 5 / 24, 1.0, "hit")])
    assert abs(w.film_duration - (10.0 + 5 / 24)) < 1e-6
    f0 = w.film_at(2.0)
    assert abs(f0 - 2.0) < 1e-6
    held = [k for k in range(240) if abs(w.sim_at(k / 24) - 2.0) < 1e-6]
    assert len(held) >= 5  # the impact frame repeats for the hold
    assert abs(w.sim_at(f0 + 5 / 24 + 0.5) - 2.5) < 1e-3  # and the story resumes at full speed afterwards
    h, u = w.holding(f0 + 2 / 24)
    assert h.kind == "hit" and 0 < u < 1


def test_slow_motion_stretches_only_its_section():
    w = TimeWarp(10.0, slows=[Slow(4.0, 5.0, 0.25, 0.1, "flip")])
    assert np.all(np.diff(w.S) >= -1e-12) and np.all(np.diff(w.F) > 0)
    assert w.film_duration > 10.0 + 2.5  # about 1 s of story at 1/4 speed (plus the ramps)
    assert abs(w.film_at(2.0) - 2.0) < 1e-6  # before: untouched
    assert abs((w.film_duration - w.film_at(8.0)) - 2.0) < 1e-3  # after: full speed again
    assert w.slow_weight(w.film_at(4.5)) > 0.99 and w.slow_weight(1.0) == 0.0


def test_build_warp_from_events():
    from apex.motion.controller import Event
    sc = SceneSpec.model_validate({"id": "s", "environment": "e", "duration": 10, "placements": [{"character": "a", "x": 0}],
                                   "shots": [{"id": "x", "start": 0, "end": 10, "camera": {"mode": "static", "center": [0, 0]}}],
                                   "time_fx": {"slowmo": [{"at": "flip@a[dir=back]", "rate": 0.3}]}})
    evs = [Event(2.0, "hit", "a", {"power": 1.5}), Event(2.0, "hurt", "b", {}), Event(2.01, "prop_hit", "p", {}),
           Event(5.0, "block_hit", "b", {"power": 0.5}), Event(6.0, "flip", "a", {"dir": "front"}), Event(7.0, "flip", "a", {"dir": "back"})]
    w = build_warp(sc, evs, 10.0, 24)
    assert [round(h.t, 2) for h in w.holds] == [2.0, 5.0]  # the hit and its prop_hit are one blow
    assert w.holds[0].film > w.holds[1].film  # a heavy hit holds longer than a block
    assert len(w.slows) == 1 and abs(w.slows[0].t1 - (7.0 + 0.45)) < 1e-9  # the filter picked the back flip


def test_time_fx_schema_bounds():
    with pytest.raises(ValueError):
        TimeFxSpec(slowmo=[{"at": "flip@a", "rate": 0.01}])
    assert TimeFxSpec().hit_stop and TimeFxSpec().smears


def test_effects_and_sounds_move_to_the_film_clock():
    from apex.motion.controller import Event
    from apex.render.pipeline import screen_effects, warp_effects, warp_events
    w = TimeWarp(10.0, holds=[Hold(2.0, 4 / 24, 1.2, "hit")], slows=[Slow(6.0, 7.0, 0.3, 0.1, "x")])
    fx = warp_effects([{"kind": "impact", "t": 3.0, "life": 0.2}], w)
    assert abs(fx[0]["t"] - (3.0 + 4 / 24)) < 1e-6
    ev = warp_events([Event(3.0, "hit", "a", {})], w)
    assert abs(ev[0].t - (3.0 + 4 / 24)) < 1e-6 and any(e.type == "slowmo" for e in ev)
    tfx = TimeFxSpec()
    s = screen_effects(w, w.film_at(2.0) + 0.01, tfx)
    assert 0.2 < s["flash"] <= 0.3 and s["vignette"] > 0  # a heavy blow flashes on its first frame (bounded brightness)
    assert screen_effects(w, w.film_at(2.0) + 0.2, tfx).get("flash", 0.0) == 0.0  # and only briefly
    assert screen_effects(w, w.film_at(6.5), tfx)["lines"] > 0.9  # speed lines in slow motion


def test_knockdown_hold_closes_in_on_the_blow():
    from apex.camera.director import CameraState
    from apex.render.pipeline import film_camera
    tfx = TimeFxSpec()
    w = TimeWarp(10.0, holds=[Hold(2.0, 5 / 24, 1.5, "hit", (300.0, 120.0), heavy=True), Hold(6.0, 4 / 24, 1.2, "hit", (0.0, 100.0))])
    base = CameraState(0.0, 150.0, 500.0, 0.0, "s")
    c = film_camera(base, w, w.film_at(2.0) + 0.1, tfx)
    assert c.view_h < 0.78 * 500.0 and c.cx > 100.0  # a knockdown: pushed in, re-centred toward the blow
    c2 = film_camera(base, w, w.film_at(6.0) + 0.1, tfx)
    assert 0.85 * 500.0 < c2.view_h < 500.0 and abs(c2.cx) < 1e-6  # an ordinary heavy blow: a small punch-in only
    assert film_camera(base, w, 4.5, tfx).view_h == 500.0  # nothing between blows
