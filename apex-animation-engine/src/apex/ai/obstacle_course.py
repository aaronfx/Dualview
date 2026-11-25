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

_GROUND = {"kind": "platform", "style": "girder", "color": "#3b4b57"}


def _actor(cid):
    return {"id": cid, "name": cid.upper(), "strength": 52000,
            "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42},
            "style": {"visual_profile": "apex_ink", "performance_profile": "continuous",
                      "body_color": "#ffd04e", "far_color": "#a87925", "glow_color": "#fdda69",
                      "has_scarf": False, "limb_width": 8.0}}


def course_scene(obstacles, *, actor="iko", start_x=-640.0, goal_x=None, width=3200.0, duration=18.0,
                 backdrop=None, actions=None, goals=None):
    """A full scene holding the whole obstacle course: a girder ground spanning the walk, every obstacle, and the
    goal prop past the last one."""
    xs = [o["center"][0] for o in obstacles]
    goal_x = goal_x if goal_x is not None else (max(xs) + 320.0)
    obs = [dict(_GROUND, id="ground", center=[0.0, -32.0], size=[width, 64.0])]
    for i, o in enumerate(obstacles):
        obs.append(dict(_GROUND, id=o.get("id", f"roof{i+1}"), kind="platform",
                        center=list(o["center"]), size=list(o["size"])))
    env = {"id": "course", "room": {"width": width, "height": 1100, "depth_back": 460, "entry_door": False,
                                    "grid_spacing": 160, "grid_alpha": 0.12, "style": "open"},
           "gravity": [0, -1568], "dust": 12, "obstacles": obs,
           "props": [{"id": "core", "kind": "glyph", "glyph": "8", "position": [goal_x, 60.0], "size": [70.0, 92.0],
                      "mass": 2.4, "solid": True, "color": "#ffd04e"}]}
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


def plan_course(obstacles, *, actor="iko", start_x=-640.0, goal_x=None, width=3200.0, max_jump_apex=260.0):
    """Chain autochoreo across the obstacles. Returns (scene_dict_with_actions, report). Raises if any obstacle
    cannot be cleared by any native tactic (honest failure — never a walk-through)."""
    obstacles = sorted(obstacles, key=lambda o: o["center"][0])
    xs = [o["center"][0] for o in obstacles]
    goal_x = goal_x if goal_x is not None else (max(xs) + 320.0)
    actions, segments = [], []
    pos = start_x
    for i, o in enumerate(obstacles):
        oid = o.get("id", f"roof{i+1}")
        left = o["center"][0] - o["size"][0] / 2
        # the segment goal sits just past THIS obstacle and before the next one (autochoreo wants one obstacle
        # between actor and goal), or the real goal for the last obstacle
        seg_goal = goal_x if i == len(obstacles) - 1 else min(goal_x, obstacles[i + 1]["center"][0]
                                                              - obstacles[i + 1]["size"][0] / 2 - 120.0)
        seg_goal = max(seg_goal, o["center"][0] + o["size"][0] / 2 + 150.0)
        seg = course_scene([o], actor=actor, start_x=pos, goal_x=seg_goal, width=width, duration=10.0)
        res = search(ProjectSpec.model_validate(seg), Objective(scene_id="s", actor=actor, obstacle_id=oid,
                     goal_prop_id="core", max_jump_apex=max_jump_apex))
        if not res.succeeded:
            raise ValueError(f"no native tactic clears obstacle {oid}; trials="
                             + repr([(t.candidate, t.reason) for t in res.trials]))
        # drop the goal-collect tail (pick_up/celebrate); keep only the traversal actions for this actor
        traverse = [dict(a) for a in res.actions if a.get("type") not in ("pick_up", "act", "wait_grounded")]
        actions.extend(traverse)
        segments.append({"obstacle": oid, "height": round(o["size"][1]), "tactic": res.chosen,
                         "actions": len(traverse)})
        pos = seg_goal
    # final: run to the core, recover it, and a triumphant beat (the pursuit payoff)
    actions.append({"character": actor, "type": "run_to", "target": "prop:core", "speed": 320})
    actions.append({"character": actor, "type": "pick_up", "target": "prop:core"})
    actions.append({"character": actor, "type": "act", "clip": "cheer", "emotion": "joyful", "duration": 1.2})
    goals = [f"climbed@{actor}" if any(s["tactic"] and "climb" in s["tactic"] for s in segments) else f"takeoff@{actor}",
             f"pick_up@{actor}[prop=core]"]
    scene = course_scene(obstacles, actor=actor, start_x=start_x, goal_x=goal_x, width=width,
                         duration=max(16.0, len(obstacles) * 5.5 + 8.0), actions=actions, goals=goals)
    report = {"method": "chained native autochoreo tactic search; engine-selected per obstacle",
              "obstacles": len(obstacles), "segments": segments}
    return scene, report
