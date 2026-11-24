"""Transition matrix: chains of moves the films never tried, run through the full engine and inspector.

Individual moves are tested elsewhere. Problems hide in the hand-overs between a scripted motion and dynamic physics
(snapping, penetration, unexpected momentum, unnatural poses). Each scenario here chains two to four moves across
those boundaries (flips, rolls, combat, ragdoll impacts, recovery, carrying, climbing) and is judged on the same
technical checks as a film. Nothing is tuned per scenario: the arena and the timing are shared.

    PYTHONPATH=src python -m apex.qa.transitions            # prints the matrix
"""
from __future__ import annotations

from typing import Dict, List, Tuple

K, R = "kai", "rho"


def k(**a):
    return dict(character=K, **a)


def r(**a):
    return dict(character=R, **a)


RHO_IDLE = [r(type="guard", duration=12.0)]
RHO_WAIT = [r(type="idle", duration=12.0)]

# name -> (KAI's chain, RHO's actions)
SCENARIOS: Dict[str, Tuple[List[dict], List[dict]]] = {
    "flip_back > guard > strike": ([k(type="jump_to", target_x=-420, height=110, flip="back"), k(type="guard", duration=0.4),
                                     k(type="strike", target="char:rho", move="cross")], RHO_IDLE),
    "flip_front > strike": ([k(type="walk_to", target_x=-420), k(type="jump_to", target_x=-220, height=100, flip="front"),
                             k(type="strike", target="char:rho", move="jab")], RHO_IDLE),
    "landing roll > strike": ([k(type="walk_to", target_x=-470), k(type="jump_to", target_x=-330, height=90, flip="front"), k(type="roll"),
                               k(type="strike", target="char:rho", move="hook")], RHO_WAIT),
    "roll > guard > dodge": ([k(type="roll", distance=150), k(type="guard", duration=0.5), k(type="dodge", dodge="back")], RHO_WAIT),
    "strike > knockdown > get_up > strike": ([k(type="strike", target="char:rho", move="sweep"), k(type="guard", duration=3.5)],
                                             [r(type="wait_for", until="next:knockdown@rho"), r(type="get_up"),
                                              r(type="strike", target="char:kai", move="jab")]),
    "knocked down > get_up > flip": ([k(type="wait_for", until="next:knockdown@kai"), k(type="get_up"),
                                      k(type="jump_to", target_x=-480, height=110, flip="back")],
                                     [r(type="strike", target="char:kai", move="roundhouse", power=1.6, reaction="knockdown")]),
    "flying_kick > roll": ([k(type="strike", target="char:rho", move="flying_kick"), k(type="roll", distance=120)], RHO_IDLE),
    "duck > uppercut": ([k(type="wait_for", until="next:strike_start@rho"), k(type="dodge", dodge="duck"),
                         k(type="strike", target="char:rho", move="uppercut")],
                        [r(type="idle", duration=0.6), r(type="strike", target="char:kai", move="hook")]),
    "pick_up > swing > throw": ([k(type="pick_up", target="prop:minus"), k(type="strike", target="char:rho", move="swing_weapon"),
                                 k(type="throw", target="char:rho")], RHO_WAIT),
    "throw > flip": ([k(type="pick_up", target="prop:minus"), k(type="throw", target="char:rho"),
                      k(type="jump_to", target_x=-470, height=110, flip="back")], RHO_IDLE),
    "climb > flip off > roll > strike": ([k(type="climb", target="obstacle:ledge"), k(type="walk_to", target_x=-430),
                                          k(type="jump_to", target_x=-260, height=80, flip="front"), k(type="roll", distance=80),
                                          k(type="strike", target="char:rho", move="cross")], RHO_IDLE),
    "vault > strike": ([k(type="vault", target="obstacle:low"), k(type="strike", target="char:rho", move="front_kick")], RHO_IDLE),
    "dodge back > flying_kick": ([k(type="wait_for", until="next:strike_start@rho"), k(type="dodge", dodge="back"),
                                  k(type="strike", target="char:rho", move="flying_kick", speed=320)],
                                 [r(type="idle", duration=0.5), r(type="strike", target="char:kai", move="front_kick")]),
    "walk into heavy crate > sidestep > strike": ([k(type="walk_to", target_x=-150), k(type="strike", target="char:rho", move="jab")],
                                                  RHO_IDLE),
}


USES = {"climb > flip off > roll > strike": ["ledge"], "vault > strike": ["low"]}  # structures a chain needs


def scene(chain: List[dict], rho: List[dict], dur: float = 11.0, uses: List[str] = ()) -> dict:
    """The shared arena: a light minus sign on the floor and a heavy crate; a ledge and a low glyph for the chains that
    climb or vault (left out otherwise, so they do not stand in the fighters' way)."""
    return {
        "schema_version": "0.1", "id": "transitions", "title": "transitions", "fps": 24, "width": 1280, "height": 720, "seed": 5,
        "characters": [{"id": K, "name": "KAI", "strength": 50000, "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42}},
                       {"id": R, "name": "RHO", "strength": 47000, "proportions": {"spine": 31, "chest": 29, "head": 23, "thigh": 46, "shin": 43}}],
        "environments": [{"id": "e", "room": {"width": 2000, "height": 900, "entry_door": False}, "dust": 0,
                          "obstacles": [o for o in ({"id": "ledge", "kind": "platform", "center": [-640, 100], "size": [260, 200]},
                                                    {"id": "low", "kind": "glyph", "glyph": "-", "center": [-150, 22], "size": [90, 30], "weight": 28})
                                        if o["id"] in uses],
                          "props": [{"id": "minus", "kind": "glyph", "glyph": "-", "position": [-300, 8], "size": [110, 16], "mass": 5, "weight": 14},
                                    {"id": "crate", "kind": "container", "position": [-80, 51], "size": [100, 100], "mass": 110,
                                     "friction": 0.05, "static_friction": 0.5, "z": 0, "depth": 50}]}],
        "scenes": [{"id": "s", "environment": "e", "duration": dur,
                    "placements": [{"character": K, "x": -360, "facing": 1, "z": -12}, {"character": R, "x": 120, "facing": -1, "z": 12}],
                    "actions": chain + rho,
                    "shots": [{"id": "a", "start": 0, "end": dur, "camera": {"mode": "follow", "target": K, "view_height": 600,
                                                                             "include": [f"char:{R}"]}}]}]}


TECH = ("no_teleport_joints", "surface_penetration", "body_clearance", "body_outside_structures", "held_props_outside_structures",
        "props_not_through_bodies", "flips_land_upright", "feet_on_tops", "strike_contact", "knockdowns_settle")


def run(name: str) -> dict:
    """Simulate one chain and judge it. Returns the outcome and the technical checks that matter at hand-overs."""
    from ..render.pipeline import build_camera
    from ..scene.runtime import SceneRuntime
    from ..scene.schema import ProjectSpec
    from .inspector import Inspector
    chain, rho = SCENARIOS[name]
    p = ProjectSpec.model_validate(scene(chain, rho, uses=USES.get(name, ())))
    rt = SceneRuntime(p, "s", strict=False)
    try:
        res = rt.simulate()
    except Exception as exc:  # an engine error is a failed hand-over, reported, not a crash of the harness
        return {"name": name, "completed": False, "left": {}, "violations": {"engine": str(exc)[:200]}, "failed_checks": [],
                "events": [], "ok": False}
    left = {cid: [a.type for a in c.queue] + ([c.cur.type] if c.cur is not None and c.cur.type not in ("idle", "guard") else [])
            for cid, c in res.controllers.items()}
    viol = {cid: c.violation for cid, c in res.controllers.items() if c.violation}
    rep = Inspector(rt, build_camera(rt, 16 / 9), 24, (1280, 720)).run(check_determinism=False)
    checks = {c.name: c for c in rep.checks if c.name.startswith(TECH)}
    bad = [f"{c.name} {c.metric:.3g}" if c.metric is not None else c.name for c in checks.values() if c.status == "FAIL"]
    return {"name": name, "completed": not any(left[K]) and not viol, "left": left, "violations": viol, "failed_checks": bad,
            "events": sorted({e.type for e in res.events}), "ok": not bad and not viol and not any(left[K])}


# --------------------------------------------------------------------------- pairwise context matrix
# The hand-picked chains above test move-to-move hand-overs. This second matrix tests one move under varied *context*:
# the factors that, combined, exposed the CORE RUN bugs (carrying through a jump, a thrown prop and a body in different
# lanes, a prop near a structure, pace). Testing every combination is 4*2*2*2*2*2 = 128 scenes; most add nothing. A
# pairwise (all-pairs) covering set hits every pair of factor levels in far fewer scenes, and a short high-risk list
# adds the specific combinations we know are dangerous.
FACTORS: Dict[str, List[str]] = {
    "move": ["jump_flip", "roll", "run_jump", "duck_slide"],
    "carrying": ["empty", "core"],      # both hands free, or carrying a glyph (continuity through the move)
    "surface": ["floor", "top"],        # starting on the ground or on a raised platform
    "lane": ["same", "split"],          # the other actor shares the depth lane, or passes in a separate one
    "nearby": ["clear", "crate"],       # a heavy structure in the path or not
    "pace": ["normal", "fast"],         # the pacing pass applied or not
}


def pairwise(factors: Dict[str, List[str]], seed: int = 0) -> List[dict]:
    """A small set of rows covering every pair of factor levels (a randomized-greedy covering array; deterministic)."""
    import random
    names = list(factors)
    rnd = random.Random(seed)
    need = set()
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for a in factors[names[i]]:
                for b in factors[names[j]]:
                    need.add((i, a, j, b))
    rows: List[dict] = []
    while need:
        best, best_cov = None, -1
        for _ in range(120):
            row = {n: rnd.choice(factors[n]) for n in names}
            cov = sum(1 for (i, a, j, b) in need if row[names[i]] == a and row[names[j]] == b)
            if cov > best_cov:
                best, best_cov = row, cov
        rows.append(best)
        need -= {(i, a, j, b) for (i, a, j, b) in need if best[names[i]] == a and best[names[j]] == b}
    return rows


def covers_all_pairs(factors: Dict[str, List[str]], rows: List[dict]) -> bool:
    names = list(factors)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for a in factors[names[i]]:
                for b in factors[names[j]]:
                    if not any(r[names[i]] == a and r[names[j]] == b for r in rows):
                        return False
    return True


def context_scene(row: dict) -> dict:
    """Build a scene placing KAI in the given context and having him perform the chosen move (carrying a glyph or not),
    with RHO watching from the same or a separate depth lane. The pacing pass is applied when the row asks for it."""
    on_top = row["surface"] == "top"
    obstacles = []
    deck_top = 320.0  # top surface height when standing on the deck
    base = deck_top if on_top else 0.0  # the surface KAI moves along
    if on_top:
        obstacles.append({"id": "deck", "kind": "platform", "center": [0, 300], "size": [1500, 40]})  # wide: the whole move stays on it
    if row["nearby"] == "crate":  # a solid beam standing clear of both actors and the move range (x in [-360, 180])
        obstacles.append({"id": "wall", "kind": "beam", "center": [520, base + 80], "size": [60, 160]})
    carrying = row["carrying"] == "core"
    kx = -360
    move = row["move"]
    if move == "jump_flip":
        act = [k(type="run_to", target_x=-180, speed=360), k(type="jump_to", target_x=120, height=220, **({} if carrying else {"flip": "back"}))]
    elif move == "roll":
        act = [k(type="run_to", target_x=-120, speed=360), k(type="roll", distance=150)]
    elif move == "run_jump":
        act = [k(type="run_to", target_x=-120, speed=380), k(type="jump_to", target_x=180, height=150)]
    else:  # duck_slide
        act = [k(type="run_to", target_x=-120, speed=360), k(type="duck_slide", target_x=140)]
    if row["pace"] == "fast":  # the pacing pass: runs quicker (capped), holds shorter — applied inline, not a schema field
        for a in act:
            if "speed" in a:
                a["speed"] = min(560.0, a["speed"] * 1.25)
    rho = [r(type="guard", duration=10.0)]
    kz, rz = -12, (-12 if row["lane"] == "same" else 40)
    place = {"character": K, "x": kx, "facing": 1, "z": kz}
    if on_top:
        place["on"] = "obstacle:deck"
    if carrying:
        place["carrying"] = "prop:core"
    rplace = {"character": R, "x": 320, "facing": -1, "z": rz}  # clear of the move range (x ends <= 180) and the wall (x 520)
    if on_top:
        rplace["on"] = "obstacle:deck"
    props = [{"id": "core", "kind": "glyph", "glyph": "0", "position": [kx, base + 40],
              "size": [34, 34], "mass": 2, "weight": 12, "z": 0, "depth": 16, "solid": False}]
    sc = {"id": "s", "environment": "e", "duration": 7.0, "placements": [place, rplace], "actions": act + rho,
          "shots": [{"id": "a", "start": 0, "end": 7.0, "camera": {"mode": "follow", "target": K, "view_height": 640, "include": [f"char:{R}"]}}]}
    return {"schema_version": "0.1", "id": "ctx", "title": "ctx", "fps": 24, "width": 1280, "height": 720, "seed": 5,
            "characters": [{"id": K, "name": "KAI", "strength": 50000}, {"id": R, "name": "RHO", "strength": 47000}],
            "environments": [{"id": "e", "room": {"width": 2200, "height": 1000, "entry_door": False}, "dust": 0,
                              "obstacles": obstacles, "props": props}],
            "scenes": [sc]}


# specific combinations we know are dangerous (each was a real CORE RUN failure or close to one)
HIGH_RISK: Dict[str, dict] = {
    "carry + jump_flip + crate in path": {"move": "jump_flip", "carrying": "core", "surface": "top", "lane": "split", "nearby": "crate", "pace": "fast"},
    "carry + roll on the floor": {"move": "roll", "carrying": "core", "surface": "floor", "lane": "same", "nearby": "clear", "pace": "normal"},
    "carry + duck_slide past a wall": {"move": "duck_slide", "carrying": "core", "surface": "floor", "lane": "same", "nearby": "crate", "pace": "fast"},
    "carry + run_jump between lanes": {"move": "run_jump", "carrying": "core", "surface": "top", "lane": "split", "nearby": "clear", "pace": "fast"},
}

CTX_CHECKS = TECH + ("carried_object_continuity", "props_not_floating", "characters_not_overlapping")


def run_context(row: dict) -> dict:
    """Simulate one context row and judge it on the technical checks plus the carry/float/overlap checks."""
    from ..render.pipeline import build_camera
    from ..scene.runtime import SceneRuntime
    from ..scene.schema import ProjectSpec
    from .inspector import Inspector
    try:
        p = ProjectSpec.model_validate(context_scene(row))
        rt = SceneRuntime(p, "s", strict=False)
        res = rt.simulate()
    except Exception as exc:
        return {"row": row, "ok": False, "failed": [f"engine: {str(exc)[:160]}"], "violations": {}}
    viol = {cid: c.violation for cid, c in res.controllers.items() if c.violation}
    rep = Inspector(rt, build_camera(rt, 16 / 9), 24, (1280, 720)).run(check_determinism=False)
    bad = [f"{c.name} {c.metric:.3g}" if c.metric is not None else c.name
           for c in rep.checks if c.name.startswith(CTX_CHECKS) and c.status == "FAIL"]
    return {"row": row, "ok": not bad and not viol, "failed": bad, "violations": viol}


if __name__ == "__main__":
    import sys
    if "--pairwise" in sys.argv:
        rows = pairwise(FACTORS)
        print(f"pairwise context matrix: {len(rows)} scenes cover all factor-level pairs (vs "
              f"{__import__('math').prod(len(v) for v in FACTORS.values())} full combinations); "
              f"covers_all_pairs={covers_all_pairs(FACTORS, rows)}")
        for row in rows:
            out = run_context(row)
            tag = "OK  " if out["ok"] else "FAIL"
            print(f"{tag} {' '.join(f'{k}={v}' for k, v in row.items()):70s} {'' if out['ok'] else (out['failed'], out['violations'])}")
        print("\nhigh-risk combinations:")
        for nm, row in HIGH_RISK.items():
            out = run_context(row)
            print(f"{'OK  ' if out['ok'] else 'FAIL'} {nm:45s} {'' if out['ok'] else (out['failed'], out['violations'])}")
    else:
        for nm in SCENARIOS:
            out = run(nm)
            print(f"{'OK  ' if out['ok'] else 'FAIL'} {nm:45s} {'' if out['ok'] else (out['failed_checks'], out['violations'], out['left'])}")
