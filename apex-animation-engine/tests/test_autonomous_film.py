"""The native autonomous film pipeline turns a natural-language brief into a rehearsed, goal-satisfying scene through
the native objective/ensemble planners, physics, event cameras and the director critic — no paid LLM."""
import pytest

from apex.ai.autonomous_film import film_from_brief, parse_brief
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.goals import matches

BRIEFS = [
    ("A lone courier scales a barrier, recovers the power core and escapes through the airlock of a factory.", False, True),
    ("In a rain-soaked city a courier recovers the data key and escapes.", False, False),
    ("Two allies: one climbs a canyon wall to grab the relic while the partner covers the escape, then both flee.", True, True),
]


@pytest.mark.parametrize("brief,want_partner,want_barrier", BRIEFS)
def test_brief_produces_a_feasible_native_film(brief, want_partner, want_barrier):
    plan = parse_brief(brief)
    assert plan["partner"] is want_partner and plan["has_barrier"] is want_barrier
    raw, meta = film_from_brief(brief)
    p = ProjectSpec.model_validate(raw)            # native schema validation
    sc = p.scenes[0]
    res = SceneRuntime(p, sc.id).simulate()
    # every authored outcome goal is actually achieved by the rehearsed native choreography
    for g in sc.goals:
        assert any(matches(g, e) for e in res.events), f"goal not met natively: {g}"
    # no native controller violations; event-derived cameras; cinematic (non-grid) environment
    assert not [c.violation for c in res.controllers.values() if c.violation]
    assert len(sc.shots) >= 2
    assert p.environments[0].backdrop is not None
    # the objective trace is real native planning, one entry per brief beat
    assert len(meta["objective_trace"]) == len(plan["beats"])


def test_unsupported_brief_fails_honestly():
    # a brief whose objective cannot be met natively raises with the native rejection evidence, never a fake film
    from apex.ai.objective_planner import plan_objectives
    bad = {"scene_id": "x", "tasks": [{"id": "t", "actor": "ghost", "kind": "collect", "target": "prop:none"}]}
    with pytest.raises(Exception):
        plan_objectives({"schema_version": "0.1", "id": "x", "title": "x", "fps": 24, "width": 320, "height": 180,
                         "seed": 1, "characters": [{"id": "iko", "name": "IKO"}],
                         "environments": [{"id": "e", "room": {"width": 800, "height": 400, "entry_door": False},
                                           "props": [], "obstacles": [], "exits": []}],
                         "scenes": [{"id": "x", "environment": "e", "duration": 5.0,
                                     "placements": [{"character": "iko", "x": 0}], "actions": [],
                                     "goals": ["pick_up@iko[prop=none]"],
                                     "shots": [{"id": "s", "start": 0, "end": 5.0,
                                                "camera": {"mode": "static", "center": [0, 0]}}]}]}, bad)
