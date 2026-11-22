"""Regression benchmark: every engine change must keep the earlier films working, with no scene-specific workarounds.

Each film is re-simulated from its scene file as it is committed and judged on:
- story outcome: its goals happen, in order (the same events the film was built around), and every scripted action
  runs (none left queued, no engine violation);
- technical gate: physics consistency, valid geometry, no unintended clipping, stable replay, correct event outcomes;
- cinematic gate: the automated readability checks (a person still reviews the film itself);
- drift: how far each goal moved in time against the stored baseline (cuts in event-timed films are placed from them).

A film regresses if it meets fewer goals, a check that passed in the baseline now fails, or a gate gets worse.

    PYTHONPATH=src python -m apex.qa.benchmark            # run and compare against the baseline
    PYTHONPATH=src python -m apex.qa.benchmark --update   # store a new baseline (after a reviewed, intended change)
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BASELINE = os.path.join(ROOT, "docs", "evidence", "regression_baseline.json")

# film file -> what it exercises
FILMS: Dict[str, str] = {
    "first_exchange.json": "combat: strikes, blocks, dodges, ragdoll knockdown and recovery",
    "the_rescue.json": "dynamic props: stick-slip push, rope, pinning, lever, help up (the PR #7 container)",
    "runaway_crate.json": "dynamic props: a crate breaking loose, character reactions",
    "symbol_run.json": "acrobatics: platforms, vault, climb, flips, rolls, glyph props",
    "glyph_duel.json": "acrobatics + combat + time effects: hit-stop, slow motion, thrown and wielded glyphs",
    "foundry_flip.json": "gravity: surface switches and flips",
    "gravity_switch_1d.json": "gravity: slides, swings, doors",
    "orb_runner.json": "level grid, orbs, portals (characters and a prop), beat sync, particles (Milestone 4)",
    "specimen.json": "breakables, morphs, a composite creature torn apart, diagrams, set dressing (Milestone 5)",
    "last_retry.json": "acting, collapses, ledge catches and rescues, retries, HUD, together exits (Milestone 6)",
}
DRIFT_WARN = 0.5  # s: a goal that moved more than this may need its cut re-placed (reported, not a failure)
_GRADE = {"PASS": 0, "WARN": 1, "FAIL": 2}


def run_film(fname: str, determinism: bool = True) -> Dict[str, dict]:
    """Simulate every scene of a film and judge it. Returns {scene id: result}."""
    from ..render.pipeline import build_camera
    from ..render.timewarp import build_warp
    from ..scene.goals import derive_goals, progress
    from ..scene.runtime import SceneRuntime
    from ..scene.schema import ProjectSpec
    from .inspector import Inspector
    with open(os.path.join(ROOT, "examples", fname)) as fh:
        project = ProjectSpec.model_validate(json.load(fh))
    out = {}
    for sc in project.scenes:
        rt = SceneRuntime(project, sc.id)
        res = rt.simulate()
        goals = list(sc.goals or derive_goals(sc))
        # derived goals are every character's waits in action-list order, not story order: check them unordered
        met, times, missing = progress(goals, res.events, ordered=bool(sc.goals))
        warp = build_warp(rt.scene, res.events, res.duration, project.fps)
        rep = Inspector(rt, build_camera(rt, project.width / project.height), project.fps,
                        size=(project.width, project.height), warp=warp).run(check_determinism=determinism)
        left = sorted({f"{cid}:{a.type}" for cid, c in res.controllers.items() for a in c.queue
                       if a.type not in ("idle", "guard")})  # holding a pose past the end of the scene is fine
        viol = sorted(f"{cid}: {c.violation}" for cid, c in res.controllers.items() if c.violation)
        out[sc.id] = {"left": left, "violations": viol, "goals": goals, "met": met, "times": [None if t is None else round(t, 3) for t in times],
                      "missing": missing, "gates": rep.gates(),
                      "checks": {c.name: c.status for c in rep.checks},
                      "failed": sorted(c.name for c in rep.checks if c.status == "FAIL"),
                      "events": len(res.events)}
    return out


def compare(base: Optional[dict], cur: dict) -> List[str]:
    """Regressions of one scene against its baseline (empty: none)."""
    bad = [f"actions never ran: {', '.join(cur['left'])}"] if cur["left"] else []
    bad += [f"violation: {v}" for v in cur["violations"]]
    if cur["met"] < len(cur["goals"]):
        bad.append(f"goal not met: {cur['missing']} ({cur['met']}/{len(cur['goals'])})")
    if base is None:
        return bad + [f"{g} gate {s}" for g, s in cur["gates"].items() if s == "FAIL"]
    if cur["met"] < base["met"]:
        bad.append(f"fewer goals met: {cur['met']} < {base['met']}")
    for g, s in cur["gates"].items():
        if _GRADE[s] > _GRADE[base["gates"].get(g, "PASS")]:
            bad.append(f"{g} gate {base['gates'].get(g)} -> {s}")
    for name, s in cur["checks"].items():
        if s == "FAIL" and base["checks"].get(name) in ("PASS", "WARN", "SKIP", None):
            bad.append(f"check now fails: {name}")
    return bad


def drift(base: Optional[dict], cur: dict) -> List[str]:
    if base is None:
        return []
    return [f"{g} moved {t - t0:+.2f}s" for g, t, t0 in zip(cur["goals"], cur["times"], base["times"])
            if t is not None and t0 is not None and abs(t - t0) > DRIFT_WARN]


def main(argv: List[str]) -> int:
    update = "--update" in argv
    only = [a for a in argv if a.endswith(".json")]
    base = json.load(open(BASELINE)) if os.path.exists(BASELINE) else {}
    results, failed = {}, False
    for fname in only or FILMS:
        res = run_film(fname)
        results[fname] = res
        for sid, cur in res.items():
            b = base.get(fname, {}).get(sid)
            bad, dr = compare(b, cur), drift(b, cur)
            failed |= bool(bad)
            print(f"{'REGRESS' if bad else 'OK     '} {fname:24s} {sid:14s} goals {cur['met']}/{len(cur['goals'])}  "
                  f"technical {cur['gates']['technical']}  cinematic {cur['gates']['cinematic']}")
            for m in bad:
                print(f"          - {m}")
            for m in dr:
                print(f"          ~ drift: {m}")
    if update:
        base.update(results)
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w") as fh:
            json.dump(base, fh, indent=1, sort_keys=True)
        print(f"baseline written: {os.path.relpath(BASELINE, ROOT)}")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
