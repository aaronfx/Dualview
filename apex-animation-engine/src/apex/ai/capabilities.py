"""Executable, versioned native action catalogue for the Smart Director.

Schema is the syntactic authority; simulation and QA are the outcome authority.
An available action is NOT a guarantee of a successful performance.
"""
from __future__ import annotations
from typing import get_args
from ..scene.schema import ActionType, ActionSpec, ProjectSpec
from ..scene.goals import KNOWN_EVENTS
from ..motion.library import list_clips

# Native event contracts: alternatives are possible outcomes, not guaranteed successes.
EVENTS = {
    "walk_to": ("footstep",), "run_to": ("footstep",), "turn": ("turn",),
    "press": ("press_contact", "switch_activated"), "jump": ("takeoff", "impact"),
    "jump_to": ("takeoff", "impact"), "look_at": (), "notice": ("notice",),
    "point": ("point",), "duck_slide": ("slide_start", "slide_end"),
    "grab_swing": ("grab", "release", "grab_missed"), "reach_exit": ("exit_reached",),
    "push": ("push_start", "push_end", "push_fail", "push_lost"),
    "lift": ("lift_start", "lift_ok", "lift_fail"), "use_lever": ("lever_engage", "lever_release"),
    "struggle": (), "crawl_out": ("crawl_start", "freed"), "get_up": ("stood_up",),
    "offer_hand": ("hand_offered", "hand_grab", "help_missed"),
    "gesture": ("fist_bump", "shoulder_pat", "wave"),
    "strike": ("hit", "blocked", "whiff", "evaded"), "guard": ("block_hit",),
    "dodge": ("dodge",), "roll": ("roll_start", "roll_end"), "vault": ("vault",),
    "climb": ("ledge_grab", "climbed"), "wall_kick": ("wall_kick",),
    "pick_up": ("pick_up",), "throw": ("throw",), "wait_beat": ("beat_wait_end",),
    "act": ("act",), "catch_ledge": ("ledge_catch",), "hang": ("hang_slip",),
    "pull_up": ("pulled_up",), "place": ("place",), "idle": (), "look_around": (),
    "wait_grounded": (), "wait_for": (),
}
REQUIRED = {
    "walk_to": ["target_x OR char:/prop: target"], "run_to": ["target_x OR char:/prop: target"],
    "turn": ["face"], "press": ["switch"], "jump": ["height"],
    "jump_to": ["target_x", "height"], "look_at": ["target"], "notice": ["target"],
    "point": ["target"], "duck_slide": ["target_x"], "grab_swing": ["target"],
    "reach_exit": ["target"], "push": ["target"], "lift": ["target"],
    "use_lever": ["target", "tool", "fulcrum"], "offer_hand": ["target"],
    "gesture": ["target", "gesture"], "wait_for": ["until"],
    "strike": ["target", "move"], "vault": ["target"], "climb": ["target"],
    "wall_kick": ["target_x"], "pick_up": ["target"], "throw": ["target"],
    "act": ["clip"], "catch_ledge": ["target"], "pull_up": ["target"], "place": ["target"],
}
ALTERNATIVES = {
    "jump_to": ["vault", "climb"], "vault": ["climb", "jump_to"],
    "climb": ["jump_to", "vault"], "lift": ["use_lever", "push"],
    "strike": ["guard", "dodge"], "pull_up": ["climb", "offer_hand"],
}
def catalogue() -> dict:
    # Lazy imports: the typed planners themselves import this catalogue.
    from .objective_planner import ObjectiveRequest
    from .ensemble_planner import EnsembleRequest
    names = sorted(get_args(ActionType))
    return {
        "version": 1,
        "authority": "ActionSpec + ProjectSpec + native SceneRuntime + Inspector",
        "scope": "Available native primitives; feasibility and artistry not guaranteed",
        "actions": [
            {"name": n, "required_parameters": ["character", *REQUIRED.get(n, [])],
             "possible_events": [e for e in EVENTS.get(n, ()) if e in KNOWN_EVENTS],
             "alternatives": ALTERNATIVES.get(n, []),
             "availability": "native_schema", "requires_rehearsal": True}
            for n in names
        ],
        "action_schema": ActionSpec.model_json_schema(),
        "events": sorted(KNOWN_EVENTS),
        "motion_clips": sorted(list_clips()),
        "typed_planner_schemas": {
            "objectives": ObjectiveRequest.model_json_schema(),
            "ensemble": EnsembleRequest.model_json_schema(),
        },
        "tools": {
            "cross_and_collect": "Bounded native downward-gravity obstacle route proposals",
            "rehearse": "Compare typed action candidates in the same native scene",
            "objectives": "Compile bounded actor objectives to native alternatives and event proofs",
            "ensemble": "Coordinate native action queues with explicit causal dependencies",
            "story_plan": "Existing budgeted StoryDirector with native setup solver",
            "render": "Native APEX renderer; accepted rehearsals only",
        },
    }

def validate_candidate(project: ProjectSpec, scene_id: str, actions) -> ProjectSpec:
    """Replace only the selected scene's action list and revalidate every reference."""
    data = project.model_dump(mode="json")
    scene = next(s for s in data["scenes"] if s["id"] == scene_id)
    scene["actions"] = [ActionSpec.model_validate(a).model_dump(mode="json") for a in actions]
    return ProjectSpec.model_validate(data)
