"""APEX chooses the physical numbers: goals, the setup solver, event-timed cuts, patch repairs, field hints. All offline."""
import copy
import json

import pytest

from apex.scene.goals import derive_goals, parse_goal, progress
from apex.scene.schema import ProjectSpec

from .conftest import ROOT


def _push_scene(static=1.4, kinetic=0.9, mass=60.0, goals=None, shots=None, duration=8.0):
    """A small, non-Rescue scene: one character pushes a crate; nothing about it is tuned."""
    return {
        "schema_version": "0.1", "id": "push_test", "title": "push", "fps": 24, "seed": 3,
        "characters": [{"id": "a", "name": "A", "strength": 45000}],
        "environments": [{"id": "room", "room": {"width": 1600, "height": 700}, "dust": 0,
                          "props": [{"id": "crate", "kind": "crate", "position": [0, 31], "size": [150, 60], "mass": mass,
                                     "friction": kinetic, "static_friction": static}]}],
        "scenes": [{"id": "s", "environment": "room", "duration": duration,
                    "placements": [{"character": "a", "x": -300, "facing": 1}],
                    "actions": [{"character": "a", "type": "walk_to", "target_x": -120, "speed": 150},
                                {"character": "a", "type": "push", "target": "prop:crate", "effort": 1.2},
                                {"character": "a", "type": "struggle", "duration": 1.0},
                                {"character": "a", "type": "get_up"}],
                    "goals": goals if goals is not None else ["push_lost@a", "body_fall@a", "stood_up@a"],
                    "shots": shots or [{"id": "w", "start": 0, "end": duration, "kind": "wide",
                                        "camera": {"mode": "static", "center": [0, 200], "view_height": 700}}]}]}


# ---------------------------------------------------------------- goals
def test_goal_syntax_and_validation():
    assert parse_goal("pinned@milo[by=post]") == ("pinned", "milo", {"by": "post"})
    assert parse_goal("event:rope_snap") == ("rope_snap", None, {})
    with pytest.raises(ValueError):
        parse_goal("pinned milo")
    d = _push_scene(goals=["body_fall@nobody"])
    with pytest.raises(ValueError, match="unknown"):
        ProjectSpec.model_validate(d)


def test_derived_goals_come_from_the_action_list():
    sc = ProjectSpec.model_validate(_push_scene()).scenes[0]
    assert derive_goals(sc) == ["body_fall@a"]


def test_rope_slack_resolves_length_from_geometry():
    d = _push_scene()
    d["environments"][0]["props"].append({"id": "post", "kind": "post", "position": [-400, 101], "size": [16, 200], "mass": 40})
    d["environments"][0]["ropes"] = [{"id": "r", "a": "prop:post", "a_point": [0, 90], "b": "prop:crate", "b_local": [-40, 30], "slack": 50}]
    env = ProjectSpec.model_validate(d).environments[0]
    assert env.ropes[0].a_local == (0, 90)  # common spellings are accepted
    assert env.ropes[0].length == pytest.approx(((-400 - -40) ** 2 + (191 - 61) ** 2) ** 0.5 + 50, abs=0.01)


# ---------------------------------------------------------------- solver
def test_solver_makes_an_untuned_push_scene_play_without_touching_the_actions():
    from apex.scene.runtime import SceneRuntime
    from apex.scene.solver import solve
    proj = ProjectSpec.model_validate(_push_scene())
    with pytest.raises(ValueError):  # as written, the crate never breaks loose: struggling while standing
        SceneRuntime(proj, "s").simulate(physics_only=True)
    fixed, rep = solve(proj, "s", budget=40)
    assert rep.success, rep.summary()
    assert any(a["knob"] == "prop:crate.static_friction" for a in rep.adjustments)
    assert [a.model_dump() for a in fixed.scenes[0].actions] == [a.model_dump() for a in proj.scenes[0].actions]
    r = SceneRuntime(fixed, "s").simulate(physics_only=True)
    met, _, missing = progress(fixed.scenes[0].goals, r.events, before=fixed.scenes[0].duration)
    assert missing is None


def test_solver_reports_a_structural_problem_instead_of_faking_it():
    from apex.scene.solver import solve
    d = _push_scene(goals=["push_lost@a", "rope_snap"])  # there is no rope: no setting can produce it
    fixed, rep = solve(ProjectSpec.model_validate(d), "s", budget=12)
    assert not rep.success and rep.missing == "rope_snap"


def test_event_timed_cuts_land_on_simulated_events():
    from apex.scene.runtime import SceneRuntime
    from apex.scene.solver import resolve_cuts, solve
    shots = [{"id": "a", "start": 0, "end": 2, "camera": {"mode": "follow", "target": "a"}},
             {"id": "b", "start": 2, "end": 5, "cut_on": "event:push_lost@a", "cut_offset": 0.1, "camera": {"mode": "follow", "target": "a"}},
             {"id": "c", "start": 5, "end": 8, "cut_on": "event:stood_up@a", "camera": {"mode": "follow", "target": "a"}}]
    proj, rep = solve(ProjectSpec.model_validate(_push_scene(shots=shots)), "s", budget=40)
    assert rep.success
    out = resolve_cuts(proj, "s")
    ev = SceneRuntime(out, "s").simulate(physics_only=True).events
    lost = next(e.t for e in ev if e.type == "push_lost")
    up = next(e.t for e in ev if e.type == "stood_up")
    sh = {s.id: s for s in out.scenes[0].shots}
    assert sh["b"].start == pytest.approx(lost + 0.1, abs=1e-3) and sh["c"].start == pytest.approx(up, abs=1e-3)
    assert sh["a"].end == sh["b"].start and sh["c"].end == out.scenes[0].duration


# ---------------------------------------------------------------- race guards
def test_struggle_until_waits_for_the_event_and_a_missing_helper_is_not_waited_on_forever():
    from apex.scene.runtime import SceneRuntime
    from apex.scene.solver import solve
    d = _push_scene(goals=["body_fall@a", "stood_up@a"], duration=14.0)
    d["characters"].append({"id": "b", "name": "B"})
    d["scenes"][0]["placements"].append({"character": "b", "x": 500, "facing": -1})
    acts = d["scenes"][0]["actions"]
    acts[2] = {"character": "a", "type": "struggle", "until": "event:wave@b"}  # b waves after 6 s
    acts[3] = {"character": "a", "type": "get_up", "target": "char:b"}  # b never offers a hand
    acts += [{"character": "b", "type": "idle", "duration": 6.0}, {"character": "b", "type": "gesture", "target": "char:a", "gesture": "wave"}]
    proj, rep = solve(ProjectSpec.model_validate(d), "s", budget=40)
    ev = SceneRuntime(proj, "s").simulate(physics_only=True).events
    wave = next(e.t for e in ev if e.type == "wave")
    assert next(e.t for e in ev if e.type == "get_up_start") >= wave  # struggle waited for it (no 1.5 s default)
    assert any(e.type == "help_missed" for e in ev) and any(e.type == "stood_up" for e in ev)


# ---------------------------------------------------------------- director: patches, hints, replay of a recorded plan
def test_patch_repairs_and_field_hints():
    from apex.ai.director import StoryDirector, apply_patch
    doc = {"a": [1, 2], "b": {"c": 1}}
    out = apply_patch(doc, [{"op": "replace", "path": "/b/c", "value": 5}, {"op": "add", "path": "/a/-", "value": 3},
                            {"op": "remove", "path": "/a/0"}])
    assert out == {"a": [2, 3], "b": {"c": 5}} and doc == {"a": [1, 2], "b": {"c": 1}}
    d = _push_scene()
    d["scenes"][0]["actions"][1]["efort"] = 1.0
    try:
        ProjectSpec.model_validate(d)
    except Exception as e:
        assert "did you mean 'effort'" in StoryDirector._explain(e)


class _Replay:
    """A fake provider: replays fixed responses (no network). Records every prompt it was sent."""
    name, model = "replay", "replay"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def complete(self, system, user, max_tokens=8000):
        self.prompts.append(user)
        return self.replies.pop(0)


def test_director_accepts_a_patch_repair():
    from apex.ai.director import StoryDirector
    d = _push_scene()
    bad = copy.deepcopy(d)
    bad["scenes"][0]["actions"][1]["target"] = "prop:crat"
    patch = {"patch": [{"op": "replace", "path": "/scenes/0/actions/1/target", "value": "prop:crate"}]}
    fp = _Replay([json.dumps(bad), json.dumps(patch)])
    proj = StoryDirector(fp, max_repairs=2).plan("someone pushes a crate")
    assert proj.scenes[0].actions[1].target == "prop:crate" and "patch" in fp.prompts[1]


def test_recorded_ai_plan_that_failed_now_plays_through_apex_physics():
    """A plan the model wrote in an earlier (paid) run, replayed offline: it failed then; APEX now tunes it."""
    from apex.ai.director import StoryDirector
    rec = json.loads((ROOT / "docs" / "ai_runs" / "rescue_upgraded_v5_opus" / "raw_responses.json").read_text())
    d = StoryDirector(_Replay([rec[4]["raw_response"]]), max_repairs=0)
    proj = d.plan("The Rescue")
    assert d.engine_report[0]["success"]
    assert d.accepted_ai_plan is not None  # the model's own plan is kept, separately from the engine's changes


def test_goals_must_name_engine_events_and_patch_replace_can_add():
    from apex.ai.director import apply_patch
    with pytest.raises(ValueError, match="not an engine event"):
        ProjectSpec.model_validate(_push_scene(goals=["run_to@a"]))  # an action name, not an event
    assert apply_patch({"a": {}}, [{"op": "replace", "path": "/a/until", "value": 1}]) == {"a": {"until": 1}}
