"""Permanent regression tests for the engine bugs found while making CORE RUN (the Director's Cut), plus positive and
negative tests for every new QA check (each check must catch a genuine failure without rejecting valid animation).

See docs/PROBLEM_LOG.md: each test here is the "regression test" column of one logged problem. The frozen benchmark
examples/core_run_r4.json is the end-to-end counterpart (apex.qa.benchmark); these are the small, fast, isolated cases.
"""
import math

import pytest

from apex.qa.inspector import Inspector
from apex.render.pipeline import build_camera
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

CHARS = [{"id": "iko", "name": "IKO"}, {"id": "pell", "name": "PELL"}]
CORE = {"id": "core", "kind": "glyph", "glyph": "0", "position": [-400.0, 340.0], "size": [34.0, 34.0],
        "mass": 2.0, "weight": 12.0, "color": "#7dfcff", "z": 0.0, "depth": 16.0, "solid": False}


def build(scenes, obstacles=(), props=(), exits=(), room=None):
    env = {"id": "e", "room": room or {"width": 2000, "height": 900, "entry_door": False}, "dust": 0,
           "obstacles": list(obstacles), "props": list(props), "exits": list(exits)}
    for sc in scenes:
        sc.setdefault("environment", "e")
        sc.setdefault("shots", [{"id": "a", "start": 0, "end": sc["duration"],
                                 "camera": {"mode": "static", "center": [0, 300], "view_height": 900}}])
    return ProjectSpec.model_validate({"schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360,
                                       "seed": 3, "characters": CHARS, "environments": [env], "scenes": scenes})


def run(p, sid):
    rt = SceneRuntime(p, sid)
    res = rt.simulate()
    return rt, res


def checks(rt, p):
    rep = Inspector(rt, build_camera(rt, p.width / p.height), p.fps, size=(p.width, p.height)).run(check_determinism=False)
    return {c.name: c for c in rep.checks}


def ev_types(res, who=None):
    return [e.type for e in res.events if who is None or e.character == who]


# two platforms with a gap, a glyph resting on the left one, IKO standing on the left one carrying it
TWO_TOPS = [{"id": "left", "kind": "platform", "center": [-400, 300], "size": [360, 40]},
            {"id": "right", "kind": "platform", "center": [320, 300], "size": [360, 40]}]


def carry_jump_project(dur=3.4, extra_actions=()):
    sc = {"id": "s", "duration": dur,
          "placements": [{"character": "iko", "x": -460, "on": "obstacle:left", "carrying": "prop:core"}],
          "actions": [{"character": "iko", "type": "run_to", "target_x": -240, "speed": 340},
                      {"character": "iko", "type": "jump_to", "target_x": 320, "height": 240, "onto": "obstacle:right"},
                      *extra_actions]}
    return build([sc], obstacles=TWO_TOPS, props=[CORE])


# --------------------------------------------------------------------------- engine-bug regressions

def test_carried_core_stays_in_hands_through_a_jump():
    """BUG: the carried core was updated only while the carrier was on the ground, so it was left hanging in mid-air
    when he jumped between platforms. It must now follow the body through the whole flight."""
    p = carry_jump_project()
    rt, res = run(p, "s")
    c = checks(rt, p)["carried_object_continuity"]
    assert c.status == "PASS", (c.details, c.diag)
    # and the core actually went up with him: its highest point is well above the platform top it started on
    tr = res.prop_tracks["core"]
    assert tr[:, 1].max() > 340 + 120, f"core never rose with the jump (peak y {tr[:, 1].max():.0f})"


def test_carried_core_leaves_through_the_exit_and_is_gone():
    """BUG: at a scene-exit gate the carried core was left floating where the carrier vanished. The carrier must take it
    out through the door (a carried_out event) and the prop must no longer be in the scene afterwards."""
    exits = [{"id": "gate", "surface": "wall_right", "s": 300.0, "width": 260, "sealed": False, "open_radius": 320}]
    sc = {"id": "s", "duration": 3.2,
          "placements": [{"character": "iko", "x": -200, "carrying": "prop:core"}],
          "actions": [{"character": "iko", "type": "reach_exit", "target": "exit:gate", "speed": 340}]}
    p = build([sc], props=[CORE], exits=exits, room={"width": 900, "height": 700, "entry_door": False})
    rt, res = run(p, "s")
    assert "carried_out" in ev_types(res), ev_types(res)
    assert "core" in res.carried_out
    out_t = res.carried_out["core"]
    assert not res.alive("core", out_t + 0.1), "the core is still in the scene after its carrier took it out"
    c = checks(rt, p)
    assert c["carried_object_continuity"].status == "PASS"
    assert c["props_not_floating"].status == "PASS", c["props_not_floating"].diag


def test_knockdown_drops_the_carried_core():
    """BUG/behaviour: a carrier knocked down must let go of what he carries (it becomes a free body), not keep it glued
    to his hands while he falls."""
    sc = {"id": "s", "duration": 3.2,
          "placements": [{"character": "iko", "x": -120, "carrying": "prop:core"},
                         {"character": "pell", "x": 120, "facing": -1}],
          "actions": [{"character": "pell", "type": "strike", "target": "char:iko", "move": "sweep",
                       "power": 1.3, "reaction": "knockdown", "distance": 70}]}
    p = build([sc], props=[CORE], room={"width": 1200, "height": 800, "entry_door": False})
    rt, res = run(p, "s")
    assert "knockdown" in ev_types(res), ev_types(res)
    # the carry span ended (a release of some kind was logged)
    span = next((s for cc in res.controllers.values() for s in getattr(cc, "carry_log", [])), None)
    assert span is not None and span[2] < math.inf, "the core was never released on the knockdown"


def test_place_seats_the_core_on_a_holder_not_floating():
    """BUG: a placed core had to end resting on its holder, not hovering. `place` sets it on the target surface."""
    holder = [{"id": "left", "kind": "platform", "center": [-400, 300], "size": [360, 40]},
              {"id": "socket", "kind": "platform", "center": [-120, 300], "size": [120, 40]}]
    sc = {"id": "s", "duration": 4.5,
          "placements": [{"character": "iko", "x": -360, "on": "obstacle:left", "carrying": "prop:core"}],
          "actions": [{"character": "iko", "type": "place", "target": "obstacle:socket"}]}
    p = build([sc], obstacles=holder, props=[CORE])
    rt, res = run(p, "s")
    assert "place" in ev_types(res), ev_types(res)
    assert checks(rt, p)["props_not_floating"].status == "PASS", "the placed core is reported as floating"


def test_glass_material_accepted_by_schema():
    """BUG: glass panes needed a material the schema rejected; `material: glass` must validate."""
    glass = dict(CORE, id="pane", material="glass")
    sc = {"id": "s", "duration": 1.0, "placements": [{"character": "iko", "x": 0}],
          "actions": [{"character": "iko", "type": "idle", "duration": 1.0}]}
    p = build([sc], props=[glass])  # validates or raises
    assert any(pr.id == "pane" for pr in p.environments[0].props)


# --------------------------------------------------------------------------- QA checks: positive + negative

def test_continuity_positive_then_negative():
    """carried_object_continuity: PASSes on a real carry; FAILs when the prop is stranded away from the carrier."""
    p = carry_jump_project()
    rt, res = run(p, "s")
    assert checks(rt, p)["carried_object_continuity"].status == "PASS"
    # negative: pin the carried prop far from the carrier for the whole carry
    rt2, _ = run(carry_jump_project(), "s")
    for an in rt2.result.animators.values():
        an.prop_at = lambda pid, t: (9000.0, 9000.0, 0.0)
    c = checks(rt2, p)["carried_object_continuity"]
    assert c.status == "FAIL" and c.diag, "a stranded carried prop was not detected"


def place_project():
    holder = [{"id": "left", "kind": "platform", "center": [-400, 300], "size": [360, 40]},
              {"id": "socket", "kind": "platform", "center": [-120, 300], "size": [120, 40]}]
    sc = {"id": "s", "duration": 4.5,
          "placements": [{"character": "iko", "x": -360, "on": "obstacle:left", "carrying": "prop:core"}],
          "actions": [{"character": "iko", "type": "place", "target": "obstacle:socket"}]}
    return build([sc], obstacles=holder, props=[CORE])


def test_floating_positive_then_negative():
    """props_not_floating: PASSes when a placed/carried core rests on a surface; FAILs when a posed core hangs in air."""
    p = place_project()
    rt, res = run(p, "s")
    assert "place" in ev_types(res)
    assert checks(rt, p)["props_not_floating"].status == "PASS"
    # negative: end the carry early but leave the core posed (kinematic) high above any support — the exact stranded-
    # at-the-gate failure. After 0.5 s the core is no longer carried, yet it hangs at y=800 with nothing under it.
    rt2, res2 = run(carry_jump_project(), "s")
    for cc in res2.controllers.values():
        for span in getattr(cc, "carry_log", []):
            span[2] = 0.5
    res2.prop_kinematic["core"][:] = True
    res2.prop_tracks["core"][:, 1] = 800.0
    c = checks(rt2, p)["props_not_floating"]
    assert c.status == "FAIL" and c.diag, "a posed, unsupported prop in mid-air was not detected"


def test_screen_overlap_positive_then_negative():
    """characters_not_overlapping: PASSes when two characters are staged apart; WARNs when one buries the other."""
    apart = {"id": "s", "duration": 1.2,
             "placements": [{"character": "iko", "x": -300}, {"character": "pell", "x": 300}],
             "actions": [{"character": "iko", "type": "idle", "duration": 1.2}, {"character": "pell", "type": "idle", "duration": 1.2}]}
    p = build([apart])
    rt, _ = run(p, "s")
    assert checks(rt, p)["characters_not_overlapping"].status == "PASS"
    # negative: same x, same depth lane -> the two silhouettes sit on top of each other
    stacked = {"id": "s", "duration": 1.2,
               "placements": [{"character": "iko", "x": 0, "z": 0}, {"character": "pell", "x": 0, "z": 0}],
               "actions": [{"character": "iko", "type": "idle", "duration": 1.2}, {"character": "pell", "type": "idle", "duration": 1.2}]}
    rt2, _ = run(build([stacked]), "s")
    assert checks(rt2, build([stacked]))["characters_not_overlapping"].status == "WARN"


def test_narrative_order_positive_then_negative():
    """narrative_order: PASSes when the scripted beats happen in the listed order; WARNs when they cannot."""
    # iko performs an emotional beat up front (~0 s); pell strikes well over a second later — clearly ordered beats,
    # more than the near-simultaneous tolerance apart.
    base = dict(placements=[{"character": "iko", "x": -120}, {"character": "pell", "x": 150, "facing": -1}],
                actions=[{"character": "iko", "type": "act", "clip": "cheer", "duration": 0.8, "emotion": "joyful"},
                         {"character": "pell", "type": "idle", "duration": 1.4},
                         {"character": "pell", "type": "strike", "target": "char:iko", "move": "sweep", "power": 1.3,
                          "reaction": "knockdown", "distance": 70}])
    good = {"id": "s", "duration": 4.0, "goals": ["act@iko", "strike_start@pell"], **base}
    p = build([good], room={"width": 1200, "height": 800, "entry_door": False})
    rt, _ = run(p, "s")
    assert checks(rt, p)["narrative_order"].status == "PASS"
    # negative: demand the beats in the impossible order (the late strike before the early acting beat)
    bad = {"id": "s", "duration": 4.0, "goals": ["strike_start@pell", "act@iko"], **base}
    pb = build([bad], room={"width": 1200, "height": 800, "entry_door": False})
    rtb, _ = run(pb, "s")
    assert checks(rtb, pb)["narrative_order"].status == "WARN"


def test_narrative_causality_positive_then_negative():
    """narrative_causality: PASSes when every effect has its cause; WARNs when an effect appears without one."""
    sc = {"id": "s", "duration": 3.2,
          "placements": [{"character": "iko", "x": -120}, {"character": "pell", "x": 140, "facing": -1}],
          "actions": [{"character": "pell", "type": "strike", "target": "char:iko", "move": "sweep", "power": 1.3,
                       "reaction": "knockdown", "distance": 70}]}
    p = build([sc], room={"width": 1200, "height": 800, "entry_door": False})
    rt, res = run(p, "s")
    assert checks(rt, p)["narrative_causality"].status == "PASS"
    # negative: inject a knockdown with no strike/hit/throw before it
    from apex.motion.controller import Event
    rt2, res2 = run(build([dict(sc, id="s")], room={"width": 1200, "height": 800, "entry_door": False}), "s")
    res2.events[:] = [e for e in res2.events if e.type not in ("strike_start", "hit", "prop_hit", "throw")]
    res2.events.append(Event(2.0, "knockdown", "iko", {"point": (0.0, 100.0)}))
    res2.events.sort(key=lambda e: (e.t, e.type))
    c = checks(rt2, p)["narrative_causality"]
    assert c.status == "WARN" and c.diag, "an uncaused knockdown was not detected"


def test_decisive_event_visible_positive_then_negative():
    """decisive_events_visible: PASSes when a scripted beat is framed; WARNs when it happens off screen."""
    sc = {"id": "s", "duration": 3.2, "goals": ["knockdown@iko"],
          "placements": [{"character": "iko", "x": -120}, {"character": "pell", "x": 140, "facing": -1}],
          "actions": [{"character": "pell", "type": "strike", "target": "char:iko", "move": "sweep", "power": 1.3,
                       "reaction": "knockdown", "distance": 70}]}
    p = build([sc], room={"width": 1200, "height": 800, "entry_door": False})
    rt, res = run(p, "s")
    assert checks(rt, p)["decisive_events_visible"].status == "PASS"
    # negative: move the decisive beat far outside the framed area
    rt2, res2 = run(build([dict(sc, id="s")], room={"width": 1200, "height": 800, "entry_door": False}), "s")
    for e in res2.events:
        if e.type == "knockdown":
            e.data["point"] = (99999.0, 99999.0)
    c = checks(rt2, p)["decisive_events_visible"]
    assert c.status == "WARN" and c.diag, "an off-screen decisive beat was not detected"


def test_diagnostics_are_structured_and_serialisable():
    """Every failing/warning new check carries machine-readable diagnostics (time, entities, positions, state, cause)."""
    import json
    rt2, _ = run(carry_jump_project(), "s")
    for an in rt2.result.animators.values():
        an.prop_at = lambda pid, t: (9000.0, 9000.0, 0.0)
    rep = Inspector(rt2, build_camera(rt2, 640 / 360), 24, size=(640, 360)).run(check_determinism=False)
    c = next(c for c in rep.checks if c.name == "carried_object_continuity")
    assert c.diag and {"t", "who", "where", "state", "cause"} <= set(c.diag[0])
    json.dumps([dict(name=c.name, diag=c.diag) for c in rep.checks])  # the whole report serialises
