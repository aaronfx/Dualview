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
    has_barrier = any(w in b for w in ("barrier", "wall", "climb", "scale", "obstacle", "gap", "ledge"))
    core_word = next((w for w in ("core", "artifact", "relic", "data", "key", "spark", "sample") if w in b), "core")
    beats = []
    beats.append(("observe", "obstacle:barrier" if has_barrier else "prop:core"))
    if has_barrier:
        beats.append(("climb", "obstacle:barrier"))
    beats.append(("collect", "prop:core"))
    beats.append(("exit", "exit:airlock"))
    return dict(world=_pick_world(brief), partner=partner, has_barrier=has_barrier,
                core_word=core_word, beats=beats, title=_title(brief))


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
    # girder sub-floor (below the feet contact; never a standable beam) for a visible ground in open rooms
    obstacles.append(dict(id="station_floor", kind="beam", center=[0.0, -33.0], size=[width, 50.0],
                          style="girder", color="#455a66"))
    env = dict(id="stage", room=dict(width=max(2600.0, width + 900), height=1000, depth_back=460,
                                     entry_door=False, grid_spacing=160, grid_alpha=0.12, style="open"),
               gravity=[0, -1568], dust=14, backdrop=bd, obstacles=obstacles, props=props,
               exits=[dict(id="airlock", surface="wall_right", s=100, width=220, sealed=False, open_radius=280)])
    chars = [_actor("iko", "IKO", "#ffd04e", "#a87925", "#fdda69")]
    placements = [dict(character="iko", x=-640.0, facing=1, z=0)]
    if plan["partner"]:
        chars.append(_actor("pell", "PELL", "#59d6ed", "#2e8399", "#76e4f4"))
        placements.append(dict(character="pell", x=560.0, facing=-1, z=45))  # back lane: depth separation vs iko
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
def _partner_actions(plan):
    """A cooperating partner (authored, preserved by the planner): wait for the core, move to the
    airlock, reach it together. Keeps the two silhouettes in separate depth lanes."""
    if not plan["partner"]:
        return []
    # pell stays in the back depth lane (no silhouette overlap) and follows iko out after iko has cleared the
    # airlock, so the two never contest the same doorway.
    A = lambda typ, **kw: dict(character="pell", type=typ, **kw)
    return [A("act", clip="wave_on", emotion="joyful", duration=0.6),
            A("wait_for", until="event:pick_up@iko[prop=core]"),
            A("wait_for", until="event:exit_reached@iko[exit=airlock]"),
            A("reach_exit", target="exit:airlock", speed=240, lane=55)]


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


def film_from_brief(brief: str, *, max_trials: int = 8, reduce_idle: bool = True) -> dict:
    """Produce a native, rehearsed, camera-staged film from a natural-language brief. Returns a ProjectSpec dict.
    Raises ValueError with the native rejection evidence if no feasible choreography exists (honest failure)."""
    from ..scene.film_staging import duration_for_payoff
    plan = parse_brief(brief)
    chars, env, placements = _base_world(plan)
    goals = _goals(plan)
    base = {
        "schema_version": "0.1", "id": "autonomous_" + re.sub(r"[^a-z0-9]+", "_", plan["title"].lower())[:40],
        "title": plan["title"], "fps": 24, "width": 1920, "height": 1080, "seed": 61,
        "characters": chars, "environments": [env],
        "scenes": [{"id": "film", "title": plan["title"], "environment": "stage", "duration": 22.0,
                    "placements": placements, "actions": _partner_actions(plan), "goals": goals,
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
    sim = SceneRuntime(project, "film").simulate()
    last = _last_goal_time(sim.events, goals)
    dur = duration_for_payoff(last, tail=1.4, maximum=30) if last else raw["scenes"][0]["duration"]
    raw["scenes"][0]["duration"] = dur
    raw["scenes"][0]["score"]["cues"].append({"mood": "triumph", "at": round(max(0.0, dur - 2.2), 1)})
    raw["scenes"][0]["shots"] = _event_cameras(plan, sim.events, dur)
    meta = {"brief": brief, "plan": plan, "objective_trace": trace, "idle_repairs": repairs}
    return raw, meta
