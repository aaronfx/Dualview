"""Produce an original film autonomously from a natural-language brief, through the native APEX systems only
(choreography, physics, acting, environment, cinematography) — no paid LLM.

    python examples/autonomous_film.py "A lone courier scales a barrier, recovers the power core and escapes" \
        out/autonomous/courier.json

Writes the native ProjectSpec and a sidecar <name>.plan.json with the brief, parsed plan and objective trace.
Render it with: python -m apex.cli render <json> -o <mp4> --scale 1 --samples 1 --qa-json <qa> --review-dir <dir>
"""
import argparse
import json
from pathlib import Path

from apex.ai.autonomous_film import film_from_brief
from apex.scene.schema import ProjectSpec


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("brief")
    ap.add_argument("output", type=Path)
    ap.add_argument("--no-reduce-idle", action="store_true")
    a = ap.parse_args()
    raw, meta = film_from_brief(a.brief, reduce_idle=not a.no_reduce_idle)
    p = ProjectSpec.model_validate(raw)  # native validation
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(p.model_dump_json(indent=2, exclude_defaults=True), encoding="utf-8")
    a.output.with_suffix(".plan.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    sc = p.scenes[0]
    print(f"wrote {a.output}: '{p.title}' | world={meta['plan']['world']} partner={meta['plan']['partner']} "
          f"duration={sc.duration:.1f}s shots={len(sc.shots)} idle_repairs={meta['idle_repairs']}")


if __name__ == "__main__":
    main()
