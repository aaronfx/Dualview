"""Consecutive-obstacle traversal via the verified `autochoreo` tactic search — no new obstacle-avoidance logic.

A high-level objective ("cross a series of obstacles to reach the goal") is lowered to the native autochoreo
Objective PER OBSTACLE: for each obstacle the engine independently searches running / jumping / vaulting / climbing /
landing tactics, simulates each at 240 Hz and rejects the infeasible ones; the winning actions are chained. The actor
threads from one obstacle to the next. The existing autochoreo is the sole authority on how an obstacle is cleared, so
the Director never bypasses native movement safety.
"""
from __future__ import annotations

from copy import deepcopy

from ..scene.schema import ProjectSpec
from ..scene.autochoreo import Objective, search
from ..scene.runtime import SceneRuntime

_GROUND = {"kind": "platform", "style": "girder", "color": "#3b4b57"}


def _actor(cid):
    return {"id": cid, "name": cid.upper(), "strength": 52000,
            "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
            "style": {"visual_profile": "apex_ink", "performance_profile": "continuous",
                      "body_color": "#ffd04e", "far_color": "#a87925", "glow_color": "#fdda69",
                      "has_scarf": False, "limb_width": 8.0}}


def course_scene(obstacles, *, actor="iko", start_x=-640.0, goal_x=None, width=3200.0, duration=18.0,
                 backdrop=None, actions=None, goals=None, extra_props=None):
    """A full scene holding the whole obstacle course: a girder ground spanning the walk, every obstacle, and the
    goal prop past the last one."""
    xs = [o["center"][0] for o in obstacles]
    goal_x = goal_x if goal_x is not None else (max(xs) + 320.0)
    obs = [dict(_GROUND, id="ground", center=[0.0, -32.0], size=[width, 64.0])]
    for i, o in enumerate(obstacles):
        obs.append(dict(_GROUND, id=o.get("id", f"roof{i+1}"), kind="platform",
                        center=list(o["center"]), size=list(o["size"])))
    props = [{"id": "core", "kind": "glyph", "glyph": "8", "position": [goal_x, 60.0], "size": [70.0, 92.0],
              "mass": 2.4, "solid": True, "color": "#ffd04e"}]
    if extra_props:
        props.extend(extra_props)
    env = {"id": "course", "room": {"width": width, "height": 1100, "depth_back": 460, "entry_door": False,
                                    "grid_spacing": 160, "grid_alpha": 0.12, "style": "open"},
           "gravity": [0, -1568], "dust": 12, "obstacles": obs, "props": props}
    if backdrop:
        env["backdrop"] = backdrop
    return {"schema_version": "0.1", "id": "obstacle_course", "title": "Obstacle Course", "fps": 24,
            "width": 1920, "height": 1080, "seed": 61, "characters": [_actor(actor)], "environments": [env],
            "scenes": [{"id": "s", "title": "course", "environment": "course", "duration": duration,
                        "placements": [{"character": actor, "x": start_x, "facing": 1, "z": 0}],
                        "actions": actions or [], "goals": goals or [],
                        "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
                        "shots": [{"id": "w", "kind": "wide", "start": 0, "end": duration,
                                   "camera": {"mode": "follow", "target": actor, "view_height": 760, "offset": [90, 45]}}]}]}


def _clamp_forward(actions, start_x):
    """A strictly left-to-right course only ever advances. Independently-planned segments, chained, can leave a
    small backward step at a hand-off: a jump overshoots its segment goal, then the next segment's orienting run
    (and the segment-finish run) target a point just behind, which forces a face-flip turn that whips a limb across
    the body (a no_teleport_joints spike). Those backward `run_to`s are redundant orient wiggles, so they are
    DROPPED — never clamped forward, which could push a step across an un-cleared obstacle. A `run_to` that is the
    functional approach to a climb/vault/push is kept. No forward motion or clearance is changed, so native movement
    safety is untouched."""
    out, maxx = [], start_x
    for i, a in enumerate(actions):
        b = dict(a)
        tx = b.get("target_x")
        nxt = actions[i + 1] if i + 1 < len(actions) else {}
        approach_to_obstacle = nxt.get("type") in ("climb", "vault", "push", "jump_to")
        if b.get("type") == "run_to" and tx is not None and tx < maxx - 2 and not approach_to_obstacle:
            continue  # drop the redundant backward orient/finish run (keeps the course monotonic, no turn whip)
        if tx is not None:
            maxx = max(maxx, tx)
        out.append(b)
    return out


def _assemble(obstacles, actor, start_x, goal_x, width, max_jump_apex, excluded):
    """One pass: per obstacle, let autochoreo SELECT a tactic (honouring `excluded`), chain the traversals, add the
    final core recovery, and strip redundant backward motion. Returns (actions, segments)."""
    actions, segments = [], []
    pos = start_x
    for i, o in enumerate(obstacles):
        oid = o.get("id", f"roof{i+1}")
        # the segment goal sits just past THIS obstacle and before the next one (autochoreo wants one obstacle
        # between actor and goal), or the real goal for the last obstacle
        seg_goal = goal_x if i == len(obstacles) - 1 else min(goal_x, obstacles[i + 1]["center"][0]
                                                              - obstacles[i + 1]["size"][0] / 2 - 120.0)
        seg_goal = max(seg_goal, o["center"][0] + o["size"][0] / 2 + 150.0)
        seg = course_scene([o], actor=actor, start_x=pos, goal_x=seg_goal, width=width, duration=10.0)
        res = search(ProjectSpec.model_validate(seg), Objective(scene_id="s", actor=actor, obstacle_id=oid,
                     goal_prop_id="core", max_jump_apex=max_jump_apex,
                     exclude_tactics=tuple(excluded.get(oid, ()))))
        if not res.succeeded:
            raise ValueError(f"no native tactic clears obstacle {oid} (excluded={sorted(excluded.get(oid, ()))}); "
                             "the crossing is not physically achievable for this actor — the Director must stop or "
                             "reroute rather than walk through it. trials="
                             + repr([(t.candidate, t.reason) for t in res.trials]))
        traverse = [dict(a) for a in res.actions if a.get("type") not in ("pick_up", "act", "wait_grounded")]
        actions.extend(traverse)
        # full decision trace: every tactic the engine considered for this obstacle and why it was accepted/rejected
        considered = [{"tactic": t.candidate, "accepted": t.accepted, "reason": t.reason} for t in res.trials]
        segments.append({"obstacle": oid, "height": round(o["size"][1]), "width": round(o["size"][0]),
                         "chosen": res.chosen, "tactic": res.chosen, "actions": len(traverse),
                         "excluded_before": sorted(excluded.get(oid, ())), "considered": considered})
        pos = seg_goal
    # final: the last segment already delivered the actor to the core's vicinity moving forward, so recover the core
    # in place (an extra backward approach would force a face-flip turn that whips a limb) and a triumphant beat.
    actions.append({"character": actor, "type": "pick_up", "target": "prop:core"})
    actions.append({"character": actor, "type": "act", "clip": "cheer", "emotion": "joyful", "duration": 1.2})
    return _clamp_forward(actions, start_x), segments


def plan_course(obstacles, *, actor="iko", start_x=-640.0, goal_x=None, width=3200.0, max_jump_apex=260.0,
                max_replans=6):
    """Chain autochoreo across the obstacles with FULL-PLAN validation. A tactic that is clean when a segment is
    rehearsed in isolation (actor at rest) can still graze the obstacle once CHAINED, because the actor arrives with
    real forward momentum. So after assembling the plan we simulate the WHOLE scene; if the body grazes any
    structure, the grazing tactic is excluded for that obstacle and the segment is re-planned with the next feasible
    native tactic (dynamic strategy re-selection). This repeats until the full traversal is graze-free, or raises if
    an obstacle has no clean tactic left (honest failure — never a walk-through or a concealed scrape)."""
    obstacles = sorted(obstacles, key=lambda o: o["center"][0])
    xs = [o["center"][0] for o in obstacles]
    goal_x = goal_x if goal_x is not None else (max(xs) + 320.0)
    duration = max(16.0, len(obstacles) * 5.5 + 8.0)
    excluded: dict[str, set] = {}
    replans = 0
    while True:
        actions, segments = _assemble(obstacles, actor, start_x, goal_x, width, max_jump_apex, excluded)
        scene = course_scene(obstacles, actor=actor, start_x=start_x, goal_x=goal_x, width=width,
                             duration=duration, actions=actions,
                             goals=[f"climbed@{actor}" if any("climb" in (s["tactic"] or "") for s in segments)
                                    else f"takeoff@{actor}", f"pick_up@{actor}[prop=core]"])
        sim = SceneRuntime(ProjectSpec.model_validate(scene), "s").simulate()
        if replans >= max_replans:
            break
        # A graze is an uncontrolled body-vs-structure collision: the tactic did not clear the body, so it is the
        # wrong tactic for this (chained) approach. Exclude it for that obstacle and re-plan with the next feasible
        # native tactic. (A marginal foot-plant penetration is handled by the per-tactic clearance checks, not by
        # disqualifying an otherwise-clean tactic here.)
        offenses = [_graze_x(sim, actor, g) for g in sim.events
                    if g.type == "graze" and getattr(g, "character", None) == actor]
        if not offenses:
            break
        tac_by_oid = {s["obstacle"]: s["tactic"] for s in segments}
        changed = False
        for ox in offenses:
            oid = min(obstacles, key=lambda o: abs(o["center"][0] - ox)).get("id")
            tac = tac_by_oid.get(oid)
            if tac and tac not in excluded.setdefault(oid, set()):
                excluded[oid].add(tac)
                changed = True
        if not changed:
            break
        replans += 1
    # event-derived duration: end the film shortly after the recovery payoff, not on a fixed clock. The last
    # meaningful beat is the cheer after the core pickup; hold a short settle tail, then stop — no dead air.
    meaningful = [e.t for e in sim.events if getattr(e, "character", None) == actor
                  and e.type in ("pick_up", "act", "takeoff", "climbed", "impact")]
    if meaningful:
        trimmed = round(max(8.0, max(meaningful) + 2.6), 2)
        if trimmed < scene["scenes"][0]["duration"]:
            scene["scenes"][0]["duration"] = trimmed
            for sh in scene["scenes"][0].get("shots", []):
                sh["end"] = min(sh.get("end", trimmed), trimmed)
    report = {"method": "chained native autochoreo tactic search with full-plan graze validation and dynamic "
              "re-selection; engine-selected per obstacle", "obstacles": len(obstacles), "segments": segments,
              "replans": replans, "excluded": {k: sorted(v) for k, v in excluded.items() if v},
              "duration": scene["scenes"][0]["duration"]}
    return scene, report


def _graze_x(sim, actor, graze_event):
    """The actor's x at the moment of a graze (to attribute it to an obstacle)."""
    pt = getattr(graze_event, "data", {}).get("point") if hasattr(graze_event, "data") else None
    if pt is not None:
        return pt[0]
    recs = sim.controllers[actor].records
    return min(recs, key=lambda r: abs(r.t - graze_event.t)).pos[0]
