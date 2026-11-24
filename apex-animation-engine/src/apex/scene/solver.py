"""Physical setup solver: APEX chooses the numbers, the planner states the intent.

A planner (human or AI) writes the story as actions plus ordered `goals` (story beats such as
"push_lost@milo", "pinned@milo[by=post]", "freed@milo"). It does not have to guess the friction, slack, break
force or positions that make those beats happen in simulation. This module does that, in two stages:

1. **Physics-derived fixes** (closed form): a pushed prop is given a breakaway friction just below the push force,
   and a sliding friction low enough for it to get away; a rope that starts shorter than its ends' distance
   gets slack; a rope that must snap gets a breaking force.
2. **Search**: a bounded, seeded local search over the physical *knobs* the action list depends on (frictions,
   masses, rope slack and breaking force, the position and balance of a prop tied to the pushed one, tool and
   fulcrum positions), using fast physics-only simulations. Score = goals achieved in order, then a partial
   measure for the next missing goal (how far the push moved the prop, the rope's peak tension over its breaking
   force, how close a falling prop landed to the character).

Actions, characters and story order are never changed: if the goals cannot be reached by tuning the setup, the
report says which goal is missing and why, and the planner must change the story structure.

`resolve_cuts` then places event-timed cuts (`shot.cut_on`) at the simulated event times.
"""
from __future__ import annotations

import copy
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .goals import derive_goals, matches, parse_goal, progress
from .schema import ProjectSpec

G_FRICTION_SCALE = 0.9  # pymunk friction = product of both shapes' coefficients; the floor contributes ~0.9-1.0


# ---------------------------------------------------------------- helpers over the project dict
def _scene_idx(d: dict, scene_id: str) -> int:
    return next(i for i, s in enumerate(d["scenes"]) if s["id"] == scene_id)


def _env(d: dict, sc: dict) -> dict:
    return next(e for e in d["environments"] if e["id"] == sc["environment"])


def _prop(env: dict, pid: str) -> dict:
    return next(p for p in env.get("props", []) if p["id"] == pid)


def _char(d: dict, cid: str) -> dict:
    return next(c for c in d["characters"] if c["id"] == cid)


def _ref(s: Optional[str]) -> Optional[str]:
    return s.split(":", 1)[1] if s and ":" in s else None


def _gmag(env: dict) -> float:
    g = env.get("gravity", (0.0, -1568.0))
    return math.hypot(g[0], g[1])


@dataclass
class Knob:
    name: str
    get: Callable[[dict], float]
    set: Callable[[dict, float], None]
    lo: float
    hi: float
    log: bool = False

    def clip(self, v: float) -> float:
        return min(self.hi, max(self.lo, v))


@dataclass
class Trial:
    score: float
    met: int
    total: int
    missing: Optional[str]
    stuck: List[str]
    times: List[Optional[float]]
    events: list = field(default_factory=list)
    error: Optional[str] = None
    result: Any = None  # the physics-only SimulationResult (prop tracks, controllers)
    over: float = 0.0  # seconds by which the last goal overruns the planned length

    @property
    def complete(self) -> bool:
        return self.met == self.total and not self.stuck and self.error is None


@dataclass
class SolveReport:
    goals: List[str]
    ordered: bool
    adjustments: List[Dict[str, Any]]
    evaluations: int
    success: bool
    met: int
    missing: Optional[str]
    stuck: List[str]
    goal_times: List[Optional[float]]
    duration: float
    note: str = ""

    def summary(self) -> str:
        got = ", ".join(f"{g} at {t:.2f}s" for g, t in zip(self.goals, self.goal_times) if t is not None) or "none"
        adj = "; ".join(f"{a['knob']}: {a['old']} -> {a['new']} ({a['why']})" for a in self.adjustments) or "none"
        s = (f"setup solver ({self.evaluations} simulations): {'all goals reached' if self.success else 'NOT solved'}; "
             f"goals reached: {got}")
        if not self.success:
            s += f"; first missing goal: {self.missing or '-'}"
            if self.stuck:
                s += f"; still waiting at the end: {'; '.join(self.stuck)}"
            if self.note:
                s += f"; {self.note}"
        return s + f". Engine adjustments: {adj}"


def stuck_characters(r) -> List[str]:
    """Characters whose action list did not complete because they are still waiting for something."""
    out = []
    for cid, c in r.controllers.items():
        a = c.cur
        if a is None:
            continue
        inter = getattr(c, "inter", {}) or {}
        ph = inter.get("phase")
        if ph == "blocked":
            continue  # reported separately (controller.violation)
        waiting = (a.type == "wait_for" or (a.type == "crawl_out" and ph == "wait")
                   or (a.type == "get_up" and ph == "up" and inter.get("wait", 0.0) > 1.0)
                   or (a.type == "use_lever" and ph == "hold" and a.until) or (a.type == "struggle" and a.until))
        if waiting:
            out.append(f"{cid} was still waiting in '{a.type}'" + (f" (until {a.until})" if a.until else "")
                       + f" when the scene ended, with {len(c.queue)} action(s) never reached")
    return out


# ---------------------------------------------------------------- knobs the action list depends on
def find_knobs(d: dict, scene_id: str) -> List[Knob]:
    sc = d["scenes"][_scene_idx(d, scene_id)]
    env = _env(d, sc)
    pids = {p["id"] for p in env.get("props", [])}
    knobs: List[Knob] = []
    seen = set()

    def add(k: Knob) -> None:
        if k.name not in seen:
            seen.add(k.name)
            knobs.append(k)

    def prop_field(pid, key, lo, hi, log=False, default=None):
        def get(dd, pid=pid, key=key):
            p = _prop(_env(dd, dd["scenes"][_scene_idx(dd, scene_id)]), pid)
            v = p.get(key)
            return float(v if v is not None else (default if default is not None else p.get("friction", 0.6)))

        def set_(dd, v, pid=pid, key=key):
            _prop(_env(dd, dd["scenes"][_scene_idx(dd, scene_id)]), pid)[key] = round(v, 5)
        add(Knob(f"prop:{pid}.{key}", get, set_, lo, hi, log))

    def prop_vec(pid, key, i, lo, hi, base=(0.0, 0.0)):
        def get(dd, pid=pid, key=key, i=i):
            p = _prop(_env(dd, dd["scenes"][_scene_idx(dd, scene_id)]), pid)
            return float(list(p.get(key, base))[i])

        def set_(dd, v, pid=pid, key=key, i=i):
            p = _prop(_env(dd, dd["scenes"][_scene_idx(dd, scene_id)]), pid)
            vec = list(p.get(key, base))
            vec[i] = round(v, 3)
            p[key] = vec
        add(Knob(f"prop:{pid}.{key}[{i}]", get, set_, lo, hi))

    pushed = set()
    for a in sc.get("actions", []):
        t = _ref(a.get("target"))
        if a["type"] == "push" and t in pids:
            pushed.add(t)
            prop_field(t, "static_friction", 0.03, 1.5, True)
            prop_field(t, "friction", 0.005, 0.8, True)
        if a["type"] in ("lift", "use_lever") and t in pids:
            m = float(_prop(env, t).get("mass", 8.0))
            prop_field(t, "mass", max(5.0, 0.5 * m), 2.0 * m, True)
        if a["type"] == "use_lever":
            for ref in (a.get("tool"), a.get("fulcrum")):
                r = _ref(ref)
                if r in pids:
                    x = float(_prop(env, r)["position"][0])
                    w = env.get("room", {}).get("width", 1200.0) / 2 - 40
                    prop_vec(r, "position", 0, max(-w, x - 260), min(w, x + 260))
    w_room = env.get("room", {}).get("width", 1200.0) / 2 - 60
    pushers = {a["character"] for a in sc.get("actions", []) if a["type"] == "push"}
    for i_pl, pl in enumerate(sc.get("placements", [])):
        if pl["character"] in pushers:
            continue  # where the pusher starts only changes the walk-in

        def gpl(dd, i_pl=i_pl):
            return float(dd["scenes"][_scene_idx(dd, scene_id)]["placements"][i_pl]["x"])

        def spl(dd, v, i_pl=i_pl):
            dd["scenes"][_scene_idx(dd, scene_id)]["placements"][i_pl]["x"] = round(v, 1)
        x0 = float(pl["x"])
        add(Knob(f"placement:{pl['character']}.x", gpl, spl, max(-w_room, x0 - 400), min(w_room, x0 + 400)))
    for rp in env.get("ropes", []):
        rid = rp["id"]

        def gslack(dd, rid=rid):
            e = _env(dd, dd["scenes"][_scene_idx(dd, scene_id)])
            r = next(x for x in e["ropes"] if x["id"] == rid)
            if r.get("slack") is not None:
                return float(r["slack"])
            return max(0.0, float(r["length"]) - _rope_d0(e, r))

        def sslack(dd, v, rid=rid):
            e = _env(dd, dd["scenes"][_scene_idx(dd, scene_id)])
            r = next(x for x in e["ropes"] if x["id"] == rid)
            r["slack"], r["length"] = round(v, 2), None
        add(Knob(f"rope:{rid}.slack", gslack, sslack, 5.0, 260.0))
        if rp.get("break_force") is not None:
            def gbf(dd, rid=rid):
                e = _env(dd, dd["scenes"][_scene_idx(dd, scene_id)])
                return float(next(x for x in e["ropes"] if x["id"] == rid)["break_force"])

            def sbf(dd, v, rid=rid):
                e = _env(dd, dd["scenes"][_scene_idx(dd, scene_id)])
                next(x for x in e["ropes"] if x["id"] == rid)["break_force"] = round(v, 1)
            add(Knob(f"rope:{rid}.break_force", gbf, sbf, 2e4, 8e6, True))
        for end in (rp.get("a"), rp.get("b")):  # a prop yanked by a rope tied to a pushed prop: where and how it falls
            r = _ref(end)
            if r in pids and r not in pushed and any(_ref(e2) in pushed for e2 in (rp.get("a"), rp.get("b"))):
                p = _prop(env, r)
                x = float(p["position"][0])
                h = float(p.get("size", (40, 40))[1])
                w = env.get("room", {}).get("width", 1200.0) / 2 - 40
                prop_vec(r, "position", 0, max(-w, x - 220), min(w, x + 220))
                if h > 1.5 * float(p.get("size", (40, 40))[0]):
                    prop_vec(r, "com", 1, 0.0, 0.42 * h)
    return knobs


def _rope_d0(env: dict, r: dict) -> float:
    props = {p["id"]: p for p in env.get("props", [])}
    ends = []
    for ref, loc in ((r["a"], r.get("a_local", (0, 0))), (r["b"], r.get("b_local", (0, 0)))):
        k, _, v = ref.partition(":")
        if k == "prop" and v in props:
            pp = props[v]
            ang = float(pp.get("angle", 0.0))
            ca, sa = math.cos(ang), math.sin(ang)
            ends.append((pp["position"][0] + loc[0] * ca - loc[1] * sa, pp["position"][1] + loc[0] * sa + loc[1] * ca))
        else:
            ends.append(tuple(float(c) for c in v.split(",")))
    return math.dist(*ends)


# ---------------------------------------------------------------- stage 1: closed-form physics fixes
def physics_fixes(d: dict, scene_id: str, goals: List[str]) -> List[Dict[str, Any]]:
    sc = d["scenes"][_scene_idx(d, scene_id)]
    env = _env(d, sc)
    g = _gmag(env)
    adj: List[Dict[str, Any]] = []
    for a in sc.get("actions", []):
        if a["type"] != "push":
            continue
        pid = _ref(a.get("target"))
        try:
            p = _prop(env, pid)
        except StopIteration:
            continue
        F = float(a.get("effort", 1.0)) * float(_char(d, a["character"]).get("strength", 45000.0))
        m = float(p.get("mass", 8.0))
        mu_s = p.get("static_friction")
        mu_s = float(mu_s if mu_s is not None else p.get("friction", 0.6))
        if mu_s * G_FRICTION_SCALE * m * g > 0.95 * F:  # cannot break loose: put breakaway just under the push force
            new = round(0.8 * F / (G_FRICTION_SCALE * m * g), 4)
            adj.append(dict(knob=f"prop:{pid}.static_friction", old=round(mu_s, 4), new=new,
                            why=f"push force {F:.0f} could not overcome static friction {mu_s * G_FRICTION_SCALE * m * g:.0f}"))
            p["static_friction"] = new
        mu_k = float(p.get("friction", 0.6))
        if any(parse_goal(x)[0] in ("push_lost",) for x in goals) and mu_k * G_FRICTION_SCALE * m * g > 0.35 * F:
            new = round(0.2 * F / (G_FRICTION_SCALE * m * g), 4)
            adj.append(dict(knob=f"prop:{pid}.friction", old=round(mu_k, 4), new=new,
                            why="once sliding, the prop must outrun the pusher for the push to be lost"))
            p["friction"] = new
    # a goal that needs a character pinned needs an obstruction that can land on a body: heavy enough, solid to characters
    for gl in goals:
        etype, who, filt = parse_goal(gl)
        if etype != "pinned":
            continue
        cands = [filt["by"]] if filt.get("by") else [_ref(a.get("target")) for a in sc.get("actions", []) if a["type"] in ("lift", "use_lever")]
        for pid in dict.fromkeys(c for c in cands if c):
            try:
                p = _prop(env, pid)
            except StopIteration:
                continue
            if not p.get("collide_characters", True) or not p.get("solid", True):
                adj.append(dict(knob=f"prop:{pid}.collide_characters", old=False, new=True,
                                why=f"goal {gl} needs {pid} to be able to land on a character"))
                p["collide_characters"], p["solid"] = True, True
            if float(p.get("mass", 8.0)) < 25.0:
                adj.append(dict(knob=f"prop:{pid}.mass", old=p.get("mass", 8.0), new=25.0, why=f"goal {gl}: too light to pin anyone"))
                p["mass"] = 25.0
    for r in env.get("ropes", []):
        if r.get("slack") is None and r.get("length") is not None:
            d0 = _rope_d0(env, r)
            if float(r["length"]) < d0 + 2.0:
                adj.append(dict(knob=f"rope:{r['id']}.slack", old=round(float(r["length"]) - d0, 1), new=40.0,
                                why="the rope started shorter than the distance between its ends"))
                r["slack"], r["length"] = 40.0, None
        if r.get("break_force") is None and any(parse_goal(x)[0] == "rope_snap" and parse_goal(x)[1] in (None, r["id"]) for x in goals):
            adj.append(dict(knob=f"rope:{r['id']}.break_force", old=None, new=600000.0, why="the story needs this rope to snap"))
            r["break_force"] = 600000.0
    return adj


def placement_fix(d: dict, scene_id: str, trial: "Trial") -> List[Dict[str, Any]]:
    """If a character fell but was not pinned, move the prop that topples so that its fall covers the fallen body.

    The fall position comes from the simulation itself (the `body_fall` event), so the planner does not have to guess
    it; the prop's toppling direction is toward the other end of the rope that yanks it."""
    if trial.missing is None or parse_goal(trial.missing)[0] != "pinned":
        return []
    _, who, filt = parse_goal(trial.missing)
    fall = next((e for e in trial.events if e.type == "body_fall" and (who is None or e.character == who)), None)
    if fall is None or "point" not in fall.data:
        return []
    sc = d["scenes"][_scene_idx(d, scene_id)]
    env = _env(d, sc)
    pushed = {_ref(a.get("target")) for a in sc.get("actions", []) if a["type"] == "push"}
    out = []
    for rp in env.get("ropes", []):
        ends = [_ref(rp["a"]), _ref(rp["b"])]
        for i, pid in enumerate(ends):
            other = ends[1 - i]
            if pid is None or pid in pushed or other not in pushed or (filt.get("by") and filt["by"] != pid):
                continue
            p, q = _prop(env, pid), _prop(env, other)
            w, h = p.get("size", (40, 40))
            if h < 1.5 * w:
                continue  # not a tall thing that topples
            direction = 1.0 if q["position"][0] >= p["position"][0] else -1.0
            fx = float(fall.data["point"][0])
            want = fx - direction * 0.55 * h  # the body lies a little past the middle of the falling length
            if abs(p["position"][0] - want) < 0.2 * h:
                continue
            lo_q = q["position"][0] - q.get("size", (40, 40))[0] / 2
            hi_q = q["position"][0] + q.get("size", (40, 40))[0] / 2
            half = env.get("room", {}).get("width", 1200.0) / 2 - w
            if lo_q - w <= want <= hi_q + w or abs(want) > half:
                continue
            out.append(dict(knob=f"prop:{pid}.position[0]", old=p["position"][0], new=round(want, 1),
                            why=f"{who or 'the character'} fell at x={fx:.0f}; place {pid} so its fall covers the body"))
            p["position"] = [round(want, 1), p["position"][1]]
    return out


LEVER_GOALS = ("lever_place", "lever_engage", "load_off", "freed", "crawl_start")


def lever_fix(d: dict, scene_id: str, trial: "Trial") -> List[Dict[str, Any]]:
    """If the lever part of the story fails, put the fulcrum where a bar can work: about 0.3 bar-lengths beyond the end
    of the load *as it actually came to rest* in the simulation, on the helper's side; the bar a short run from there."""
    if trial.missing is None or parse_goal(trial.missing)[0] not in LEVER_GOALS or trial.result is None:
        return []
    sc = d["scenes"][_scene_idx(d, scene_id)]
    env = _env(d, sc)
    act = next((a for a in sc.get("actions", []) if a["type"] == "use_lever"), None)
    if act is None:
        return []
    load, ful, bar = _ref(act["target"]), _ref(act["fulcrum"]), _ref(act["tool"])
    pin = next((e for e in trial.events if e.type == "pinned"), None)
    tr = trial.result.prop_tracks.get(load)
    if tr is None or ful is None or bar is None:
        return []
    i = len(tr) - 1
    if pin is not None:
        i = min(len(tr) - 1, int(round((pin.t + 0.6) / (trial.result.prop_times[1] - trial.result.prop_times[0]))))
    x, y, ang = tr[i]
    lp = _prop(env, load)
    w, h = lp.get("size", (40, 40))
    half = (w if w >= h else h) / 2
    ax = (math.cos(ang), math.sin(ang)) if w >= h else (-math.sin(ang), math.cos(ang))
    ends = sorted([x + ax[0] * half, x - ax[0] * half])
    helper = next(pl for pl in sc["placements"] if pl["character"] == act["character"])
    hx = float(helper["x"])
    pinned_c = pin.character if pin is not None else None
    px = trial.result.controllers[pinned_c].s if pinned_c in trial.result.controllers else x
    # lift the end nearer the pinned body: that is the part that has to rise (the far end stays on the floor as the pivot)
    end = ends[1] if abs(ends[1] - px) < abs(ends[0] - px) else ends[0]
    direction = 1.0 if end >= x else -1.0
    L = float(_prop(env, bar).get("size", (175, 7))[0])
    want_f = end + direction * 0.3 * L
    room = env.get("room", {}).get("width", 1200.0) / 2 - 40
    want_b = max(-room, min(room, want_f + direction * (0.3 * L + 120.0)))
    fp, bp = _prop(env, ful), _prop(env, bar)
    out = []
    if abs(fp["position"][0] - want_f) > 0.12 * L and abs(want_f) < room:
        out.append(dict(knob=f"prop:{ful}.position[0]", old=fp["position"][0], new=round(want_f, 1),
                        why=f"{load} came to rest with an end at x={end:.0f}; a {L:.0f}-long bar needs its fulcrum ~{0.3 * L:.0f} beyond it"))
        fp["position"] = [round(want_f, 1), fp["position"][1]]
        if fp.get("solid", True) or fp.get("collide_characters", True):
            # moved set dressing must not change the accident (block the sliding load or trip a character); the lever
            # pins to the fulcrum's top point, so the fulcrum needs no collision shape
            out.append(dict(knob=f"prop:{ful}.solid", old=fp.get("solid", True), new=False,
                            why="a relocated fulcrum is set dressing (it must not block the earlier action)"))
            fp["solid"], fp["collide_characters"] = False, False
            fp["z"] = max(float(fp.get("z", 0.0)), 30.0)
    if abs(bp["position"][0] - want_b) > 300.0 and not bp.get("solid", True):  # a solid bar on the floor would block things too
        out.append(dict(knob=f"prop:{bar}.position[0]", old=bp["position"][0], new=round(want_b, 1),
                        why=f"the bar was {abs(bp['position'][0] - want_f):.0f} units from where it is needed"))
        bp["position"] = [round(want_b, 1), bp["position"][1]]
    return out


# ---------------------------------------------------------------- stage 2: search
def _partial(goal: Optional[str], d: dict, scene_id: str, r) -> float:
    """A measure in [0, 1) of how close the simulation came to the first missing goal."""
    if goal is None:
        return 0.0
    etype, who, filt = parse_goal(goal)
    sc = d["scenes"][_scene_idx(d, scene_id)]
    env = _env(d, sc)
    if etype in ("push_lost", "body_fall"):
        for a in sc.get("actions", []):
            if a["type"] == "push" and (who is None or a["character"] == who):
                tr = r.prop_tracks.get(_ref(a["target"]))
                if tr is not None:
                    return min(0.95, abs(float(tr[-1, 0] - tr[0, 0])) / 80.0)
    if etype == "rope_snap":
        best = 0.0
        for rp in env.get("ropes", []):
            if who in (None, rp["id"]) and rp.get("break_force"):
                best = max(best, min(0.95, r.rope_peak.get(rp["id"], 0.0) / float(rp["break_force"])))
        return best
    if etype == "pinned" and who in r.controllers:
        c = r.controllers[who]
        by = filt.get("by")
        best = 0.0
        for p in env.get("props", []):
            if (by and p["id"] != by) or float(p.get("mass", 8)) < 20 or not p.get("collide_characters", True):
                continue
            x, _, ang = r.prop_tracks[p["id"]][-1]
            w, h = p.get("size", (40, 40))
            half = 0.5 * (abs(w * math.cos(ang)) + abs(h * math.sin(ang)))
            body = sorted((c.s - c.facing * (c.p_leg + 10.0), c.s + c.facing * c.stand_h * 0.55))
            gap = max(0.0, max(body[0] - (x + half), (x - half) - body[1]))
            best = max(best, 0.95 * (1.0 - min(1.0, gap / 260.0)))
        return best
    return 0.0


def evaluate(d: dict, scene_id: str, goals: List[str], ordered: bool, horizon: float, fit: Optional[float] = None) -> Trial:
    """Score one setup. `fit` is the time by which the last goal should have happened (the planned length minus a tail)."""
    from .runtime import SceneRuntime
    try:
        proj = ProjectSpec.model_validate(d)
        r = SceneRuntime(proj, scene_id, strict=False).simulate(physics_only=True, horizon=horizon)
    except (ValueError, KeyError) as e:  # a plan the runtime cannot execute at all
        return Trial(-1.0, 0, len(goals), goals[0] if goals else None, [], [None] * len(goals), [], str(e)[:400])
    met, times, missing = progress(goals, r.events, ordered=ordered)
    stuck = stuck_characters(r)
    for cid, c in r.controllers.items():
        if getattr(c, "violation", None):
            stuck.append(c.violation)
    score = 10.0 * met + _partial(missing, d, scene_id, r)
    over = 0.0
    if met == len(goals) and not stuck:
        last = max([t for t in times if t is not None] or [0.0])
        over = max(0.0, last - fit) if fit is not None else 0.0
        score += 5.0 - 0.01 * last - 0.25 * over  # the story should fit the planned length
    tr = Trial(score, met, len(goals), missing, stuck, times, r.events, None, r)
    tr.over = over
    return tr


def solve(project: ProjectSpec, scene_id: str, goals: Optional[List[str]] = None, budget: int = 90, seed: int = 0,
          max_duration: float = 30.0, tail: float = 2.5, restarts: int = 3) -> Tuple[ProjectSpec, SolveReport]:
    """Tune the physical setup until the goals happen (or the budget runs out). Returns (project, report)."""
    d = json.loads(project.model_dump_json())
    sc = d["scenes"][_scene_idx(d, scene_id)]
    ordered = bool(goals if goals is not None else sc.get("goals"))
    goals = list(goals if goals is not None else (sc.get("goals") or derive_goals(project.scene(scene_id))))
    duration = float(sc["duration"])
    horizon = min(max_duration, max(duration * 1.5, duration + 8.0))
    fit = duration - tail
    adjustments = physics_fixes(d, scene_id, goals)
    env = _env(d, sc)
    for r in env.get("ropes", []):  # hold slack (not length) fixed, so moving a prop does not silently tighten a rope
        if r.get("slack") is None and r.get("length") is not None:
            r["slack"], r["length"] = round(max(0.0, float(r["length"]) - _rope_d0(env, r)), 3), None
    best = evaluate(d, scene_id, goals, ordered, horizon, fit)
    evals = 1
    for _ in range(3):  # where things actually happened in a run decides where props go (pin, then lever)
        geo = placement_fix(d, scene_id, best) or lever_fix(d, scene_id, best)
        if not geo:
            break
        adjustments += geo
        best = evaluate(d, scene_id, goals, ordered, horizon, fit)
        evals += 1
    knobs = find_knobs(d, scene_id)
    start = {k.name: k.get(d) for k in knobs}
    base_d, base = d, best
    best_d = d
    done = lambda tr: tr.complete and tr.over <= 0.0
    # search until the goals happen and fit the planned length, or the budget runs out; the budget is split over
    # `restarts` independent local searches from the same physics-fixed start (one unlucky path does not decide it)
    per_run = max(1, (budget - evals) // max(1, restarts))
    for rs in range(max(1, restarts)):
        if done(best) or not knobs or best.error is not None or evals >= budget:
            break
        rng = random.Random(seed * 1000 + rs)
        cur_d, cur = base_d, base
        sigma, stop = 0.35, min(budget, evals + per_run)
        while evals < stop and not done(cur):
            cand = copy.deepcopy(cur_d)
            for k in rng.sample(knobs, min(len(knobs), rng.choice((1, 1, 2, 3)))):
                v = k.get(cand)
                if rng.random() < 0.2:  # occasional global jump
                    nv = math.exp(rng.uniform(math.log(k.lo), math.log(k.hi))) if k.log and k.lo > 0 else rng.uniform(k.lo, k.hi)
                elif k.log and v > 0:
                    nv = v * math.exp(rng.gauss(0.0, sigma * 1.6))
                else:
                    nv = v + rng.gauss(0.0, sigma * (k.hi - k.lo) * 0.5)
                k.set(cand, k.clip(nv))
            tr = evaluate(cand, scene_id, goals, ordered, horizon, fit)
            evals += 1
            if tr.score > cur.score:
                cur_d, cur = cand, tr
            else:
                sigma = max(0.08, sigma * 0.97)
        if cur.score > best.score:
            best_d, best = cur_d, cur
    for k in knobs:
        old, new = start[k.name], k.get(best_d)
        if abs(new - old) > 1e-6 * max(1.0, abs(old)):
            adjustments.append(dict(knob=k.name, old=round(old, 4), new=round(new, 4), why="setup search (goal-driven)"))
    note = ""
    if best.error:
        note = f"the action list itself fails in simulation: {best.error}"
    elif not best.complete and best.missing:
        note = (f"no setting of {', '.join(k.name for k in knobs) or 'the physical setup'} produced '{best.missing}'; "
                "change the actions, their order or the props involved")
    # scene length: extended only if the goals do not fit (never shorter than planned)
    sc2 = best_d["scenes"][_scene_idx(best_d, scene_id)]
    last = max([t for t in best.times if t is not None] or [0.0])
    new_dur = duration
    if best.complete and last > duration - 0.5:  # only when the goals do not fit in the planned length
        new_dur = min(max_duration, max(duration, math.ceil((last + tail) * 24) / 24))
        if new_dur > duration + 1e-6:
            adjustments.append(dict(knob="scene.duration", old=duration, new=new_dur, why="the goals finish later than planned"))
            sc2["duration"] = new_dur
            shots = sorted(sc2["shots"], key=lambda s: s["start"])
            shots[-1]["end"] = new_dur
    report = SolveReport(goals, ordered, adjustments, evals, best.complete, best.met, best.missing, best.stuck,
                         best.times, new_dur, note)
    return ProjectSpec.model_validate(best_d), report


# ---------------------------------------------------------------- event-timed cuts
def resolve_cuts(project: ProjectSpec, scene_id: str, events=None, min_shot: float = 0.5) -> ProjectSpec:
    """Place every `cut_on` shot at its simulated event time; shots between anchors are spread evenly."""
    sc0 = project.scene(scene_id)
    if not any(s.cut_on for s in sc0.shots):
        return project
    if events is None:
        from .runtime import SceneRuntime
        events = SceneRuntime(project, scene_id).simulate(physics_only=True).events
    d = json.loads(project.model_dump_json())
    sc = d["scenes"][_scene_idx(d, scene_id)]
    shots = sorted(sc["shots"], key=lambda s: s["start"])
    D = float(sc["duration"])
    starts: List[Optional[float]] = [0.0] + [None] * (len(shots) - 1)
    prev = 0.0
    for i, s in enumerate(shots):
        if i == 0 or not s.get("cut_on"):
            continue
        goal = s["cut_on"].split(":", 1)[1]
        hit = next((e for e in events if matches(goal, e) and e.t + s.get("cut_offset", 0.0) > prev + min_shot - 1e-9), None)
        if hit is None:
            raise ValueError(f"shot {s['id']}: cut_on {s['cut_on']} never happens after the previous cut "
                             f"(at {prev:.2f}s) in the simulation")
        starts[i] = round(hit.t + s.get("cut_offset", 0.0), 3)
        prev = starts[i]
    # unanchored shots: keep their planned share of the gap between the anchors around them
    anchors = [i for i, v in enumerate(starts) if v is not None] + [len(shots)]
    for a, b in zip(anchors, anchors[1:]):
        t0 = starts[a]
        t1 = starts[b] if b < len(shots) else D
        p0 = shots[a]["start"]
        p1 = shots[b]["start"] if b < len(shots) else shots[-1]["end"]
        for j in range(a + 1, b):
            u = (shots[j]["start"] - p0) / (p1 - p0) if p1 > p0 else (j - a) / (b - a)
            starts[j] = round(t0 + u * (t1 - t0), 3)
    for i, s in enumerate(shots):
        s["start"] = starts[i]
        s["end"] = starts[i + 1] if i + 1 < len(shots) else D
        if s["end"] - s["start"] < min_shot - 1e-9:
            raise ValueError(f"shot {s['id']}: only {s['end'] - s['start']:.2f}s long after event-timed cuts "
                             f"(its cut event comes too soon after the previous one, or the order differs from the shots)")
    sc["shots"] = shots
    return ProjectSpec.model_validate(d)
