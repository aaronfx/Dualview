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

EXAMPLE = Path(__file__).resolve().parents[3] / "examples" / "gravity_switch_1b.json"

SYSTEM = f"""You are the APEX Story Director. Convert the user's story into ONE JSON object that validates against the
APEX scene schema v{SCHEMA_VERSION}. Output JSON only. Rules:
- Use only action types: idle, walk_to, run_to, turn, press, jump, look_around, wait_grounded.
- Coordinates are centimetres on the support surface; the room spans x in [-width/2, width/2].
- Shots must be contiguous, start at 0 and end exactly at the scene duration.
- Every shot needs: id, start, end, description, camera, action_objectives, physics_requirements, sound_cues, exit_conditions.
- exit_conditions use: "event:<press_contact|gravity_shift|lost_support|impact|recovered|takeoff>", "state:<idle|loco|press>",
  "grounded_on:<floor|wall_right|wall_left|ceiling>".
- Gravity changes only happen through a switch's effect (no free-form gravity edits).
- Keep characters consistent: one CharacterSpec per character, referenced by id everywhere."""


class PlanningError(RuntimeError):
    pass


class StoryDirector:
    def __init__(self, provider: Optional[Provider] = None, max_repairs: int = 2):
        self.provider = provider
        self.max_repairs = max_repairs

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
            raw = self.provider.complete(SYSTEM, prompt)
            try:
                proj = self._parse(raw)
                self._dry_run(proj)
                return proj
            except (ValidationError, ValueError, KeyError) as e:
                errors.append(str(e)[:2000])
        raise PlanningError(f"planner output failed validation after {self.max_repairs + 1} attempts: {errors[-1][:500]}")

    @staticmethod
    def _parse(raw: str) -> ProjectSpec:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("no JSON object in response")
        return ProjectSpec.model_validate(json.loads(m.group(0)))

    @staticmethod
    def _dry_run(proj: ProjectSpec) -> None:
        """A plan is only accepted if every scene simulates (catches impossible directives early)."""
        from ..scene.runtime import SceneRuntime
        for sc in proj.scenes:
            SceneRuntime(proj, sc.id).simulate()


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
