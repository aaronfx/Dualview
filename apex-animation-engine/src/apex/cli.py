"""Command line interface: `apex validate|render|qa|plan|serve|schema`."""
from __future__ import annotations

import argparse
import json
import sys
import time


def _load(path: str):
    from .scene.schema import ProjectSpec
    with open(path, encoding="utf-8") as fh:
        return ProjectSpec.model_validate(json.load(fh))


def _progress(stage: str, frac: float, msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {stage:8s} {frac * 100:5.1f}%  {msg}", flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="apex", description="APEX animation engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="validate a project JSON against the scene schema")
    v.add_argument("project")
    r = sub.add_parser("render", help="simulate + render one scene to MP4 (with QA)")
    r.add_argument("project")
    r.add_argument("--scene", help="scene id (default: first scene)")
    r.add_argument("-o", "--out", required=True)
    r.add_argument("--samples", type=int, default=1, help="motion-blur sub-samples per frame")
    r.add_argument("--scale", type=float, default=1.0, help="preview resolution scale (e.g. 0.5)")
    r.add_argument("--no-qa", action="store_true")
    r.add_argument("--qa-json", help="write the QA report here")
    r.add_argument("--review-dir", help="write contact sheet, diagnostics (JSON + chart) and decode report here")
    p = sub.add_parser("plan", help="AI Story Director: story text -> validated project JSON")
    p.add_argument("story")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--offline", action="store_true", help="use the deterministic template planner (no AI provider)")
    p.add_argument("--log-dir", help="preserve every raw model response, the repair errors and the accepted plan here")
    s = sub.add_parser("serve", help="run the FastAPI backend")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8077)
    sub.add_parser("schema", help="print the JSON schema")
    rv = sub.add_parser("review", help="write a human-review packet (rubric + objective metrics) for a render")
    rv.add_argument("project")
    rv.add_argument("out_dir")
    rv.add_argument("--scene")
    rv.add_argument("--video")
    rv.add_argument("--qa-json")
    rv.add_argument("--ai", action="store_true", help="add AI Director correction suggestions (needs a configured provider)")
    a = ap.parse_args(argv)

    if a.cmd == "validate":
        proj = _load(a.project)
        print(f"OK: {proj.id} ({len(proj.scenes)} scene(s), {len(proj.characters)} character(s))")
        return 0
    if a.cmd == "schema":
        from .scene.schema import json_schema
        print(json.dumps(json_schema(), indent=1))
        return 0
    if a.cmd == "render":
        from .render.pipeline import render_scene
        proj = _load(a.project)
        sid = a.scene or proj.scenes[0].id
        res = render_scene(proj, sid, a.out, samples=a.samples, qa=not a.no_qa, preview_scale=a.scale, progress=_progress, qa_path=a.qa_json, review_dir=a.review_dir)
        print(f"wrote {res.video} ({res.frames} frames) in {res.seconds:.1f}s")
        if res.qa:
            print(res.qa.summary())
            return 0 if res.qa.passed else 2
        return 0
    if a.cmd == "review":
        from .qa.review import build_review_packet
        proj = _load(a.project)
        md = build_review_packet(proj, a.scene or proj.scenes[0].id, a.out_dir, a.video, a.qa_json, with_ai=a.ai)
        print(f"wrote {md} and review_scores.json (human reviewers score; metrics are listed separately)")
        return 0
    if a.cmd == "plan":
        from .ai.director import StoryDirector
        import json as _json
        import os as _os
        import time as _time
        director = StoryDirector.from_env(offline=a.offline)
        t0 = _time.time()
        result = {"story": a.story, "planner": director.name, "model": getattr(director.provider, "model", None),
                  "started_utc": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())}
        try:
            proj = director.plan(a.story)
            result["status"] = "accepted"
        except Exception as e:  # preserve the failure as well
            result.update(status="failed", error=f"{type(e).__name__}: {e}"[:4000])
            proj = None
        result.update(attempts=len(director.log), seconds=round(_time.time() - t0, 1))
        if a.log_dir:
            _os.makedirs(a.log_dir, exist_ok=True)
            from .ai.director import system_prompt
            with open(_os.path.join(a.log_dir, "raw_responses.json"), "w", encoding="utf-8") as fh:
                _json.dump(director.log, fh, indent=1)
            with open(_os.path.join(a.log_dir, "system_prompt.txt"), "w", encoding="utf-8") as fh:
                fh.write(system_prompt())
            with open(_os.path.join(a.log_dir, "result.json"), "w", encoding="utf-8") as fh:
                _json.dump(result, fh, indent=1)
        if proj is None:
            print(f"planning failed: {result['error'][:400]}")
            return 1
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(proj.model_dump_json(indent=1))
        if a.log_dir:
            with open(_os.path.join(a.log_dir, "accepted_plan.json"), "w", encoding="utf-8") as fh:
                fh.write(proj.model_dump_json(indent=1))
        print(f"planned {proj.id}: {len(proj.scenes)} scene(s) -> {a.out} (planner: {director.name}, {result['attempts']} call(s))")
        return 0
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("apex.api.app:app", host=a.host, port=a.port)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
