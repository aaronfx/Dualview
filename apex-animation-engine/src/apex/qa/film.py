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
    # Plot-critical props are checked against actual simulation carry spans and
    # action events, never just the declarative scene plan. Scenes remain separately
    # simulated; their physical handoff (ownership) must be explicitly reconciled.
    tracks = {}
    simulations = {}
    def simulation(sc):
        if sc.id not in simulations:
            simulations[sc.id] = SceneRuntime(project, sc.id).simulate(physics_only=True)
        return simulations[sc.id]

    def owner_at(res, pid, instant):
        owners = []
        for cid, ctl in res.controllers.items():
            if any(p == pid and t0 <= instant + 1e-6 and instant < t1 - 1e-6
                   for p, t0, t1 in ctl.carry_log):
                owners.append(cid)
        return owners[0] if len(owners) == 1 else ("world" if not owners else "INVALID")

    errors, details = [], []
    for index, sc in enumerate(project.scenes):
        if not sc.story_props and sc.restoration is None:
            continue
        res = simulation(sc)
        for h in sc.story_props:
            a = owner_at(res, h.prop, 0.0)
            b = owner_at(res, h.prop, sc.duration)
            if a != h.owner_in or b != h.owner_out:
                errors.append(f"{sc.id}/{h.prop}: observed {a}->{b}, declared {h.owner_in}->{h.owner_out}")
            entries = [e for e in res.events if e.data.get("prop") == h.prop]
            if h.owner_in == "world" and h.owner_out != "world":
                if not any(e.type == "pick_up" and e.character == h.owner_out for e in entries):
                    errors.append(f"{sc.id}/{h.prop}: missing physical pickup by {h.owner_out}")
            if h.owner_in != "world" and h.owner_out == "world":
                if not any(e.type in ("throw", "prop_placed", "prop_dropped", "disarmed") for e in entries):
                    errors.append(f"{sc.id}/{h.prop}: no physical release event")
            tracks.setdefault(h.prop, []).append((index, sc, h, res))
            details.append(f"{sc.id}:{h.prop} {a}->{b}")
        if sc.restoration is not None:
            pid = sc.restoration.prop
            restored = [e for e in res.events if e.type == "core_restored" and e.data.get("prop") == pid]
            if not restored or owner_at(res, pid, sc.duration) != "world":
                errors.append(f"{sc.id}/{pid}: no physically settled, released core_restored event")
            else:
                details.append(f"{sc.id}:{pid} restored at t={restored[0].t:.2f}")
    for pid, appearances in tracks.items():
        for (i, prev_sc, prev, prev_res), (j, next_sc, nxt, next_res) in zip(appearances, appearances[1:]):
            if j != i + 1:
                errors.append(f"{pid}: missing from scene(s) between {prev_sc.id} and {next_sc.id}")
                continue
            if prev.owner_out != nxt.owner_in:
                errors.append(f"{pid}: ownership jumps {prev.owner_out}->{nxt.owner_in} "
                              f"between {prev_sc.id} and {next_sc.id}")
            if prev.owner_out == nxt.owner_in == "world":
                if prev_sc.environment != next_sc.environment:
                    errors.append(f"{pid}: unheld prop changes worlds without a carried transfer")
                else:
                    a = prev_res.prop_tracks[pid][-1, :2]
                    b = next_res.prop_tracks[pid][0, :2]
                    if math.dist(a, b) > 5.0:
                        errors.append(f"{pid}: unheld prop jumps {math.dist(a, b):.1f} units "
                                      f"between {prev_sc.id} and {next_sc.id}")
    if tracks:
        out.append(Check("plot_prop_continuity", "FAIL" if errors else "PASS", float(len(errors)), 0.0,
                         "; ".join(errors) if errors else "; ".join(details)))

    if project.film_goals:
        from ..scene.goals import matches
        errors, witnessed = [], []
        last_index, last_time = -1, -1.0
        for goal in project.film_goals:
            index = next(i for i, sc in enumerate(project.scenes) if sc.id == goal.scene)
            res = simulation(project.scenes[index])
            ev = next((e for e in res.events if matches(goal.event, e)
                       and (index > last_index or e.t >= last_time - 1e-6)), None)
            if ev is None:
                errors.append(f"{goal.scene}: missing or out-of-order {goal.event}")
                continue
            last_index, last_time = index, ev.t
            witnessed.append(f"{goal.scene}:{goal.event}@{ev.t:.2f}")
        out.append(Check("narrative_event_chain", "FAIL" if errors else "PASS", float(len(errors)), 0.0,
                         "; ".join(errors) if errors else "; ".join(witnessed)))

    return out
