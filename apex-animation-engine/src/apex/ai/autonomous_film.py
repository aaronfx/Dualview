"""Native autonomous film from a natural-language brief — no paid LLM.

A constrained English brief is parsed, deterministically, into a world and a set
of high-level actor objectives. The native objective/ensemble planners compile
those into candidate choreographies; native physics rehearsal (Inspector-backed)
selects a feasible one; the native director critic flags unmotivated idle and
silhouette overlap and feasible shortened-idle repairs are re-rehearsed; cameras
are derived from the real events; the environment is an original cinematic world.

This is a native intent compiler, not an online improviser or an LLM: the brief
selects from bounded, verified native capabilities. The separate budgeted
StoryDirector / local_production path (paid, opt-in) is unchanged and not used
here. Artistic acceptance remains a human gate.

    from apex.ai.autonomous_film import film_from_brief
    raw = film_from_brief("A lone courier scales a barrier, recovers the power "
                          "core and escapes through the airlock.")
"""
from __future__ import annotations

import re
from copy import deepcopy

from .objective_planner import plan_objectives
from .ensemble_planner import plan_ensemble, EnsembleRequest
from ..scene.schema import ProjectSpec
from ..scene.runtime import SceneRuntime
from ..qa.director_critic import critique, repair_candidates

# --- original cinematic environments (existing native world/backdrop types, not the bare grid) ---
_WORLDS = {
    "canyon": dict(kind="canyon", seed=24, weather="motes", weather_amount=0.3,
                   sky=["#2a1a12", "#6b3b24", "#caa36a"], fog="#7a5235"),
    "tower":  dict(kind="tower", art_profile="industrial_depth", seed=42, weather="motes",
                   weather_amount=0.28, sky=["#080e19", "#1b3040", "#304853"], fog="#20313b"),
    "city":   dict(kind="city", seed=11, weather="rain", weather_amount=0.35,
                   sky=["#0a0f1e", "#1a2740", "#394a6b"], fog="#1d2740"),
    "void":   dict(kind="void", seed=5, weather="motes", weather_amount=0.2,
                   sky=["#05060c", "#0d1226", "#1a2142"], fog="#0c1024"),
}
_MOOD = [("canyon", ("canyon", "desert", "dune", "cliff", "chase")),
         ("city", ("city", "rain", "street", "neon", "rooftop", "urban")),
         ("void", ("space", "void", "dark", "night", "abyss", "dream")),
         ("tower", ("tower", "factory", "station", "industrial", "reactor", "airlock", "core"))]

INK = dict(visual_profile="apex_ink", performance_profile="continuous")


def _pick_world(brief: str) -> str:
    b = brief.lower()
    for name, keys in _MOOD:
        if any(k in b for k in keys):
            return name
    return "tower"


def _actor(cid, name, body, far, glow):
    return dict(id=cid, name=name, strength=51000,
                proportions=dict(spine=30, chest=28, head=24, thigh=44, shin=42),
                style=dict(INK, body_color=body, far_color=far, glow_color=glow, has_scarf=False,
                           limb_width=8.0, cadence_scale=1.06))


def parse_brief(brief: str) -> dict:
    """Deterministically map a brief to a world + bounded objectives. Returns the plan skeleton."""
    b = brief.lower()
    partner = any(w in b for w in ("partner", "ally", "together", "friend", "team", "companion", "two "))
    # Two characters share ONE depth lane so native body collision is active (no pass-through). The brief's own words
    # decide whether a barrier exists; when they do and a partner is present, BOTH allies cross the barrier (the lead
    # via full autochoreo tactic search, the trailing partner via the same native climb), so the depicted film is
    # faithful to the brief ("one climbs ... then both flee") without any character passing through the structure.
    has_barrier = any(w in b for w in ("barrier", "wall", "climb", "scale", "obstacle", "gap", "ledge"))
    core_word = next((w for w in ("core", "artifact", "relic", "data", "key", "spark", "sample") if w in b), "core")
    beats = []
    beats.append(("observe", "obstacle:barrier" if has_barrier else "prop:core"))
    if has_barrier:
        beats.append(("climb", "obstacle:barrier"))
    beats.append(("collect", "prop:core"))
    beats.append(("exit", "exit:airlock"))
    world = _pick_world(brief)
    # per-story variation (issue 5): the performance is tuned to the world/mood, so films are not identical
    urgent = any(w in b for w in ("collaps", "escape", "flee", "chase", "danger", "explo", "urgent"))
    payoff = {"tower": "cheer", "canyon": "laugh", "city": "impact_to_grin", "void": "rise"}.get(world, "cheer")
    watch = {"tower": "peer_down", "canyon": "kneel_look", "city": "doubt_to_dash", "void": "peer_down"}.get(world, "peer_down")
    return dict(world=world, partner=partner, has_barrier=has_barrier, core_word=core_word, beats=beats,
                title=_title(brief), urgent=urgent, payoff_clip=payoff, watch_clip=watch,
                run_speed=360.0 if urgent else 300.0, focus="upper" if urgent else "body")


def _title(brief: str) -> str:
    words = re.findall(r"[A-Za-z]+", brief)[:6]
    return " ".join(w.capitalize() for w in words) or "Autonomous Film"


def _base_world(plan: dict, width: float = 2200.0):
    """An original cinematic scene holding exactly the entities the objectives reference."""
    bd = dict(_WORLDS[plan["world"]])
    props = [dict(id="core", kind="glyph", glyph="8", position=[260.0, 60.0], size=[70.0, 92.0],
                  mass=2.4, solid=True, color="#ffd04e", z=0)]
    obstacles = []
    if plan["has_barrier"]:
        obstacles.append(dict(id="barrier", kind="platform", center=[-40.0, 115.0], size=[70.0, 230.0],
                              style="girder", color="#536d7f"))
        # a movable crate gives the planner a climb aid, as in the native crossing benchmark
        props.append(dict(id="crate", kind="crate", position=[-200.0, 45.0], size=[90.0, 90.0],
                          mass=9.0, solid=True, z=0, color="#6b5330"))
    room_w = max(2600.0, width + 900)
    # The walking surface must be visually represented across the whole walk (not a partial sub-floor girder). A
    # standable ground PLATFORM whose top is the contact plane (y=0) spans the full room: it is drawn and stood upon,
    # and platforms are not subject to the beam obstacle-clearance check, so no physical validation is weakened.
    obstacles.append(dict(id="ground", kind="platform", center=[0.0, -32.0], size=[room_w, 64.0],
                          style="girder", color="#3b4b57"))
    env = dict(id="stage", room=dict(width=room_w, height=1000, depth_back=460,
                                     entry_door=False, grid_spacing=160, grid_alpha=0.12, style="open"),
               gravity=[0, -1568], dust=14, backdrop=bd, obstacles=obstacles, props=props,
               exits=[dict(id="airlock", surface="wall_right", s=100, width=220, sealed=False, open_radius=280)])
    chars = [_actor("iko", "IKO", "#ffd04e", "#a87925", "#fdda69")]
    placements = [dict(character="iko", x=-640.0, facing=1, z=0)]
    if plan["partner"]:
        chars.append(_actor("pell", "PELL", "#59d6ed", "#2e8399", "#76e4f4"))
        # SAME depth lane as iko (z=0) so native body collision is active and the two can never pass through each
        # other; pell starts behind iko and trails, so they stay spatially separated without any depth trick.
        placements.append(dict(character="pell", x=-880.0, facing=1, z=0))
    return chars, env, placements


def _goals(plan: dict):
    g = ["notice@iko"]
    if plan["has_barrier"]:
        g.append("climbed@iko")
    g.append("pick_up@iko[prop=core]")
    g.append("exit_reached@iko[exit=airlock]")
    if plan["partner"]:
        g.append("exit_reached@pell[exit=airlock]")
    return g


def _objectives(plan: dict):
    tasks, prev = [], None
    for i, (kind, target) in enumerate(plan["beats"]):
        tid = f"b{i}"
        t = dict(id=tid, actor="iko", kind=kind, target=target)
        if prev is not None:
            t["after"] = [prev]
        tasks.append(t)
        prev = tid
    return tasks


# --- camera + score ---------------------------------------------------------
def _partner_actions(plan, exit_x):
    """A cooperating partner who shares iko's depth lane (native body collision active) and always TRAILS it, so the
    two can never pass through each other while pell stays active and finally follows iko out."""
    if not plan["partner"]:
        return []
    sp = plan.get("run_speed", 300.0)
    A = lambda typ, **kw: dict(character="pell", type=typ, **kw)
    watch = plan.get("watch_clip", "peer_down")
    acts = [A("notice", target="char:iko", duration=0.5),                            # observe the leader
            A("act", clip="beckon", emotion="encouraging", duration=0.9),            # urge iko on (lets iko pull ahead)
            A("run_to", target_x=-180, speed=sp),                                    # advance, staying behind iko
            A("act", clip=watch, emotion="anxious", duration=1.2),                   # watch iko work
            A("point", target="prop:core", duration=0.7),                            # communicate the goal
            A("wait_for", until="event:pick_up@iko[prop=core]"),
            A("act", clip="cheer", emotion="joyful", duration=1.0)]                  # react to the recovery
    if plan["has_barrier"]:
        # the partner follows the leader over the SAME barrier via the native climb (iko has already crossed and moved
        # on, so pell climbs into clear space — no pass-through, no overtake)
        acts.append(A("climb", target="obstacle:barrier"))
    acts += [A("run_to", target_x=round(exit_x - 640), speed=sp),                    # follow toward the exit, trailing
             A("wait_for", until="event:exit_reached@iko[exit=airlock]"),            # iko clears the doorway first
             A("act", clip=plan.get("payoff_clip", "cheer"), emotion="joyful", duration=1.1),  # closing reaction
             A("reach_exit", target="exit:airlock", speed=sp)]
    return acts


def _event_cameras(plan, events, duration):
    from ..scene.film_staging import BeatShot, event_shots
    beats = [BeatShot("establish", "wide", dict(mode="follow", target="iko", view_height=720,
                                                offset=[70, 45], include=["char:pell"] if plan["partner"] else []),
                      description="Establish the world and the objective.")]
    if plan["has_barrier"]:
        beats.append(BeatShot("ascend", "tracking", dict(mode="follow", target="iko", view_height=520,
                              offset=[60, 60]), "climbed@iko", -0.9, "The courier scales the barrier."))
    beats.append(BeatShot("recover", "medium", dict(mode="follow", target="iko", view_height=430,
                          offset=[55, 30]), "pick_up@iko[prop=core]", -0.3, "The core is recovered."))
    beats.append(BeatShot("escape", "wide", dict(mode="follow", target="iko", view_height=560,
                          offset=[80, 40], include=["char:pell"] if plan["partner"] else []),
                          "pick_up@iko[prop=core]", 0.3, "Break for the airlock."))
    return event_shots(events, duration, beats)


def _last_goal_time(events, goals):
    from ..scene.goals import matches
    ts = [e.t for e in events for g in goals if matches(g, e)]
    return max(ts) if ts else None


def _inject_payoff(raw, plan, exit_x):
    """Issue 7: the lead runs most of the way to the exit, turns for a beat of triumphant reaction (the emotional
    payoff), and only then leaves — so the film lands on a character moment instead of ending the instant someone
    crosses the exit. Replaces the planner's bare reach_exit with approach -> payoff -> exit."""
    acts = [a for a in raw["scenes"][0]["actions"] if not (a.get("character") == "iko" and a.get("type") == "reach_exit")]
    sp = plan.get("run_speed", 300.0)
    acts += [{"character": "iko", "type": "run_to", "target_x": round(exit_x - 240), "speed": sp},
             {"character": "iko", "type": "act", "clip": plan.get("payoff_clip", "cheer"), "emotion": "joyful",
              "duration": 1.3},
             {"character": "iko", "type": "reach_exit", "target": "exit:airlock", "speed": sp}]
    raw["scenes"][0]["actions"] = acts
    return raw


def film_from_brief(brief: str, *, max_trials: int = 8, reduce_idle: bool = True) -> dict:
    """Produce a native, rehearsed, camera-staged film from a natural-language brief. Returns a ProjectSpec dict.
    Raises ValueError with the native rejection evidence if no feasible choreography exists (honest failure)."""
    from ..scene.film_staging import duration_for_payoff
    plan = parse_brief(brief)
    chars, env, placements = _base_world(plan)
    exit_x = env["room"]["width"] / 2
    goals = _goals(plan)
    base = {
        "schema_version": "0.1", "id": "autonomous_" + re.sub(r"[^a-z0-9]+", "_", plan["title"].lower())[:40],
        "title": plan["title"], "fps": 24, "width": 1920, "height": 1080, "seed": 61,
        "characters": chars, "environments": [env],
        "scenes": [{"id": "film", "title": plan["title"], "environment": "stage", "duration": 22.0,
                    "placements": placements, "actions": _partner_actions(plan, exit_x), "goals": goals,
                    "time_fx": {"hit_stop": False, "smears": False, "screen_fx": False, "punch_in": False},
                    "score": {"key": "D", "level": 0.45, "cues": [{"mood": "tension", "at": 0.0}]},
                    "shots": [{"id": "w", "kind": "wide", "start": 0, "end": 22.0,
                               "camera": {"mode": "follow", "target": "iko", "view_height": 720, "offset": [70, 45]}}]}],
    }
    req = {"scene_id": "film", "tasks": _objectives(plan), "max_trials": max_trials}
    sel, trace = plan_objectives(base, req)
    if sel.project is None:
        raise ValueError("no feasible native choreography for brief; trials="
                         + repr([(t.name, t.reason) for t in sel.trials]))
    project = sel.project
    # native director critic: reduce unmotivated idle (deficiency 1) via feasible shortened-idle rehearsal
    repairs = []
    if reduce_idle:
        rt = SceneRuntime(project, "film")
        found = [f for f in critique(rt)["findings"] if f["kind"] in ("idle", "unmotivated_idle")]
        if found:
            from .smart_director import rehearse as _rehearse, ActionCandidate
            cands = [ActionCandidate(name=c["name"], actions=c["actions"])
                     for c in repair_candidates(project, "film") if c["name"] != "original"]
            if cands:
                tightened = _rehearse(project.model_dump(mode="json"), "film", cands, max_trials=4)
                if tightened.project is not None:
                    project = tightened.project
                    repairs = [t.name for t in tightened.trials]
    raw = project.model_dump(mode="json")
    exit_x = raw["environments"][0]["room"]["width"] / 2
    raw = _inject_payoff(raw, plan, exit_x)         # issue 7: a reaction/payoff beat before the exit
    project = ProjectSpec.model_validate(raw)
    sim = SceneRuntime(project, "film").simulate()
    last = _last_goal_time(sim.events, goals)
    dur = duration_for_payoff(last, tail=1.4, maximum=30) if last else raw["scenes"][0]["duration"]
    raw["scenes"][0]["duration"] = dur
    raw["scenes"][0]["score"]["cues"].append({"mood": "triumph", "at": round(max(0.0, dur - 2.2), 1)})
    raw["scenes"][0]["shots"] = _event_cameras(plan, sim.events, dur)
    meta = {"brief": brief, "plan": plan, "objective_trace": trace, "idle_repairs": repairs}
    return raw, meta
