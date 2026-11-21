"""Story goals: the beats a scene must produce in simulation, e.g. "pinned@milo[by=post]".

Syntax: `[event:]<type>[@<who>][[key=value,...]]`, where `who` is a character, prop or rope id and the bracketed
filters match the event's data (e.g. `by=post`). Explicit goals are ordered: each must happen after the previous.
When a scene has none, `derive_goals` infers the events the action list depends on (unordered).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

_GOAL = re.compile(r"^(?:event:|next:)?([a-z_]+)(?:@([A-Za-z0-9_\-]+))?(?:\[([^\]]*)\])?$")
PRONE_ACTIONS = ("struggle", "crawl_out", "get_up")
# every event type the engine emits (a goal or an event-timed cut naming anything else could never happen)
KNOWN_EVENTS = frozenset("""action_impossible body_fall brace crawl_start door_close door_open door_unlocked door_unlocking
exit_reached footstep freed get_up_start grab grab_missed gravity_settled gravity_shift graze hand_grab hand_offered help_missed
impact lever_engage lever_place lever_release lift_fail lift_ok lift_start load_off look_back lost_support notice pick_up pinned
point press_contact prop_impact push_end push_fail push_lost push_start recovered release rope_snap rope_taut slide_end
slide_start stood_up switch_activated takeoff turn fist_bump shoulder_pat wave
strike_start swing hit hurt blocked block_hit whiff evaded knockdown settled dodge gesture_start
step_off flip roll_start roll_end vault_start vault climb_start ledge_grab climbed wall_run wall_contact wall_kick throw_start throw
prop_hit bump
orb_jump orb_boost orb_pad collect portal_enter portal_exit beat_wait_end
break morph_start morph morph_blocked""".split())


def check_event(etype: str, where: str) -> None:
    if etype not in KNOWN_EVENTS:
        import difflib
        near = difflib.get_close_matches(etype, sorted(KNOWN_EVENTS), n=3, cutoff=0.5)
        raise ValueError(f"{where}: '{etype}' is not an engine event (an action name is not an event)"
                         + (f"; did you mean {' or '.join(near)}?" if near else f"; events: {' '.join(sorted(KNOWN_EVENTS))}"))


def parse_goal(g: str) -> Tuple[str, Optional[str], Dict[str, str]]:
    m = _GOAL.match(g.strip())
    if not m:
        raise ValueError(f"goal {g!r} must look like 'type', 'type@who' or 'type@who[key=value]'")
    etype, who, filt = m.group(1), m.group(2), {}
    if m.group(3):
        for part in m.group(3).split(","):
            k, _, v = part.partition("=")
            if not k.strip() or not v.strip():
                raise ValueError(f"goal {g!r}: filter {part!r} must be key=value")
            filt[k.strip()] = v.strip()
    return etype, who, filt


def matches(goal: str, e) -> bool:
    etype, who, filt = parse_goal(goal)
    return (e.type == etype and (who is None or e.character == who)
            and all(str(e.data.get(k)) == v for k, v in filt.items()))


def derive_goals(scene) -> List[str]:
    """Events the action list cannot do without: every `until` event, and a fall before any lying-down action."""
    out: List[str] = []
    for a in scene.actions:
        if a.type in PRONE_ACTIONS:
            g = f"body_fall@{a.character}"
            if g not in out:
                out.append(g)
        if a.until:
            g = a.until.split(":", 1)[1]
            if g not in out:
                out.append(g)
    return out


ORDER_TOLERANCE = 0.75  # s: beats that happen almost together (a fall and a strap snapping) may come in either order


def progress(goals: Sequence[str], events, ordered: bool = True, before: Optional[float] = None, tol: float = ORDER_TOLERANCE):
    """How many goals happened (in order, if `ordered`, within `tol` seconds), their times, and the first goal missing."""
    t_prev = -1.0
    times: List[Optional[float]] = []
    met = 0
    for g in goals:
        hit = next((e for e in events if matches(g, e) and (not ordered or e.t >= t_prev - tol)
                    and (before is None or e.t <= before)), None)
        times.append(hit.t if hit else None)
        if hit is None:
            if ordered:
                times += [None] * (len(goals) - len(times))
                break
            continue
        met += 1
        if ordered:
            t_prev = max(t_prev, hit.t)
    missing = next((g for g, t in zip(goals, times) if t is None), None)
    return met, times, missing
