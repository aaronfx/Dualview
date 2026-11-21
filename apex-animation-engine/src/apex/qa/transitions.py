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


if __name__ == "__main__":
    for nm in SCENARIOS:
        out = run(nm)
        print(f"{'OK  ' if out['ok'] else 'FAIL'} {nm:45s} {'' if out['ok'] else (out['failed_checks'], out['violations'], out['left'])}")
