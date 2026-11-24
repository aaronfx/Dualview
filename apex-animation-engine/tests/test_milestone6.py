"""Milestone 6: acting, collapsing structures, ledge catches and rescues, the retry system, the HUD, exits that need
everyone, and multi-scene films."""
import json
import os

import pytest

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

CHARS = [{"id": "iko", "name": "IKO"}, {"id": "pell", "name": "PELL"}]


def proj(scenes, obstacles=(), exits=(), dur=None, room=None, **env_extra):
    env = {"id": "e", "room": room or {"width": 1800, "height": 900, "entry_door": False}, "dust": 0,
           "obstacles": list(obstacles), "exits": list(exits)}
    env.update(env_extra)
    for sc in scenes:
        sc.setdefault("environment", "e")
        sc.setdefault("shots", [{"id": "a", "start": 0, "end": sc["duration"], "camera": {"mode": "static", "center": [0, 300],
                                                                                         "view_height": 900}}])
    return ProjectSpec.model_validate({"schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360,
                                       "seed": 3, "characters": CHARS, "environments": [env], "scenes": scenes})


def qa(p, sid):
    from apex.qa.inspector import Inspector
    from apex.render.pipeline import build_camera
    rt = SceneRuntime(p, sid)
    res = rt.simulate()
    rep = Inspector(rt, build_camera(rt, p.width / p.height), p.fps).run(check_determinism=False)
    return rt, res, {c.name: c for c in rep.checks}


def types(res, who=None):
    return [e.type for e in res.events if who is None or e.character == who]


BRIDGE = [{"id": "left", "kind": "platform", "center": [-600, 260], "size": [400, 40]},
          {"id": "bridge", "kind": "platform", "center": [-180, 270], "size": [440, 20], "collapse": {"under": "pell", "after": 2.4}},
          {"id": "right", "kind": "platform", "center": [300, 260], "size": [520, 40]}]


def rescue_scene(hang):
    return {"id": "s", "duration": 11.0,
            "placements": [{"character": "pell", "x": -650, "on": "obstacle:left"}, {"character": "iko", "x": 250, "facing": -1, "on": "obstacle:right"}],
            "actions": [{"character": "pell", "type": "walk_to", "target_x": 200}, {"character": "pell", "type": "catch_ledge", "target": "obstacle:right"},
                        hang, {"character": "pell", "type": "idle", "duration": 2},
                        {"character": "iko", "type": "wait_for", "until": "event:ledge_catch@pell"},
                        {"character": "iko", "type": "pull_up", "target": "char:pell"}]}


# ---------------------------------------------------------------- collapse, ledge catch, rescue
def test_a_collapse_drops_its_stander_who_catches_the_ledge_and_is_pulled_up_hand_in_hand():
    p = proj([rescue_scene({"character": "pell", "type": "hang", "slip_at": 1.0, "distance": 12})], BRIDGE)
    rt, res, ch = qa(p, "s")
    ev = types(res)
    for a, b in (("collapse", "ledge_catch"), ("ledge_catch", "hang_slip"), ("hang_slip", "hand_grab"), ("hand_grab", "pulled_up")):
        assert ev.index(a) < ev.index(b), (a, b)
    for name in ("hands_meet", "feet_on_tops", "body_outside_structures"):
        assert ch[name].status == "PASS", ch[name].details
    assert ch["hands_meet"].metric < 10
    c = res.controllers["pell"]
    assert c.frame.owner == "right" and c.mode == "grounded"
    assert abs(res.controllers["iko"].s - c.s) > 40  # the rescuer stepped back as he pulled: they do not end in one spot


def test_a_hanging_character_can_climb_up_alone():
    p = proj([dict(rescue_scene({"character": "pell", "type": "hang", "duration": 1.5}), actions=[
        {"character": "pell", "type": "walk_to", "target_x": 200}, {"character": "pell", "type": "catch_ledge", "target": "obstacle:right"},
        {"character": "pell", "type": "hang", "duration": 1.5}, {"character": "pell", "type": "idle", "duration": 2}])], BRIDGE)
    res = SceneRuntime(p, "s").simulate(physics_only=True)
    ev = types(res, "pell")
    assert "ledge_catch" in ev and "climbed" in ev and "hand_grab" not in ev
    assert res.controllers["pell"].frame.owner == "right"


def test_a_collapse_goes_at_the_first_of_its_triggers():
    obs = [{"id": "pad", "kind": "platform", "center": [0, 200], "size": [300, 20],
            "collapse": {"under": "iko", "after": 20.0, "at": 1.0}}]
    p = proj([{"id": "s", "duration": 3.0, "placements": [{"character": "iko", "x": 0, "on": "obstacle:pad"}], "actions": []}], obs)
    res = SceneRuntime(p, "s").simulate(physics_only=True)
    t = [e.t for e in res.events if e.type == "collapse"]
    assert len(t) == 1 and abs(t[0] - 1.0) < 0.01  # the time came first; it collapses once
    assert "step_off" in types(res, "iko")


# ---------------------------------------------------------------- acting
def test_acting_clips_play_and_event_waits_can_filter_on_the_clip():
    acts = [{"character": "iko", "type": "act", "clip": c, "duration": 1.2, "emotion": e}
            for c, e in (("cheer", "joyful"), ("laugh", "joyful"), ("despair", "sad"), ("kneel_look", "sad"), ("rise", "determined"))]
    acts += [{"character": "pell", "type": "wait_for", "until": "event:act@iko[clip=despair]"},
             {"character": "pell", "type": "act", "clip": "shock", "emotion": "scared", "tremble": 0.6, "duration": 1.0}]
    p = proj([{"id": "s", "duration": 8.0, "placements": [{"character": "iko", "x": -200}, {"character": "pell", "x": 200, "facing": -1}],
               "actions": acts}])
    rt, res, ch = qa(p, "s")
    clips = [e.data["clip"] for e in res.events if e.type == "act" and e.character == "iko"]
    assert clips == ["cheer", "laugh", "despair", "kneel_look", "rise"]
    t_despair = next(e.t for e in res.events if e.type == "act" and e.data["clip"] == "despair")
    t_shock = next(e.t for e in res.events if e.type == "act" and e.character == "pell")
    assert abs(t_shock - t_despair) < 0.05  # PELL waited for that clip, not for IKO's first act
    assert all(c.status != "FAIL" for c in ch.values()), [n for n, c in ch.items() if c.status == "FAIL"]


# ---------------------------------------------------------------- retry system, HUD, exits
def test_a_fall_out_of_the_level_is_a_fail_and_the_hud_counts_it():
    from apex.render.hud import Hud
    p = proj([{"id": "s", "duration": 4.0, "placements": [{"character": "iko", "x": -700, "on": "obstacle:left"}],
               "fail": {"below": 180}, "hud": {"retries": 3, "messages": [{"text": "RETRY", "on": "event:fail@iko", "duration": 1.0}]},
               "actions": [{"character": "iko", "type": "walk_to", "target_x": -150}]}],
             [{"id": "left", "kind": "platform", "center": [-600, 300], "size": [500, 40]}])
    res = SceneRuntime(p, "s").simulate(physics_only=True)
    fails = [e for e in res.events if e.type == "fail"]
    assert len(fails) == 1 and fails[0].data["point"][1] < 180
    h = Hud(p.scenes[0], res.events)
    assert h.at(fails[0].t - 0.1).retries == 3 and h.at(fails[0].t + 0.1).retries == 2
    assert h.at(fails[0].t + 0.1).flash > 0.5 and any(m[0] == "RETRY" for m in h.at(fails[0].t + 0.5).messages)


def test_a_together_exit_opens_only_for_everyone_at_once():
    ex = [{"id": "door", "surface": "wall_right", "s": 110, "unlock_on": "together:iko,pell", "open_radius": 260}]
    def scene(pell_x):
        return {"id": "s", "duration": 8.0, "placements": [{"character": "iko", "x": 300}, {"character": "pell", "x": -200}],
                "actions": [{"character": "iko", "type": "walk_to", "target_x": 760}, {"character": "pell", "type": "walk_to", "target_x": pell_x}]}
    alone = SceneRuntime(proj([scene(200)], exits=ex), "s").simulate(physics_only=True)
    assert "exit_together" not in types(alone) and alone.doors["door"]["unlock_t"] is None
    rt, res, ch = qa(proj([scene(660)], exits=ex), "s")
    assert "exit_together" in types(res) and res.doors["door"]["open_t"] is not None
    assert ch["door_state_machine[door]"].status == "PASS"


def test_film_checks_hold_retries_to_one_checkpoint_and_the_counter():
    from apex.qa.film import check_film
    plat = [{"id": "left", "kind": "platform", "center": [-600, 300], "size": [500, 40]}]
    def attempt(id_, retries, x=-700, **kw):
        return dict({"id": id_, "duration": 3.5, "placements": [{"character": "iko", "x": x, "on": "obstacle:left"}],
                     "fail": {"below": 180}, "hud": {"retries": retries}, "actions": [{"character": "iko", "type": "walk_to", "target_x": -150}]}, **kw)
    good = proj([attempt("a", 3), attempt("b", 2, retry_of="a", transition_in="rewind")], plat)
    assert all(c.status == "PASS" for c in check_film(good))
    bad = proj([attempt("a", 3), attempt("b", 3, x=-650, retry_of="a", transition_in="rewind")], plat)
    st = {c.name: c.status for c in check_film(bad)}
    assert st == {"retry_resets_consistent": "FAIL", "retry_counter_consistent": "FAIL"}


def test_a_film_joins_its_scenes_with_a_rewind_built_from_the_failed_attempt(tmp_path):
    from apex.render.film import FREEZE_T, REWIND_T, render_film
    from apex.render.video import probe
    plat = [{"id": "left", "kind": "platform", "center": [-600, 300], "size": [500, 40]}]
    sc = {"placements": [{"character": "iko", "x": -700, "on": "obstacle:left"}], "fail": {"below": 180}, "duration": 3.0,
          "actions": [{"character": "iko", "type": "walk_to", "target_x": -150}]}
    p = proj([dict(sc, id="a", hud={"retries": 2}), dict(sc, id="b", retry_of="a", transition_in="rewind", hud={"retries": 1})], plat)
    out = str(tmp_path / "film.mp4")
    r = render_film(p, out, preview_scale=0.5, qa=False)
    d = float(probe(out)["format"]["duration"])
    assert abs(d - (6.0 + FREEZE_T + REWIND_T)) < 0.3 and abs(r.duration - d) < 1e-6
    assert [m.scene for m in r.scenes] == ["a", "b"] and r.peak_rss_mb > 0
    assert {c["name"]: c["status"] for c in r.film_checks}["retry_resets_consistent"] == "PASS"
