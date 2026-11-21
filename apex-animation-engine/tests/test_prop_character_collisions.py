"""Standing characters block solid moving props.

The collision mask is a physics contract, not merely a rendering effect.
Ghost/set-dressing props remain non-colliding when explicitly requested.
"""
import json
import math

from apex.physics.world import PhysicsWorld
from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec

from .conftest import ROOT


def _prop_approaches_standing_character(*, collide_characters=True, ghost=False):
    world = PhysicsWorld((0, 0))
    # Tall capsule occupies x near 40, with its lower half inside the box.
    world.add_capsule("actor", (40, 90), (0, -48), (0, 48), 9.0, 70, kinematic=True)
    world.add_box("crate", (-90, 57), (40, 56), 40, friction=0.1,
                  collide_characters=collide_characters)
    if ghost:
        world.set_solid_to_props("actor", False)
    world.set_dynamic("crate", (300, 0), 0, 40, world._mass_moment["crate"][1])
    events = []
    for _ in range(240):
        events.extend(world.step(1 / 240))
    return world, events


def test_moving_solid_prop_cannot_cross_standing_character():
    world, events = _prop_approaches_standing_character()
    assert world.state("crate").pos[0] < 30.0, (
        "solid crate tunneled through the standing character"
    )
    assert any({ev.a, ev.b} == {"actor", "crate"} for ev in events), (
        "standing/prop contact must be detected"
    )


def test_prop_opt_out_and_explicit_ghost_still_work():
    no_collision, events = _prop_approaches_standing_character(collide_characters=False)
    assert no_collision.state("crate").pos[0] > 80
    assert not any({e.a, e.b} == {"actor", "crate"} for e in events)
    ghost, events = _prop_approaches_standing_character(ghost=True)
    assert ghost.state("crate").pos[0] > 80
    assert not any({e.a, e.b} == {"actor", "crate"} for e in events)


def test_rescue_juno_stays_behind_container_during_push():
    d = json.loads((ROOT / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
    rt = SceneRuntime(ProjectSpec.model_validate(d), "rescue")
    rt.simulate()
    push = next(s for s in rt.result.controllers["milo"].segments if s.kind == "push")
    juno = rt.result.controllers["juno"]
    for record in juno.records:
        if push.t0 <= record.t <= min(push.t1, 3.4):
            assert record.s < -320, "JUNO walked into the active push path"
    event_types = {event.type for event in rt.result.events}
    assert {"push_lost", "body_fall", "pinned", "lift_fail",
            "crawl_start", "freed", "hand_grab", "stood_up", "fist_bump"} <= event_types
