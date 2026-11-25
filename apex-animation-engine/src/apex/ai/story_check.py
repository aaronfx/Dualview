"""D10.5 — independent story verification.

The user's required story is derived from the brief HERE, independently of any generated animation plan, then
verified against the ACTUAL native simulation events and scene structure. A technically valid render that does not
satisfy the requested story is rejected. An unsupported offline request yields a clear limitation, never a silent
substitution of an unrelated story.

Requirements are deterministic and conservative: each is either structural (scene composition) or an ordered native
event that must actually occur. This module makes no model call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .capabilities import EVENTS as _ACTION_EVENTS  # noqa: F401  (documents which actions can raise which events)


@dataclass(frozen=True)
class Requirement:
    id: str
    description: str
    kind: str                       # "structural" | "event"
    event: Optional[str] = None     # event type that must occur (kind == "event")
    after: tuple = ()               # ids of requirements whose events must occur earlier
    structural: Optional[Callable] = None   # (project) -> bool, for kind == "structural"


# --- story archetypes -> required objectives (independent of the plan) ----------------------------------------
def _two_chars(project) -> bool:
    return len({pl.character for s in project.scenes for pl in s.placements}) >= 2


RESCUE = [
    Requirement("two_characters", "Two distinct characters", "structural", structural=_two_chars),
    Requirement("trapped", "One character is trapped beneath a heavy object", "event", event="pinned"),
    Requirement("discovery", "The second character discovers the trapped one", "event", event="notice", after=("trapped",)),
    Requirement("failed_lift", "An unsuccessful direct lift attempt", "event", event="lift_fail", after=("discovery",)),
    Requirement("lever", "A lever is found and physically engaged", "event", event="lever_engage", after=("failed_lift",)),
    Requirement("release", "The trapped character is released", "event", event="freed", after=("lever",)),
    Requirement("recovery", "The freed character recovers (stands up)", "event", event="stood_up", after=("release",)),
    Requirement("friendship", "An emotional moment of friendship", "event", event="fist_bump", after=("recovery",)),
]

_ARCHETYPES = {"rescue": RESCUE}

# offline (template, no-LLM) production can currently satisfy these archetypes natively; anything else must be
# reported as a limitation rather than silently replaced.
_OFFLINE_SUPPORTED = {"rescue"}


def detect_archetype(brief: str) -> Optional[str]:
    b = brief.lower()
    if any(w in b for w in ("rescue", "trapped", "pinned", "stuck under", "lever", "free the", "save ")):
        return "rescue"
    return None


def requirements_for(brief: str):
    arch = detect_archetype(brief)
    return arch, list(_ARCHETYPES.get(arch, []))


def offline_support(brief: str) -> Optional[str]:
    """None if the offline engine can attempt this brief's archetype; otherwise a clear limitation message."""
    arch = detect_archetype(brief)
    if arch is None:
        return ("Offline mode cannot infer a supported story from this brief. Supported offline archetypes: "
                + ", ".join(sorted(_OFFLINE_SUPPORTED)) + ". Provide a clearer brief or enable the approved AI planner.")
    if arch not in _OFFLINE_SUPPORTED:
        return f"Offline mode does not yet support the '{arch}' archetype natively; enable the approved AI planner."
    return None


# --- verification against the actual native simulation --------------------------------------------------------
def verify(requirements, project, events) -> dict:
    """Check each required objective against real native events / structure. Returns a per-objective report and an
    overall pass. Ordered events (via `after`) must occur in the required order."""
    first_t = {}
    for e in events:
        first_t.setdefault(e.type, e.t)
    results = []
    ok_all = True
    for req in requirements:
        if req.kind == "structural":
            met = bool(req.structural(project))
            detail = "scene composition"
        else:
            met = req.event in first_t
            if met:
                # ordered events: each depended-on requirement's event must occur before this one
                for dep in req.after:
                    dep_req = next((r for r in requirements if r.id == dep), None)
                    if dep_req and dep_req.kind == "event":
                        if dep_req.event not in first_t or first_t[dep_req.event] > first_t[req.event]:
                            met = False
            detail = f"native event '{req.event}'" + (f" at t={first_t[req.event]:.2f}" if req.event in first_t else " (absent)")
        ok_all = ok_all and met
        results.append({"id": req.id, "description": req.description, "met": met, "detail": detail})
    return {"archetype_checked": True, "requirements": results, "met": sum(r["met"] for r in results),
            "total": len(results), "story_pass": ok_all,
            "note": "independent of the animation plan; verified against native simulation events"}


def verify_brief(brief: str, project, events) -> dict:
    arch, reqs = requirements_for(brief)
    if not reqs:
        return {"archetype_checked": False, "story_pass": None, "requirements": [],
                "note": f"no verifiable story archetype detected in brief; limitation={offline_support(brief)}"}
    report = verify(reqs, project, events)
    report["archetype"] = arch
    return report
