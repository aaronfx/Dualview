"""Consecutive-obstacle autonomous traversal via chained native autochoreo. The engine selects the tactic per
obstacle (jump vs climb by height), clears every obstacle with no structure penetration and no controller violation,
and reaches the goal. Tests vary obstacle positions, heights, gaps and the start position (genuine autonomy)."""
import pytest

from apex.ai.obstacle_course import plan_course
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
from apex.scene.goals import matches
from apex.qa.inspector import Inspector
from apex.render.pipeline import build_camera

COURSES = [
    ([{"id": "r1", "center": [-200, 65], "size": [80, 130]},
      {"id": "r2", "center": [260, 100], "size": [80, 200]},
      {"id": "r3", "center": [720, 80], "size": [80, 160]}], -660, 250.0),
    ([{"id": "r1", "center": [-120, 55], "size": [80, 110]},
      {"id": "r2", "center": [420, 110], "size": [80, 220]}], -520, 300.0),
    ([{"id": "r1", "center": [-260, 75], "size": [80, 150]},
      {"id": "r2", "center": [120, 60], "size": [80, 120]},
      {"id": "r3", "center": [520, 95], "size": [80, 190]},
      {"id": "r4", "center": [980, 70], "size": [80, 140]}], -700, 270.0),
]


@pytest.mark.parametrize("obstacles,start_x,apex", COURSES)
def test_autonomous_course_clears_every_obstacle_without_penetration(obstacles, start_x, apex):
    scene, report = plan_course(obstacles, start_x=start_x, width=3600, max_jump_apex=apex)
    assert report["obstacles"] == len(obstacles)
    assert all(s["tactic"] for s in report["segments"])          # a native tactic was chosen for every obstacle
    p = ProjectSpec.model_validate(scene)
    rt = SceneRuntime(p, "s")
    sim = rt.simulate()
    # native movement safety: no controller violation, and the body never enters a structure (no walk-through)
    assert not [c.violation for c in sim.controllers.values() if c.violation]
    ins = Inspector(rt, build_camera(rt, p.width / p.height), p.fps, size=(p.width, p.height))
    ins.times = [i / p.fps for i in range(int(sim.duration * p.fps))]
    checks = {c.name: c for c in ins.run(check_determinism=False).checks}
    assert checks["body_outside_structures"].status == "PASS"
    # the actor actually traversed (real takeoffs/climbs) and recovered the core
    assert sum(1 for e in sim.events if e.type in ("takeoff", "climbed")) >= len(obstacles)
    assert any(matches("pick_up@iko[prop=core]", e) for e in sim.events)


def test_tactic_depends_on_obstacle_height():
    # a low obstacle is jumped; a tall one is climbed — the engine chooses, not a hardcoded move
    low, _ = plan_course([{"id": "r", "center": [0, 55], "size": [80, 110]}], start_x=-520, max_jump_apex=240)
    tall, _ = plan_course([{"id": "r", "center": [0, 130], "size": [80, 260]}], start_x=-520, max_jump_apex=240)
    assert "jump" in low["scenes"][0]["actions"][0].get("type", "") or any(
        "jump" in a.get("type", "") for a in low["scenes"][0]["actions"])
    # the tall obstacle's plan uses a climb tactic
    assert any(a.get("type") == "climb" for a in tall["scenes"][0]["actions"])
