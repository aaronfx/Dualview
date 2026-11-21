"""Milestone 4: level builder, orbs, portals, beat sync, particles."""
import math
from types import SimpleNamespace as N

import numpy as np
import pytest

from apex.motion.arcade import PortalMap
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import EnvironmentSpec, ProjectSpec


def env(rows, **kw):
    return EnvironmentSpec.model_validate({"id": "e", "room": {"width": 1700, "height": 900, "entry_door": False}, "dust": 0,
                                           "level": {"cell": 60, "origin": [-780, 0], "rows": rows, **kw}})


def proj(acts, rows, props=(), dur=6.0, music=None, shots=None):
    sc = {"id": "s", "environment": "e", "duration": dur, "placements": [{"character": "kai", "at": "1", "facing": 1}],
          "actions": acts, "shots": shots or [{"id": "a", "start": 0, "end": dur, "camera": {"mode": "follow", "target": "kai"}}]}
    if music:
        sc["music"] = music
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360, "seed": 3,
        "characters": [{"id": "kai", "name": "KAI"}],
        "environments": [{"id": "e", "room": {"width": 1700, "height": 900, "entry_door": False}, "dust": 0, "props": list(props),
                          "level": {"cell": 60, "origin": [-780, 0], "rows": rows}}],
        "scenes": [sc]})


def qa(p):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    from apex.render.timewarp import build_warp
    rt = SceneRuntime(p, "s")
    res = rt.simulate()
    w = build_warp(rt.scene, res.events, res.duration, p.fps)
    rep = Inspector(rt, build_camera(rt, p.width / p.height), p.fps, warp=w).run(check_determinism=False)
    return rt, res, rep


# ---------------------------------------------------------------- level builder
def test_level_grid_expands_into_platforms_orbs_portals_and_markers():
    e = env(["          ",
             "   o  *   ",
             "  ===  A  ",
             "1 ^ ##  a "])
    blocks = [o for o in e.obstacles if o.kind == "platform"]
    assert {o.id[:8] for o in blocks} == {"lv_block", "lv_ledge"}
    blk = next(o for o in blocks if o.id.startswith("lv_block"))
    assert blk.size == (120.0, 60.0) and blk.center == (-780 + 4 * 60 + 60, 30.0)  # a run of two cells merged
    assert sorted(o.kind for o in e.orbs) == ["collect", "jump", "pad"]
    assert {p.id: p.link for p in e.portals} == {"portal_A": "portal_a", "portal_a": "portal_A"}
    assert e.level.markers["1"] == (-750.0, 0.0)
    again = EnvironmentSpec.model_validate(e.model_dump())  # re-validation does not expand twice
    assert len(again.obstacles) == len(e.obstacles) and len(again.orbs) == len(e.orbs)


def test_level_rejects_unpaired_portals_and_oversized_grids():
    with pytest.raises(ValueError, match="partner"):
        env(["1  A   "])
    with pytest.raises(ValueError, match="fit the room"):
        env(["#" * 40])


# ---------------------------------------------------------------- portals
@pytest.mark.parametrize("a,b", [(180, 0), (180, 180), (90, 0), (-90, 90), (30, 200)])
def test_portal_map_preserves_speed_and_keeps_up_up_when_it_can(a, b):
    m = PortalMap(N(center=(10, 20), angle=a, height=100), N(center=(300, 400), angle=b, height=100))
    v = (-math.cos(math.radians(a)) * 500 + 30, -math.sin(math.radians(a)) * 500 - 70)
    assert math.isclose(math.hypot(*m.vec(v)), math.hypot(*v), rel_tol=1e-9)
    n_in = (-math.cos(math.radians(a)), -math.sin(math.radians(a)))
    out = m.vec(n_in)
    assert math.isclose(out[0], math.cos(math.radians(b)), abs_tol=1e-9) and math.isclose(out[1], math.sin(math.radians(b)), abs_tol=1e-9)
    if (a, b) == (180, 180):  # same-facing portals mirror the body instead of turning it upside down
        assert m.mirror and abs(m.angle(0.0)) < 1e-9


def test_a_character_runs_through_a_floor_portal_with_its_speed_and_qa_verifies_it():
    p = proj([{"character": "kai", "type": "run_to", "target_x": 700}],
             ["          ", "1        A          a     "])
    rt, res, rep = qa(p)
    ent = next(e for e in res.events if e.type == "portal_enter")
    ex = next(e for e in res.events if e.type == "portal_exit")
    assert ex.data["grounded"] and math.isclose(ex.data["speed"], ent.data["speed"], rel_tol=1e-9)
    assert any(s.data.get("cut") for s in res.controllers["kai"].segments)
    checks = {c.name: c for c in rep.checks}
    assert checks["portal_transfers"].status == "PASS" and checks["no_teleport_joints[kai]"].status == "PASS"
    assert rep.gates()["technical"] == "PASS"
    assert res.controllers["kai"].s > ex.data["point"][0]  # it ran on out of the exit and braked to a stop


def test_a_falling_prop_leaves_a_rotated_portal_sideways_at_the_same_speed():
    p = ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360, "seed": 3,
        "characters": [{"id": "kai", "name": "KAI"}],
        "environments": [{"id": "e", "room": {"width": 1700, "height": 900, "entry_door": False}, "dust": 0,
                          "props": [{"id": "box", "kind": "crate", "position": [-300, 500], "size": [30, 30], "mass": 4, "z": 40, "depth": 10}],
                          "portals": [{"id": "down", "center": [-300, 150], "angle": 90, "link": "side", "height": 160},
                                      {"id": "side", "center": [300, 300], "angle": 0, "link": "down", "height": 160}]}],
        "scenes": [{"id": "s", "environment": "e", "duration": 2, "placements": [{"character": "kai", "x": -700}], "actions": [],
                    "shots": [{"id": "a", "start": 0, "end": 2, "camera": {"mode": "static", "center": [0, 300]}}]}]})
    r = SceneRuntime(p, "s").simulate(physics_only=True)
    ent = next(e for e in r.events if e.type == "portal_enter")
    ex = next(e for e in r.events if e.type == "portal_exit")
    assert ent.data["velocity"][1] < -800 and ex.data["velocity"][0] > 800 and abs(ex.data["velocity"][1]) < 1e-6
    i = r.prop_cuts["box"][0]
    from apex.scene.runtime import interp_track
    tr, T = r.prop_tracks["box"], r.prop_times
    mid = (T[i - 1] + T[i]) / 2  # between the samples on either side of the jump: never a point in between
    assert interp_track(T, tr[:, 0], mid, r.prop_cuts["box"]) == tr[i - 1, 0]


# ---------------------------------------------------------------- orbs
def test_pad_and_jump_orb_change_the_velocity_by_their_spec():
    rows = ["          ", "          ", "          o     *         ", "          ", "          ", "          ",
            "1     ^         ######    "]
    rt, res, rep = qa(proj([{"character": "kai", "type": "run_to", "target_x": 400}], rows))
    kinds = [e.type for e in res.events if e.type.startswith("orb_") or e.type == "collect"]
    assert kinds == ["orb_pad", "orb_jump", "collect"]
    checks = {c.name: c for c in rep.checks}
    assert checks["orb_impulses"].status == "PASS" and checks["orb_impulses"].metric < 0.01
    assert rep.gates()["technical"] == "PASS"
    assert res.controllers["kai"].frame.tag.startswith("lv_block")  # the orbs carried him onto the block


# ---------------------------------------------------------------- beats
def test_beat_waits_end_on_the_beat_and_cuts_snap_but_not_across_a_portal():
    rows = ["          ", "1        A          a     "]
    shots = [{"id": "a", "start": 0, "end": 1.3, "camera": {"mode": "follow", "target": "kai"}},
             {"id": "b", "start": 1.3, "end": 6, "camera": {"mode": "follow", "target": "kai"}}]
    p = proj([{"character": "kai", "type": "wait_beat", "beats": 3}, {"character": "kai", "type": "run_to", "target_x": 700}],
             rows, music={"bpm": 128}, shots=shots)
    rt, res, rep = qa(p)
    end = next(e for e in res.events if e.type == "beat_wait_end")
    assert end.data["beat"] == 3 and abs(end.t - 3 * 60 / 128) <= 1.0 / 240 + 1e-9
    assert rt.beat_log[0]["snapped"] and abs(rt.scene.shots[0].end - 3 * 60 / 128) < 1e-9
    checks = {c.name: c for c in rep.checks}
    assert checks["beat_cuts"].status == "PASS" and checks["beat_waits"].status == "PASS"


def test_snap_keeps_a_cut_that_is_on_a_portal_crossing():
    from apex.scene.beats import snap_shots
    from apex.render.timewarp import TimeWarp
    sc = N(music=N(bpm=120.0, offset=0.0, snap_window=0.5), duration=6.0,
           shots=[N(id="a", start=0.0, end=2.1, model_copy=lambda update: update), N(id="b", start=2.1, end=6.0, model_copy=lambda update: update)])

    class Ident:
        film_at = staticmethod(lambda t: t)
        sim_at = staticmethod(lambda t: t)
    out, log = snap_shots(sc, Ident, 24, locks=[2.1])
    assert log[0]["locked"] and not log[0]["snapped"]
    out, log = snap_shots(sc, Ident, 24)
    assert log[0]["snapped"] and log[0]["after"] == 2.0


def test_the_beat_track_puts_a_kick_on_every_beat():
    from apex.audio.sound_director import SR, Synth, kick_wave
    x = Synth(3).beat_track(N(bpm=100.0, offset=0.25, beats_per_bar=4, gain=1.0), 6.0)
    k = kick_wave()[: int(0.08 * SR)]
    for j in range(8):
        b = 0.25 + j * 0.6
        i0 = int((b - 0.03) * SR)
        corr = np.correlate(x[i0: int((b + 0.03) * SR) + len(k)], k, mode="valid")
        assert abs((i0 + int(np.argmax(corr))) / SR - b) < 0.001


# ---------------------------------------------------------------- particles
def test_particles_are_deterministic_and_stateless():
    from apex.render.particles import Particles
    from apex.motion.controller import Event
    e = env(["1  o  "])
    evs = [Event(1.0, "orb_jump", "kai", {"orb": "jump1", "point": (0.0, 200.0)}),
           Event(1.2, "impact", "kai", {"normal_speed": 900.0, "point": (50.0, 0.0)}),
           Event(1.3, "footstep", "kai", {"point": (0.0, 0.0)})]
    a, b = Particles(evs, e, 7), Particles(list(reversed(evs)), e, 7)
    assert len(a.bursts) == 2  # only events that emit
    for t in (1.5, 1.1, 1.25, 1.0):  # any order: no hidden state
        assert a.at(t) == b.at(t)
    assert a.at(0.5) == [] and a.at(10.0) == []
    assert Particles(evs, e, 8).at(1.1) != a.at(1.1)  # the seed matters


# ---------------------------------------------------------------- gait (found by the orb level)
def test_a_braking_runner_never_puts_a_lifted_foot_back_down():
    from apex.motion.gait import Gait, GaitParams
    ts = np.linspace(0, 1.0, 241)
    v = np.clip(430 - 900 * np.maximum(0, ts - 0.2), 0, None)
    s = np.concatenate([[0.0], np.cumsum((v[1:] + v[:-1]) / 2 * np.diff(ts))])
    g = Gait(ts, s, v, GaitParams(), 1.0, (8.0, -8.0))
    for leg in (0, 1):
        plants = [p for (_, _, p) in g.stance_intervals(leg)]
        assert len(plants) == len(set(plants)), "a foot came back down on a plant it had left"
