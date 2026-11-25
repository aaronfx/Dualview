"""AI Story Director: natural-language story -> validated ProjectSpec (structured animation data, not prose).

The LLM is only a planner. Its output must validate against the scene schema and pass a dry-run simulation
before it is accepted; validation errors are fed back for a bounded number of repair attempts. The engine
(simulation, motion, rendering) never depends on the LLM.
"""
from __future__ import annotations

import difflib
import json
import math
import re
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from ..scene.schema import SCHEMA_VERSION, ProjectSpec
from .budget import BudgetError
from .providers import Provider, provider_from_env

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "foundry_flip.json"
# a small two-character physical-interaction example (not The Rescue): teaches structure, not the answer
INTERACTION_EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "runaway_crate.json"

ACTION_HELP = {
    "idle": "stand (duration)", "walk_to": "walk to target_x, or to a 'char:'/'prop:' target", "run_to": "run (same targets as walk_to)",
    "turn": "face=+1/-1", "press": "press a switch (switch)", "jump": "running jump (height)", "look_around": "look around (duration)",
    "wait_grounded": "wait until standing on a surface again", "look_at": "look at target (duration)", "notice": "double take at target",
    "point": "point at target", "duck_slide": "slide feet-first to target_x", "jump_to": "standing jump to target_x (height, optional switch; onto obstacle: lands on its top; flip front|back)",
    "grab_swing": "catch a bar while falling (target bar:)", "reach_exit": "walk out through an open exit (target exit:)",
    "push": "push a prop (target prop:, effort 0.5-1.6 of the character's strength); if it breaks loose and outruns the character, "
            "contact is lost and the character stumbles and FALLS PRONE (physics decides)",
    "lift": "try to lift the nearest end of a prop by hand (target prop:, effort, duration); too heavy simply does not rise",
    "use_lever": "fetch a bar (tool prop:), place it over a fulcrum (fulcrum prop:) under the load (target prop: = the prop "
                 "lying ON the trapped character) and bear down; picking up and placing the bar are part of this action; "
                 "holds until `until` event",
    "struggle": "while lying prone: struggle (duration or until)", "crawl_out": "while prone: wait until the load is off, crawl out (emits freed)",
    "get_up": "while prone: get up; with target char: take that character's offered hand",
    "offer_hand": "walk to a lying/kneeling character (target char:) and offer a hand, pull them up",
    "gesture": "gesture with another character (target char:, gesture fist_bump|shoulder_pat|wave)",
    "wait_for": "wait until an event happens (until 'event:<type>[@<who>]' = has happened at any time; "
                "'next:<type>[@<who>]' = the next one after this action starts)",
    "strike": "attack another character (target char:, move jab|cross|hook|uppercut|front_kick|side_kick|roundhouse|sweep|"
              "flying_kick (a jumping kick)|swing_weapon (swing the carried prop), "
              "power 0.3-2, optional reaction flinch|stagger|knockdown); closes to range first; the simulation decides "
              "hit / blocked (target guarding and facing) / whiff (out of reach, ducked); knockdowns are physics falls",
    "guard": "fighting stance with fists up (duration or until); blocks head and body strikes from the front",
    "dodge": "dodge = back (step out of reach) or duck (under head-height strikes)",
    "roll": "forward roll along the floor (distance, or target_x); right after a jump it is a landing roll",
    "vault": "vault over a low structure or prop (target obstacle:/prop:, top under ~0.95 body height)",
    "climb": "climb onto the top of a platform or glyph structure from beside it (target obstacle:): hang, pull up, stand",
    "wall_kick": "run at a wall (room wall, or target obstacle:), two steps up it, push off to land at target_x (height; flip back)",
    "pick_up": "pick up a light prop, e.g. a glyph (target prop:); carried in both hands until thrown",
    "throw": "throw the carried prop at a character or point (target char:/point:); the simulation decides hit / blocked / miss",
}
EVENT_TYPES = ("footstep turn notice point press_contact switch_activated gravity_shift lost_support impact recovered takeoff "
               "push_start push_lost rope_taut rope_snap body_fall pinned load_off lift_start lift_fail lift_ok pick_up lever_place "
               "lever_engage lever_release crawl_start freed get_up_start hand_offered hand_grab stood_up fist_bump shoulder_pat prop_impact "
               "strike_start swing hit hurt blocked block_hit whiff evaded knockdown settled dodge gesture_start "
               "step_off flip roll_start roll_end vault climbed ledge_grab wall_contact wall_kick throw prop_hit")


def system_prompt() -> str:
    """The planner's contract, generated from the live schema (action list, required fields, names)."""
    from ..audio.sound_director import SOUND_NAMES
    from ..scene.schema import ActionSpec, PropSpec
    from .objective_planner import ActorObjective
    import typing
    acts = typing.get_args(ActionSpec.model_fields["type"].annotation)
    kinds = typing.get_args(PropSpec.model_fields["kind"].annotation)
    lines = "\n".join(f"  - {a}: {ACTION_HELP.get(a, '')}" for a in acts)
    return f"""You are the APEX Story Director. Convert the user's story into ONE JSON object that validates against the
APEX scene schema v{SCHEMA_VERSION}. Output JSON only. The engine SIMULATES physics: you describe intentions and the
physical setup; the simulation decides outcomes. Do not fake an action with `idle` + a note when an action exists for it.
Action types: ONLY these (each action has `character`; durations in seconds). Anything else (e.g. "pick_up", "pull") is
not an action; events such as pick_up are emitted BY actions and can only be waited for:
{lines}
Props (environment.props): kinds {", ".join(kinds)}; fields id, kind, position [x, y-centre], size [w, h], mass, angle (rad),
friction (sliding), static_friction (at rest: heavy things break loose), collide_characters, solid (false = fixed set dressing
until picked up, e.g. a tool on a rack), com (centre of mass offset, e.g. a top-heavy post), z (depth; negative = nearer the camera).
Ropes (environment.ropes): straps between props ("prop:<id>" ends, a_local/b_local attachment points), slack (extra length beyond
the initial distance; preferred over length), break_force (snaps).
PHYSICAL NUMBERS ARE THE ENGINE'S JOB: give plausible masses, frictions, slack and positions, and list the story beats in
scene.goals, in order, as "<event>@<who>" (optionally "[key=value]"), e.g. ["push_lost@a", "rope_snap", "pinned@a[by=post]",
"lift_fail@b", "freed@a", "stood_up@a"]. APEX's setup solver simulates the scene and tunes frictions, masses, rope slack and
break force, and the positions of the props involved until the goals happen. You do not need exact values; you do need the right
actions, props and order. Use `until` events to synchronise characters.
Shot timing: give each shot after the first a cut_on event ("event:<type>@<who>", optional cut_offset seconds) so the cut lands
when the event happens in the simulation; approximate start/end values are then rewritten by the engine.
Characters: id, name, proportions, style (colours, cadence/stride/lean/arm_swing scales), strength (max hand force, ~40000-60000).
Targets: "switch:<id>", "exit:<id>", "bar:<id>", "prop:<id>", "char:<id>", "point:x,y". Coordinates: x along the floor, room spans
[-width/2, width/2]; gravity [0,-1568]; standing pelvis ~95 above the floor; a character is ~175 tall.
Shots: contiguous, start at 0, end exactly at the scene duration; kinds establishing|wide|medium|close|insert|tracking; camera modes
static|follow|track_x|dolly; camera.target is a placed character's bare ID (not char: or prop:); camera.include lists targets to keep in frame (e.g. "char:<id>", "prop:<id>").
exit_conditions: "event:<type>" with types from: {EVENT_TYPES}.
sound_cues: {{on_event, sound, gain}}; sound must be one of: {", ".join(SOUND_NAMES)}.
Keep characters consistent: one CharacterSpec per character, referenced by id everywhere. Include only what the story
needs: no switches, exits or gravity changes unless the story asks for them.
OPTIONAL CREATIVE PLAN: When constructing math-world, arcade/rhythm, or multi-scene epic stories, include a top-level
creative_plan with "profile" = math|arcade|epic|hybrid, "premise", optional "initial_state": {{key: state}},
and "beats": [{{"id", "scene", "t", "kind", "intent", "actor", "causes": ["previous_id"],
"requires": {{}}, "effects": {{}}, optional "proof_event": "eventtype@actor",
optional "on_beat": true, "film_t": seconds, optional "math": {{"before": typed_AST, "after": typed_AST}}}}].
Beat kinds: setup|discovery|obstacle|response|reversal|payoff|transition. Every non-setup beat must name its
earlier cause; changing world state must be motivated by a previous beat. A proof_event must actually be emitted
at time t by simulation. For math expression trees use strictly typed operations int(value), var(value),
add(args), sub(args), mul(args), div(args), pow(args), eq(args). NEVER invent a physics event for a mathematical
operation unless APEX has an implemented action that triggers it. Avoid claims that equations rewrite physically
until that engine feature exists. If profile=arcade, music beat markers refer to FILM time, including slow motion.
A creative plan is optional; do not add it to simple projects where it serves no purpose.
NATIVE PLANNING (optional top-level native_plans, NOT a scene-schema field): for a scene with explicit goals, you may
delegate actors to existing native planners rather than write all their movement. Up to four entries, at most one per scene.
Each entry is {{"tool":"objectives","request":{{"scene_id":"s","max_trials":4,"tasks":[{{"id":"find","actor":"a",
"kind":"observe","target":"prop:core","after":[],"urgency":"urgent"}}]}}}}.
Objective kinds: {", ".join(typing.get_args(ActorObjective.model_fields["kind"].annotation))}.
Or use {{"tool":"ensemble","request":{{"scene_id":"s","tasks":[{{"id":"find","actor":"a","after":[],
"proof":"notice@a[target=prop:core]","alternatives":[[{{"character":"a","type":"notice","target":"prop:core"}}]]}}]}}}}.
Use actual placed actors, existing targets, explicit outcome goals, and duration <=60 seconds. Each delegated actor must
have no authored actions in that scene; other actors' actions are retained. Dependencies are task IDs, not timestamps.
For throw_at or evade_projectile, specify prop as an existing prop:<id> and target as char:<id>.
An evade_projectile defender has only its independent reaction task and waits for the specified release; no after dependency.
Allow at least three seconds after release for the native flight observation. A release alone is not a successful hit.
The native planner chooses and rehearses alternatives; failed plans are rejected, never replaced with a generic story.
Do not use this for a complex scene whose goals cannot be represented by those tools; use normal native actions instead.
REPAIRS: when told your previous output was invalid, reply with ONLY {{"patch": [...]}}: RFC 6902 operations
({{"op": "replace"|"add"|"remove", "path": "/scenes/0/actions/3/until", "value": ...}}) against your previous JSON, not a full
rewrite."""


SYSTEM = system_prompt.__doc__  # kept for backwards compatibility; the live prompt is system_prompt()


class PlanningError(RuntimeError):
    pass


def _allowed_at(loc) -> Optional[List[str]]:
    """The field names allowed at a validation-error location (walks ProjectSpec's annotations)."""
    import typing
    from ..scene import schema as S
    model = S.ProjectSpec
    for part in list(loc)[:-1]:
        if isinstance(part, int):
            continue
        f = model.model_fields.get(part)
        if f is None:
            return None
        ann, found = f.annotation, None
        stack = [ann]
        while stack:
            a = stack.pop()
            if isinstance(a, type) and issubclass(a, S.BaseModel):
                found = a
                break
            stack.extend(typing.get_args(a))
        if found is None:
            return None
        model = found
    return sorted(model.model_fields)


def _field_names() -> List[str]:
    from ..scene import schema as S
    names = set()
    for obj in vars(S).values():
        if isinstance(obj, type) and issubclass(obj, S.BaseModel) and obj is not S.BaseModel:
            names.update(obj.model_fields)
    return sorted(names)


def apply_patch(doc: dict, ops: list) -> dict:
    """Minimal RFC 6902 (add / replace / remove) on a deep copy of `doc`."""
    import copy as _copy
    out = _copy.deepcopy(doc)
    if not isinstance(ops, list):
        raise ValueError("patch must be a list of operations")
    for i, op in enumerate(ops):
        if not isinstance(op, dict):
            raise ValueError(f"patch op {i}: expected an object")
        kind, path = op.get("op"), op.get("path", "")
        if kind not in ("add", "replace", "remove") or not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"patch op {i}: need op add|replace|remove and a path starting with '/' (got {op})")
        parts = [p.replace("~1", "/").replace("~0", "~") for p in path[1:].split("/")]
        parent = out
        for p in parts[:-1]:
            parent = parent[int(p)] if isinstance(parent, list) else parent[p]
        last = parts[-1]
        if isinstance(parent, list):
            if kind == "add":
                parent.insert(len(parent) if last == "-" else int(last), op["value"])
            elif kind == "replace":
                parent[int(last)] = op["value"]
            else:
                del parent[int(last)]
        else:
            if kind == "remove":
                del parent[last]
            else:  # "replace" of a missing key is treated as "add" (planners use replace to set optional fields)
                parent[last] = op["value"]
    return out


class StoryDirector:
    def __init__(self, provider: Optional[Provider] = None, max_repairs: int = 2):
        self.provider = provider
        self.max_repairs = max_repairs  # paid providers are further capped by the budget policy (APEX_AI_MAX_CALLS)
        self.log: List[dict] = []  # every raw response and the error fed back to it (preserved by `apex plan --log-dir`)
        self.cost_record: Optional[dict] = None  # the experiment's ledger record (model, reason, estimate, actual cost)
        self.accepted_ai_plan: Optional[dict] = None  # the plan exactly as the model wrote it (before engine tuning)
        self.engine_report: Optional[list] = None  # what APEX's solver changed, and why

    @property
    def name(self) -> str:
        return self.provider.name if self.provider else "offline-template"

    @classmethod
    def from_env(cls, offline: bool = False, reason: str = "") -> "StoryDirector":
        """Raises budget.BudgetError when the spending policy refuses the configured paid model (nothing is sent)."""
        return cls(None if offline else provider_from_env(reason=reason))

    # ------------------------------------------------------------ public
    def plan(self, story: str) -> ProjectSpec:
        if self.provider is None:
            return TemplatePlanner().plan(story)
        # the gravity/switch example only when the story is about that (otherwise its hatch and switch get copied)
        gravity_story = re.search(r"gravity|switch|button|hatch|ceiling|wall", story, re.I) is not None
        example = EXAMPLE.read_text(encoding="utf-8") if (EXAMPLE.exists() and gravity_story) else ""
        inter = INTERACTION_EXAMPLE.read_text(encoding="utf-8") if INTERACTION_EXAMPLE.exists() else ""
        user = (f"STORY:\n{story}"
                + (f"\n\nEXAMPLE OF A VALID PROJECT (structure reference, do not copy its story):\n{example}" if example else "")
                + (f"\n\nEXAMPLE OF A TWO-CHARACTER PHYSICAL INTERACTION (structure reference: events, posture order, goals, "
                   f"cut_on; do not copy its story):\n{inter}" if inter else ""))
        errors: List[str] = []
        status, note = "failed", ""
        prev: Optional[dict] = None  # the last plan that parsed as JSON (repairs are patches against it)
        try:
            for attempt in range(self.max_repairs + 1):
                if not errors:
                    prompt = user
                else:
                    base = json.dumps(prev, separators=(",", ":")) if prev is not None else "(none: your output was not JSON)"
                    prompt = (f"STORY:\n{story}\n\nYOUR PREVIOUS JSON:\n{base}\n\nIT WAS INVALID:\n{errors[-1]}\n\n"
                              + ('Reply with ONLY {"patch": [...]} (RFC 6902 operations against YOUR PREVIOUS JSON).'
                                 if prev is not None else "Return the complete corrected JSON object."))
                try:
                    raw = self.provider.complete(system_prompt(), prompt, max_tokens=16000) or ""
                except BudgetError as e:  # a spending limit stops planning; it is never retried with another model
                    note = f"stopped by the spending policy: {e}"
                    raise PlanningError(note) from e
                entry = {"attempt": attempt + 1, "raw_response": raw, "fed_back_error": errors[-1] if errors else None}
                usage = getattr(getattr(self.provider, "inner", None), "last_usage", None) or {}
                if usage.get("completion_tokens") and len(raw) < 0.5 * usage["completion_tokens"]:
                    entry["warning"] = (f"billed {usage['completion_tokens']} output tokens for {len(raw)} visible characters "
                                        "(hidden reasoning or truncation)")
                self.log.append(entry)
                try:
                    data = self._parse_json(raw, prev)
                    prev = data
                    from .plan_compiler import compile_project
                    from .story_native_plans import split_native_plans, execute_native_plans, verify_native_plans
                    project_data, native_plans = split_native_plans(data)
                    proj, repairs = compile_project(project_data)
                    entry["compiler_repairs"] = [r.as_dict() for r in repairs]
                    entry["native_planning"] = []
                    proj, contracts = execute_native_plans(proj, native_plans, entry["native_planning"])
                    proj, report = self.prepare(proj)
                    verify_native_plans(proj, contracts)
                    entry["engine_adjustments"] = report
                    status = "accepted"
                    self.accepted_ai_plan, self.engine_report = data, report
                    return proj
                except (ValidationError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as e:
                    msg = self._explain(e)
                    entry["rejected_because"] = msg[:4000]
                    errors.append(msg[:3000])
            note = errors[-1][:500]
            raise PlanningError(f"planner output failed validation after {self.max_repairs + 1} attempts: {errors[-1][:500]}")
        finally:
            exp = getattr(self.provider, "experiment", None)
            if exp is not None:
                self.cost_record = exp.finish(status, note)

    @staticmethod
    def _parse(raw: str) -> ProjectSpec:
        return StoryDirector._validate(StoryDirector._parse_json(raw, None))

    @staticmethod
    def _parse_json(raw: str, prev: Optional[dict]) -> dict:
        """The response as a project dict: a full JSON object, or {"patch": [...]} applied to the previous plan."""
        m = re.search(r"\{.*\}", raw or "", re.S)
        if not m:
            raise ValueError("no JSON object in response (empty or truncated output)")
        data = json.loads(m.group(0))
        if isinstance(data, dict) and set(data) == {"patch"}:
            if prev is None:
                raise ValueError("a patch needs a previous plan; return the complete JSON object")
            return apply_patch(prev, data["patch"])
        return data

    @staticmethod
    def _validate(data: dict) -> ProjectSpec:
        return ProjectSpec.model_validate(data)

    @staticmethod
    def _explain(e: Exception) -> str:
        """Error text for the planner, with 'did you mean' hints for unknown field names."""
        if isinstance(e, ValidationError):
            hints = []
            for err in e.errors():
                if err.get("type") == "extra_forbidden" and err.get("loc"):
                    bad = str(err["loc"][-1])
                    allowed = _allowed_at(err["loc"])
                    near = difflib.get_close_matches(bad, allowed or _field_names(), n=3, cutoff=0.5)
                    near = [n for n in near if n != bad]
                    hints.append(f"unknown field '{bad}' at {'/'.join(map(str, err['loc']))}"
                                 + (f": did you mean {' or '.join(repr(n) for n in near)}?" if near else "")
                                 + (f" (allowed there: {', '.join(allowed)})" if allowed else ""))
            return str(e) + ("\nHINTS: " + "; ".join(hints) if hints else "")
        return str(e)

    @staticmethod
    def prepare(proj: ProjectSpec) -> tuple:
        """APEX's own physics and validation: tune the setup until the goals happen, time the cuts, then dry-run.

        Returns (project, report). Raises ValueError (fed back to the planner) when the story structure cannot work."""
        from ..scene.solver import resolve_cuts, solve
        StoryDirector._check_sounds(proj)
        reports = []
        for sc in proj.scenes:
            proj, rep = solve(proj, sc.id)
            reports.append({"scene": sc.id, "goals": rep.goals, "success": rep.success, "simulations": rep.evaluations,
                            "adjustments": rep.adjustments, "goal_times": rep.goal_times, "summary": rep.summary()})
            if not rep.success:
                raise ValueError(f"scene {sc.id}: {rep.summary()}")
            proj = resolve_cuts(proj, sc.id)
        StoryDirector._dry_run(proj)
        return proj, reports

    @staticmethod
    def _dry_run(proj: ProjectSpec) -> None:
        """A plan is only accepted if every sound exists and every scene simulates (catches impossible directives early)."""
        from ..scene.goals import progress
        from ..scene.runtime import SceneRuntime
        from ..scene.solver import stuck_characters
        StoryDirector._check_sounds(proj)
        creative_evidence = {}
        for sc in proj.scenes:
            r = SceneRuntime(proj, sc.id).simulate(physics_only=True)
            if proj.creative_plan is not None:
                creative_evidence[sc.id] = r.events
            # every character must get through its action list: a step that never completes means the physical setup
            # did not produce what the story needs (e.g. a wait_for event that never happened)
            stuck = stuck_characters(r)
            if sc.goals:
                met, _, missing = progress(sc.goals, r.events, ordered=True, before=sc.duration)
                if missing:
                    stuck.append(f"story goal '{missing}' did not happen (in order) within {sc.duration:.1f}s")
            if stuck:
                happened = ", ".join(f"{e.t:.1f}s {e.type}@{e.character}" for e in r.events
                                     if e.type not in ("footstep", "turn", "prop_impact"))[:1500]
                raise ValueError(f"scene {sc.id}: the simulation did not play the story out: {'; '.join(stuck)}. "
                                 f"Events that actually happened: {happened or 'none'}. Physics diagnostics: "
                                 f"{StoryDirector._diagnose(proj, sc, r)}. Adjust the physical setup "
                                 "(masses, friction, positions, ropes) or the actions so the needed events occur.")
        if proj.creative_plan is not None:
            from ..qa.creative import audit_creative_plan
            broken = [c for c in audit_creative_plan(proj, creative_evidence) if c.status == "FAIL"]
            if broken:
                details = "; ".join(f"{c.name}: {c.details}" for c in broken)
                raise ValueError("AI creative plan contradicted its mathematical, rhythmic, narrative or "
                                 f"simulation evidence: {details}. Repair causal beats or underlying scene physics.")

    @staticmethod
    def _check_sounds(proj: ProjectSpec) -> None:
        from ..audio.sound_director import SOUND_NAMES
        for sc in proj.scenes:
            for sh in sc.shots:
                for cue in sh.sound_cues:
                    if cue.sound not in SOUND_NAMES:
                        raise ValueError(f"shot {sh.id}: unknown sound {cue.sound!r}; use one of {', '.join(SOUND_NAMES)}")

    @staticmethod
    def _diagnose(proj: ProjectSpec, sc, r) -> str:
        """Numbers the planner needs to tune a physical setup: push force vs static friction, strap geometry, loads."""
        import math as _m
        env = proj.environment(sc.environment)
        props = {p.id: p for p in env.props}
        chars = {c.id: c for c in proj.characters}
        g = _m.hypot(*env.gravity)
        out = []
        for a in sc.actions:
            if a.type == "push" and a.target:
                p = props.get(a.target.split(":", 1)[1])
                if p:
                    mu = (p.static_friction if p.static_friction is not None else p.friction) * 0.9
                    need, have = mu * p.mass * g, a.effort * chars[a.character].strength
                    out.append(f"push {a.character}->{p.id}: force {have:.0f} vs static friction {need:.0f} "
                               f"({'breaks loose' if have > need else 'cannot move it'}); once sliding, friction "
                               f"{p.friction * 0.9 * p.mass * g:.0f}")
            if a.type == "lift" and a.target:
                p = props.get(a.target.split(":", 1)[1])
                if p:
                    out.append(f"lift {a.character}->{p.id}: weight {p.mass * g:.0f}, max hand force "
                               f"{a.effort * chars[a.character].strength:.0f} (lifting one end of a long prop needs ~half its weight)")
        for rp in env.ropes:
            snap = r.rope_snaps.get(rp.id)
            ends = []
            for ref, loc in ((rp.a, rp.a_local), (rp.b, rp.b_local)):
                k, _, v = ref.partition(":")
                if k == "prop" and v in props:
                    pp = props[v]
                    ca, sa = _m.cos(pp.angle), _m.sin(pp.angle)
                    ends.append((pp.position[0] + loc[0] * ca - loc[1] * sa, pp.position[1] + loc[0] * sa + loc[1] * ca))
                elif k == "world":
                    ends.append(tuple(float(c) for c in v.split(",")))
            if len(ends) == 2:
                d0 = _m.dist(*ends)
                out.append(f"rope {rp.id}: length {rp.length:.0f} vs initial end distance {d0:.0f}"
                           + (" (SHORTER than the distance: it starts taut)" if rp.length < d0 else f" (slack {rp.length - d0:.0f})")
                           + (f", snapped at {snap:.2f}s" if snap is not None else ", never snapped"))
        return "; ".join(out) or "none"


class TemplatePlanner:
    """Deterministic, rule-based planner used when no AI provider is configured (and in tests).

    It recognises a small vocabulary (enter/walk/run, switch/button, gravity direction words, jump) and emits a
    schema-valid project. It is intentionally simple and is NOT presented as AI story understanding.
    """

    def plan(self, story: str) -> ProjectSpec:
        s = story.lower()
        name = (re.search(r"\b([A-Z][A-Za-z]{2,})\b", story) or [None, "Axel"])[1]
        cid = name.lower()
        direction = (1, 0)
        surface = "wall_right"
        if "left" in s:
            direction, surface = (-1, 0), "wall_left"
        if "ceiling" in s or "upward" in s or "reverse" in s:
            direction, surface = (0, 1), "ceiling"
        run = "run" in s
        actions = [{"type": "run_to" if run else "walk_to", "character": cid, "target_x": -58, "speed": 330 if run else 150},
                   {"type": "idle", "character": cid, "duration": 0.35}]
        shots = [{"id": "s1_enter", "start": 0, "end": 3.0, "description": f"{name} approaches the switch",
                  "camera": {"mode": "follow", "target": cid, "view_height": 560, "offset": [60, 60]},
                  "action_objectives": ["reach the switch"], "exit_conditions": []}]
        has_switch = any(w in s for w in ("switch", "button", "lever"))
        if has_switch:
            actions += [{"type": "press", "character": cid, "switch": "gswitch"}, {"type": "wait_grounded", "character": cid},
                        {"type": "look_around", "character": cid, "duration": 1.4}]
            shots += [{"id": "s2_press", "start": 3.0, "end": 6.0, "description": "the switch is pressed and gravity changes",
                       "camera": {"mode": "static", "center": [10, 110], "view_height": 460},
                       "object_interactions": ["hand contacts gswitch"], "environment_state": {"gravity": "G0 -> G1"},
                       "sound_cues": [{"on_event": "press_contact", "sound": "click"}, {"on_event": "gravity_shift", "sound": "pulse"}],
                       "exit_conditions": ["event:press_contact"]},
                      {"id": "s3_land", "start": 6.0, "end": 10.5, "description": f"{name} falls and lands on the new floor",
                       "camera": {"mode": "follow", "target": cid, "view_height": 760, "offset": [-120, 60]},
                       "physics_requirements": [f"gravity {direction}", "ballistic fall", f"contact with {surface}"],
                       "sound_cues": [{"on_event": "impact", "sound": "impact"}], "exit_conditions": ["event:impact", f"grounded_on:{surface}"]}]
        else:
            actions += [{"type": "idle", "character": cid, "duration": 2.0}]
            shots[0]["end"] = 10.5
        data = {"schema_version": SCHEMA_VERSION, "id": re.sub(r"[^a-z0-9]+", "_", s[:40]).strip("_") or "story", "title": story[:80],
                "fps": 24, "width": 1920, "height": 1080, "seed": 7,
                "characters": [{"id": cid, "name": name}],
                "environments": [{"id": "chamber", "room": {"width": 1200, "height": 1400}, "gravity": [0, -1568],
                                  "switches": [{"id": "gswitch", "x": 0, "height": 66, "effect": {"to": list(direction), "delay": 0.45, "duration": 0.2}}]}],
                "scenes": [{"id": "scene_1", "title": story[:60], "environment": "chamber", "duration": 10.5,
                            "placements": [{"character": cid, "x": -540, "facing": 1}], "actions": actions, "shots": shots}]}
        proj = ProjectSpec.model_validate(data)
        return self._retime(proj, data) if has_switch else proj

    @staticmethod
    def _retime(proj: ProjectSpec, data: dict) -> ProjectSpec:
        """Derive shot boundaries from a dry-run simulation (cuts follow simulated events, not guesses)."""
        from ..scene.runtime import SceneRuntime
        r = SceneRuntime(proj, "scene_1").simulate()
        first = {}
        for e in r.events:
            first.setdefault(e.type, e.t)
        press, impact = first.get("press_contact"), first.get("impact")
        rec = first.get("recovered", impact)
        if press is None or impact is None:
            return proj
        sc = data["scenes"][0]
        b1 = round(max(0.5, press - 0.75), 3)
        b2 = round(max(b1 + 0.5, (press + impact) / 2), 3)
        fps = proj.fps
        dur = math.ceil(max(rec + 2.5, b2 + 1.5) * fps) / fps  # whole number of frames (exact: rounding to 6 decimals broke frame alignment)
        sh = sc["shots"]
        sh[0]["end"], sh[1]["start"], sh[1]["end"], sh[2]["start"], sh[2]["end"] = b1, b1, b2, b2, dur
        sc["duration"] = dur
        return ProjectSpec.model_validate(data)
