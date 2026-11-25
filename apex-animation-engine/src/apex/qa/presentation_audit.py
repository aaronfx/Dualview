"""Presentation QA — rendered-ground consistency, visible character overlap, excessive inactivity, implausible
physical contact and narrative payoff.

These are artistic-acceptance *aids*: they detect staging/story defects that a zero-violation physical run can still
contain. They never relax physical validation; they only add failing signals. Each returns a Check-like dict
{name, status, metric, threshold, detail}. `presentation_audit(rt, sim=None)` runs them all.
"""
from __future__ import annotations

import math

_AIRBORNE = {"airborne", "fall", "jump", "takeoff", "launch", "fly", "dive"}
_MEANINGFUL = {"footstep", "notice", "point", "act", "gesture", "pick_up", "place", "lift_start", "lift_fail",
               "push_start", "climb_start", "ledge_grab", "climbed", "takeoff", "impact", "lever_engage", "freed",
               "stood_up", "fist_bump", "shoulder_pat", "strike", "throw", "exit_reached", "crawl_start", "wave"}
_PAYOFF = {"fist_bump", "shoulder_pat", "wave", "gesture"}
# requirement 9: intentional close contact for combat, rescue and cooperation is expected, not a penetration defect
_INTENTIONAL_CONTACT = {"strike", "hit", "blocked", "guard", "lift_start", "lift_ok", "lift_fail", "offer_hand",
                        "hand_offered", "hand_grab", "help_up", "pulled_up", "fist_bump", "shoulder_pat", "gesture",
                        "lever_engage", "freed", "crawl_start", "pinned"}


def _result(sim, rt):
    return sim if sim is not None else rt.simulate()


def _ground_spans(env):
    """Drawn ground surfaces (x_lo, x_hi, top_y): platform/beam obstacle tops and standable prop tops."""
    spans = []
    for o in env.obstacles:
        if o.kind in ("platform", "beam", "bar"):
            spans.append((o.center[0] - o.size[0] / 2, o.center[0] + o.size[0] / 2, o.center[1] + o.size[1] / 2))
    return spans


def check_ground_consistency(rt, sim=None, margin=170.0, tol_frac=0.02):
    """Every grounded character must stand over a VISIBLE surface. An 'open' room draws no implicit floor, so a
    character walking on the invisible floor plane (no platform/beam/prop beneath) is a rendered-ground defect."""
    sim = _result(sim, rt)
    env = rt.env
    open_room = getattr(env.room, "style", "box") == "open"
    if not open_room:
        return {"name": "rendered_ground_consistency", "status": "PASS", "metric": 0.0, "threshold": tol_frac,
                "detail": "closed room draws its floor everywhere"}
    spans = _ground_spans(env)
    wall = env.room.width / 2
    worst = []
    total = bad = 0
    for cid, ctrl in sim.controllers.items():
        for r in ctrl.records[::4]:
            if r.mode in _AIRBORNE:
                continue
            x, y = r.pos
            if x >= wall - 70 or y > 170:        # exiting through the wall, or airborne/high: skip
                continue
            total += 1
            if not any(a - 40 <= x <= b + 40 and (y - margin) <= t <= (y + 20) for a, b, t in spans):
                bad += 1
                worst.append((cid, round(r.t, 2), round(x)))
    frac = bad / total if total else 0.0
    ok = frac <= tol_frac
    return {"name": "rendered_ground_consistency", "status": "PASS" if ok else "FAIL", "metric": round(frac, 3),
            "threshold": tol_frac, "detail": f"{bad}/{total} grounded frames over invisible ground"
            + (f"; e.g. {worst[0]}" if worst else "")}


def check_character_overlap(rt, sim=None, penetrate=26.0, y_gap=120.0, tol_frac=0.0):
    """Two character bodies must never occupy the same screen position — a true silhouette penetration. Depth is NOT
    credited: two stick figures at the same screen x read as passing through each other whatever their depth lane, so
    a depth offset does not excuse it. Native same-lane body collision (BODY_GAP ~30u) keeps characters apart, so a
    corrected film clears this; a depth-separated pair standing at the same x fails."""
    sim = _result(sim, rt)
    cids = list(sim.controllers)
    if len(cids) < 2:
        return {"name": "visible_character_overlap", "status": "PASS", "metric": 0.0, "threshold": tol_frac,
                "detail": "single character"}
    wall = rt.env.room.width / 2 + 40            # past this a character has gone through an exit (faded off screen)
    # Contact is pair-specific. A rescue, punch or gesture elsewhere in an
    # ensemble must not grant every other actor permission to intersect.
    import bisect
    from collections import defaultdict
    contacts = defaultdict(list)
    actors = set(cids)
    for e in sim.events:
        if e.type not in _INTENTIONAL_CONTACT and e.type not in ("strike_start", "gesture_start"):
            continue
        if e.character not in actors:
            continue
        for field in ("with", "target", "to", "by"):
            other = e.data.get(field)
            if not isinstance(other, str):
                continue
            if other.startswith("char:"):
                other = other[5:]
            if other in actors and other != e.character:
                contacts[frozenset((e.character, other))].append(e.t)
    for times in contacts.values():
        times.sort()

    def intentional(a, b, t, w=1.6):
        times = contacts.get(frozenset((a, b)), ())
        j = bisect.bisect_left(times, t)
        return (j < len(times) and times[j] - t <= w) or (j > 0 and t - times[j - 1] <= w)
    recs = {c: sim.controllers[c].records for c in cids}
    n = min(len(recs[c]) for c in cids)
    total = bad = 0
    worst = None
    for i in range(0, n, 2):
        total += 1
        frame_bad = False
        for a in range(len(cids)):
            for b in range(a + 1, len(cids)):
                ra, rb = recs[cids[a]][i], recs[cids[b]][i]
                if abs(ra.pos[0]) > wall or abs(rb.pos[0]) > wall:   # one has exited; not on screen
                    continue
                dx, dy = abs(ra.pos[0] - rb.pos[0]), abs(ra.pos[1] - rb.pos[1])
                if dx < penetrate and dy < y_gap and not intentional(cids[a], cids[b], ra.t):
                    frame_bad = True
                    if worst is None or dx < worst[0]:
                        worst = (dx, cids[a], cids[b], round(ra.t, 2), round(abs(ra.z - rb.z)))
        bad += int(frame_bad)
    frac = bad / total if total else 0.0
    ok = frac <= tol_frac
    return {"name": "visible_character_overlap", "status": "PASS" if ok else "FAIL", "metric": round(frac, 3),
            "threshold": tol_frac, "detail": (f"{bad}/{total} frames with silhouette penetration; worst "
            f"dx={worst[0]:.0f}u between {worst[1]}/{worst[2]} at t={worst[3]} (depth gap {worst[4]}u — not credited)"
            if worst else "no silhouette penetration")}


def check_inactivity(rt, sim=None, max_idle=6.0):
    """No character should stand inert for an excessive span while the film continues and others act."""
    sim = _result(sim, rt)
    dur = sim.duration
    worst = ("", 0.0, 0.0)
    for cid, ctrl in sim.controllers.items():
        acts = sorted(e.t for e in sim.events if e.character == cid and e.type in _MEANINGFUL)
        # the character is 'present' until it reaches the exit (after which it has left the frame)
        exit_t = next((e.t for e in sim.events if e.character == cid and e.type == "exit_reached"), dur)
        marks = [0.0] + acts + [exit_t]
        for p, q in zip(marks, marks[1:]):
            if q - p > worst[1]:
                worst = (cid, round(q - p, 2), round(p, 2))
    ok = worst[1] <= max_idle
    return {"name": "excessive_inactivity", "status": "PASS" if ok else "FAIL", "metric": worst[1],
            "threshold": max_idle, "detail": f"longest inert span {worst[1]}s ({worst[0]} from t={worst[2]})"}


def check_narrative_payoff(rt, sim=None, tail=6.0):
    """The film must end on a reaction/payoff, not merely on an exit. Require a payoff beat (gesture/reaction) in the
    closing stretch (the final ~third of these short films), not just movement into an exit."""
    sim = _result(sim, rt)
    dur = sim.duration
    payoff = [e for e in sim.events if e.type in _PAYOFF or (e.type == "act")]
    late = [e for e in payoff if e.t >= dur - tail]
    ok = bool(late)
    return {"name": "narrative_payoff", "status": "PASS" if ok else "FAIL", "metric": len(late), "threshold": 1,
            "detail": (f"payoff beat at t={late[-1].t:.2f} ({late[-1].type})" if late
                       else "film ends without a reaction/payoff beat (only movement/exit)")}


def presentation_audit(rt, sim=None) -> list:
    sim = _result(sim, rt)
    return [check_ground_consistency(rt, sim), check_character_overlap(rt, sim),
            check_inactivity(rt, sim), check_narrative_payoff(rt, sim)]
