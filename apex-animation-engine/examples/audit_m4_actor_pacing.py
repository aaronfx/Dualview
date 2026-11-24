"""Audit a validated APEX film's actor time budget against native simulation.

Usage:
  python examples/audit_m4_actor_pacing.py out/m4/impossible_crossing_m4.json out/m4/pacing_report.json

Exit code 2 if an actor exceeds the allowed unmotivated pause budget. This
creates a measurable *technical* acceptance signal; it is NOT an artistic score.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from apex.qa.actor_pacing import audit_character
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    source, target = Path(argv[0]), Path(argv[1])
    project = ProjectSpec.model_validate_json(source.read_text(encoding="utf-8"))
    reports = {}
    for scene in project.scenes:
        sim = SceneRuntime(project, scene.id).simulate(physics_only=True)
        for char in {p.character for p in scene.placements}:
            key = f"{scene.id}/{char}"
            reports[key] = audit_character(sim, char).to_dict()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"project": project.id, "actors": reports}, indent=2), encoding="utf-8")
    for actor, rep in sorted(reports.items()):
        print(f"{actor}: wasted={rep['wasted_seconds']:.3f}s, deliberate={rep['deliberate_seconds']:.3f}s, "
              f"longest={rep['longest_wasted']:.3f}s, gate={'PASS' if rep['passed'] else 'FAIL'}")
    return 0 if all(r["passed"] for r in reports.values()) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
