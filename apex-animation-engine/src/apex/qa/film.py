"""Film-level checks (Milestone 6): what holds across the scenes of a film, not inside one.

- retry_resets_consistent: a retry (`retry_of`) restarts from exactly the state of the attempt it repeats: the same
  place, the same characters standing where they stood, facing the same way. It is checked on the simulation too:
  every body is at the same position at the first instant of both scenes.
- retry_counter_consistent: the retry counter carried from scene to scene: a scene starts with the retries the
  previous one started with, minus the fails that happened in it. A failed attempt is followed by a retry.
"""
from __future__ import annotations

import math
from typing import List

from .inspector import Check


def check_film(project) -> List[Check]:
    from ..scene.runtime import SceneRuntime
    scenes = {s.id: s for s in project.scenes}
    out: List[Check] = []
    retries = [s for s in project.scenes if s.retry_of]
    if retries:
        worst, bad = 0.0, []
        for s in retries:
            o = scenes.get(s.retry_of)
            if o is None:
                bad.append(f"{s.id}: retry of unknown scene {s.retry_of}")
                continue
            if s.environment != o.environment:
                bad.append(f"{s.id}: a different place from {o.id}")
            pa = {(p.character, p.x, p.at, p.on, p.facing) for p in s.placements}
            pb = {(p.character, p.x, p.at, p.on, p.facing) for p in o.placements}
            if pa != pb:
                bad.append(f"{s.id}: characters do not start as in {o.id}")
            fa = SceneRuntime(project, s.id).simulate()
            fb = SceneRuntime(project, o.id).simulate()
            for cid in set(fa.animators) & set(fb.animators):
                worst = max(worst, math.dist(fa.animators[cid].root_at(0.0), fb.animators[cid].root_at(0.0)))
            for tid in set(fa.prop_tracks) & set(fb.prop_tracks):
                worst = max(worst, math.dist(fa.prop_tracks[tid][0][:2], fb.prop_tracks[tid][0][:2]))
        out.append(Check("retry_resets_consistent", "FAIL" if bad or worst > 0.5 else "PASS", worst, 0.5,
                         "; ".join(bad) or f"{len(retries)} retr{'y' if len(retries) == 1 else 'ies'}: every body starts where "
                                            f"it started in the attempt it repeats (largest difference {worst:.2f} units)"))
    huds = [s for s in project.scenes if s.hud is not None and s.hud.retries is not None]
    if len(huds) > 1:
        bad = []
        prev = None
        for s in project.scenes:
            if s.hud is None or s.hud.retries is None:
                continue
            fails = 0
            if prev is not None:
                res = SceneRuntime(project, prev.id).simulate(physics_only=True)
                fails = sum(1 for e in res.events if e.type == "fail")
                if s.hud.retries != prev.hud.retries - fails:
                    bad.append(f"{s.id} starts with {s.hud.retries} retries; {prev.id} started with {prev.hud.retries} "
                               f"and had {fails} fail(s)")
                if fails and not s.retry_of:
                    bad.append(f"{s.id} follows a failed attempt but is not a retry")
            prev = s
        out.append(Check("retry_counter_consistent", "FAIL" if bad else "PASS",
                         details="; ".join(bad) or f"the counter carries across {len(huds)} scenes"))
    return out
