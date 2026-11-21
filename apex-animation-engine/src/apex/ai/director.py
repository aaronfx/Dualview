"""AI Story Director: natural-language story -> validated ProjectSpec (structured animation data, not prose).

The LLM is only a planner. Its output must validate against the scene schema and pass a dry-run simulation
before it is accepted; validation errors are fed back for a bounded number of repair attempts. The engine
(simulation, motion, rendering) never depends on the LLM.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import List, Optional

from pydantic import ValidationError

from ..scene.schema import SCHEMA_VERSION, ProjectSpec
from .providers import Provider, provider_from_env

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "foundry_flip.json"

ACTION_HELP = {
    "idle": "stand (duration)", "walk_to": "walk to target_x, or to a 'char:'/'prop:' target", "run_to": "run (same targets as walk_to)",
    "turn": "face=+1/-1", "press": "press a switch (switch)", "jump": "running jump (height)", "look_around": "look around (duration)",
    "wait_grounded": "wait until standing on a surface again", "look_at": "look at target (duration)", "notice": "double take at target",
    "point": "point at target", "duck_slide": "slide feet-first to target_x", "jump_to": "standing jump to target_x (height, optional switch)",
    "grab_swing": "catch a bar while falling (target bar:)", "reach_exit": "walk out through an open exit (target exit:)",
    "push": "push a prop (target prop:, effort 0.5-1.6 of the character's strength); if it breaks loose and outruns the character, "
            "contact is lost and the character stumbles and FALLS PRONE (physics decides)",
    "lift": "try to lift the nearest end of a prop by hand (target prop:, effort, duration); too heavy simply does not rise",
    "use_lever": "fetch a bar (tool prop:), place it over a fulcrum (fulcrum prop:) under the load (target prop:) and bear down; "
                 "holds until `until` event",
    "struggle": "while lying prone: struggle (duration or until)", "crawl_out": "while prone: wait until the load is off, crawl out (emits freed)",
    "get_up": "while prone: get up; with target char: take that character's offered hand",
    "offer_hand": "walk to a lying/kneeling character (target char:) and offer a hand, pull them up",
    "gesture": "gesture with another character (target char:, gesture fist_bump|shoulder_pat|wave)",
    "wait_for": "wait until an event happens (until 'event:<type>' or 'event:<type>@<character>')",
}
EVENT_TYPES = ("footstep turn notice point press_contact switch_activated gravity_shift lost_support impact recovered takeoff "
               "push_start push_lost rope_taut rope_snap body_fall pinned load_off lift_start lift_fail lift_ok pick_up lever_place "
               "lever_engage lever_release crawl_start freed get_up_start hand_offered hand_grab stood_up fist_bump shoulder_pat prop_impact")


def system_prompt() -> str:
    """The planner's contract, generated from the live schema (action list, required fields, names)."""
    from ..audio.sound_director import SOUND_NAMES
    from ..scene.schema import ActionSpec, PropSpec
    import typing
    acts = typing.get_args(ActionSpec.model_fields["type"].annotation)
    kinds = typing.get_args(PropSpec.model_fields["kind"].annotation)
    lines = "\n".join(f"  - {a}: {ACTION_HELP.get(a, '')}" for a in acts)
    return f"""You are the APEX Story Director. Convert the user's story into ONE JSON object that validates against the
APEX scene schema v{SCHEMA_VERSION}. Output JSON only. The engine SIMULATES physics: you describe intentions and the
physical setup; the simulation decides outcomes. Do not fake an action with `idle` + a note when an action exists for it.
Action types (each action has `character`; durations in seconds):
{lines}
Props (environment.props): kinds {", ".join(kinds)}; fields id, kind, position [x, y-centre], size [w, h], mass, angle (rad),
friction (sliding), static_friction (at rest: heavy things break loose), collide_characters, solid (false = fixed set dressing
until picked up, e.g. a tool on a rack), com (centre of mass offset, e.g. a top-heavy post), z (depth; negative = nearer the camera).
Ropes (environment.ropes): straps between props ("prop:<id>" ends, local attachment points), length (slack), break_force (snaps).
Characters: id, name, proportions, style (colours, cadence/stride/lean/arm_swing scales), strength (max hand force, ~40000-60000).
Targets: "switch:<id>", "exit:<id>", "bar:<id>", "prop:<id>", "char:<id>", "point:x,y". Coordinates: x along the floor, room spans
[-width/2, width/2]; gravity [0,-1568]; standing pelvis ~95 above the floor; a character is ~175 tall.
Shots: contiguous, start at 0, end exactly at the scene duration; kinds establishing|wide|medium|close|insert|tracking; camera modes
static|follow|track_x|dolly; camera.include lists targets to keep in frame (e.g. "char:<id>", "prop:<id>").
exit_conditions: "event:<type>" with types from: {EVENT_TYPES}.
sound_cues: {{on_event, sound, gain}}; sound must be one of: {", ".join(SOUND_NAMES)}.
Keep characters consistent: one CharacterSpec per character, referenced by id everywhere."""


SYSTEM = system_prompt.__doc__  # kept for backwards compatibility; the live prompt is system_prompt()


class PlanningError(RuntimeError):
    pass


class StoryDirector:
    def __init__(self, provider: Optional[Provider] = None, max_repairs: int = 7):
        self.provider = provider
        self.max_repairs = max_repairs
        self.log: List[dict] = []  # every raw response and the error fed back to it (preserved by `apex plan --log-dir`)

    @property
    def name(self) -> str:
        return self.provider.name if self.provider else "offline-template"

    @classmethod
    def from_env(cls, offline: bool = False) -> "StoryDirector":
        return cls(None if offline else provider_from_env())

    # ------------------------------------------------------------ public
    def plan(self, story: str) -> ProjectSpec:
        if self.provider is None:
            return TemplatePlanner().plan(story)
        example = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.exists() else ""
        user = f"STORY:\n{story}\n\nEXAMPLE OF A VALID PROJECT (structure reference, do not copy its story):\n{example}"
        errors: List[str] = []
        for attempt in range(self.max_repairs + 1):
            prompt = user if not errors else user + "\n\nYOUR PREVIOUS OUTPUT WAS INVALID:\n" + "\n".join(errors[-1:]) + "\nReturn a corrected JSON object."
            raw = self.provider.complete(system_prompt(), prompt, max_tokens=16000) or ""
            self.log.append({"attempt": attempt + 1, "raw_response": raw, "fed_back_error": errors[-1] if errors else None})
            try:
                proj = self._parse(raw)
                self._dry_run(proj)
                return proj
            except (ValidationError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
                errors.append(str(e)[:2000])
        raise PlanningError(f"planner output failed validation after {self.max_repairs + 1} attempts: {errors[-1][:500]}")

    @staticmethod
    def _parse(raw: str) -> ProjectSpec:
        m = re.search(r"\{.*\}", raw or "", re.S)
        if not m:
            raise ValueError("no JSON object in response (empty or truncated output: return the complete JSON object)")
        return ProjectSpec.model_validate(json.loads(m.group(0)))

    @staticmethod
    def _dry_run(proj: ProjectSpec) -> None:
        """A plan is only accepted if every sound exists and every scene simulates (catches impossible directives early)."""
        from ..audio.sound_director import SOUND_NAMES
        from ..scene.runtime import SceneRuntime
        for sc in proj.scenes:
            for sh in sc.shots:
                for cue in sh.sound_cues:
                    if cue.sound not in SOUND_NAMES:
                        raise ValueError(f"shot {sh.id}: unknown sound {cue.sound!r}; use one of {', '.join(SOUND_NAMES)}")
            r = SceneRuntime(proj, sc.id).simulate()
            # every character must get through its action list: a step that never completes means the physical setup
            # did not produce what the story needs (e.g. a wait_for event that never happened)
            stuck = []
            for cid, c in r.controllers.items():
                a = c.cur
                if a is None:
                    continue
                ph = getattr(c, "inter", {}).get("phase")
                waiting = (a.type == "wait_for" or (a.type == "crawl_out" and ph == "wait")
                           or (a.type == "get_up" and ph == "up" and c.inter.get("wait", 0.0) > 1.0)
                           or (a.type == "use_lever" and ph == "hold" and a.until) or (a.type == "struggle" and a.until))
                if waiting:
                    stuck.append(f"{cid} was still waiting in '{a.type}'" + (f" (until {a.until})" if a.until else "")
                                 + f" when the scene ended, with {len(c.queue)} action(s) never reached")
            if stuck:
                happened = ", ".join(f"{e.t:.1f}s {e.type}@{e.character}" for e in r.events
                                     if e.type not in ("footstep", "turn", "prop_impact"))[:1500]
                raise ValueError(f"scene {sc.id}: the simulation did not play the story out: {'; '.join(stuck)}. "
                                 f"Events that actually happened: {happened or 'none'}. Physics diagnostics: "
                                 f"{StoryDirector._diagnose(proj, sc, r)}. Adjust the physical setup "
                                 "(masses, friction, positions, ropes) or the actions so the needed events occur.")

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
