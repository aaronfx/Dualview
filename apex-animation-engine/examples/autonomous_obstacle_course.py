"""Reproduce the CORE RUN consecutive-obstacle sequence from a high-level objective: cross a series of obstacles to
recover the power core. The engine independently selects running/jumping/vaulting/climbing/landing per obstacle via
the verified native autochoreo tactic search (no copied choreography, no new obstacle logic).

    python examples/autonomous_obstacle_course.py out/reference_grade/obstacle_course.json
"""
import argparse
import json
from pathlib import Path

from apex.ai.obstacle_course import plan_course
from apex.scene.schema import ProjectSpec

# a rooftop course: different heights, gaps and positions
COURSE = [{"id": "roof1", "center": [-200.0, 65.0], "size": [80.0, 130.0]},
          {"id": "roof2", "center": [260.0, 100.0], "size": [80.0, 200.0]},
          {"id": "roof3", "center": [720.0, 80.0], "size": [80.0, 160.0]}]
TOWER = {"kind": "tower", "art_profile": "industrial_depth", "seed": 42, "weather": "motes", "weather_amount": 0.28,
         "sky": ["#080e19", "#1b3040", "#304853"], "fog": "#20313b"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path)
    ap.add_argument("--jump-apex", type=float, default=250.0)
    a = ap.parse_args()
    scene, report = plan_course(COURSE, start_x=-660.0, width=3400.0, max_jump_apex=a.jump_apex)
    scene["environments"][0]["backdrop"] = TOWER
    p = ProjectSpec.model_validate(scene)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(p.model_dump_json(indent=2, exclude_defaults=True), encoding="utf-8")
    a.output.with_suffix(".plan.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {a.output}: {report['obstacles']} obstacles, engine-selected tactics "
          + ", ".join(f"{s['obstacle']}(h{s['height']})={s['tactic']}" for s in report["segments"]))


if __name__ == "__main__":
    main()
