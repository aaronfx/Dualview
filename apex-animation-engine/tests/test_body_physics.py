"""Critical fix: characters and dynamic props interact through a bounded-force physical body.

No ghosting (props never pass through a standing body) and no infinite-mass pushing (a scripted character can push
with at most its strength). Covers the reversal reported on PR #7: a heavy container driven ~294 units backwards by a
kinematic character.
"""
import math

from apex.scene.runtime import SceneRuntime
from apex.scene.schema import ProjectSpec


def proj(acts, props, dur=6.0, placements=None, room_depth_lanes=True):
    return ProjectSpec.model_validate({
        "schema_version": "0.1", "id": "t", "title": "t", "fps": 24, "width": 640, "height": 360, "seed": 3,
        "characters": [{"id": "kai", "name": "KAI", "proportions": {"spine": 30, "chest": 28, "head": 24, "thigh": 44, "shin": 42}}],
        "environments": [{"id": "e", "room": {"width": 1800, "height": 900, "entry_door": False}, "props": props, "dust": 0}],
        "scenes": [{"id": "s", "environment": "e", "duration": dur,
                    "placements": placements or [{"character": "kai", "x": 0, "facing": -1}], "actions": acts,
                    "shots": [{"id": "a", "start": 0, "end": dur, "camera": {"mode": "follow", "target": "kai", "view_height": 600}}]}]})


def sim(p):
    return SceneRuntime(p, "s", strict=False).simulate(physics_only=True)


def ev(r, kind):
    return [e for e in r.events if e.type == kind]


# a heavy container as deep as the room's usable lanes allow: it cannot be stepped around in depth
WALL_DEEP = dict(kind="container", size=[120, 100], mass=110, friction=0.03, static_friction=0.39, depth=150)


def test_a_sliding_container_never_passes_through_a_standing_body():
    box = dict(WALL_DEEP, id="box", position=[-400, 51])
    p = proj([{"character": "kai", "type": "idle", "duration": 6}], [box])
    p.environments[0].props[0].position = (-400.0, 51.0)
    rt = SceneRuntime(p, "s", strict=False)
    # launch it at the character (as a container breaking loose would)
    import apex.scene.runtime as R
    orig = R.PhysicsWorld.step
    fired = [False]

    def step(self, dt):
        if not fired[0]:
            self._bodies["box"].velocity = (420.0, 0.0)
            fired[0] = True
        return orig(self, dt)
    R.PhysicsWorld.step = step
    try:
        r = rt.simulate(physics_only=True)
    finally:
        R.PhysicsWorld.step = orig
    c = r.controllers["kai"]
    xs = r.prop_tracks["box"][:, 0]
    body_x = [rec.pos[0] for rec in c.records]
    # the box's face never gets past the body (half width 60 + body radius 11, small solver slop allowed)
    assert all(x + 60 <= bx - 11 + 4 for x, bx in zip(xs, body_x[:len(xs)]))
    assert ev(r, "shoved"), "the impact displaces the character"
    assert max(body_x) - body_x[0] < 160  # displaced, bounded by the momentum it took


def test_a_character_cannot_drive_a_heavy_container_backwards():
    """The PR #7 case: the container rests against a scripted character who then walks into it."""
    box = dict(WALL_DEEP, id="box", position=[-80, 51])
    r = sim(proj([{"character": "kai", "type": "walk_to", "target_x": -400}], [box]))
    x = r.prop_tracks["box"][:, 0]
    assert abs(x[-1] - x[0]) < 3.0, f"moved {x[-1] - x[0]:.1f} units"  # static friction > the character's strength
    assert ev(r, "prop_block")
    assert r.controllers["kai"].records[-1].pos[0] > -80 + 60  # stopped at it, not through it


def test_a_light_crate_is_pushed_with_bounded_force():
    crate = dict(kind="crate", id="crate", position=[-80, 31], size=[60, 60], mass=12, friction=0.5, depth=150)
    r = sim(proj([{"character": "kai", "type": "walk_to", "target_x": -400, "speed": 100}], [crate]))
    x = r.prop_tracks["crate"][:, 0]
    assert x[-1] < x[0] - 100  # it was pushed along
    v = (x[1:] - x[:-1]) * 240.0
    w = 24  # 0.1 s windows: the sustained push force (a bump's momentary contact impulse is bounded separately)
    force = max(abs(v[i + w] - v[i]) * 12 / 0.1 for i in range(len(v) - w))
    assert force < 45000.0 * 1.15 + 8 * 100 / 0.1  # at most the character's strength (+ the light contact mass's bump)


def test_walks_plan_around_props_in_depth():
    box = dict(kind="container", id="box", position=[-200, 51], size=[120, 100], mass=110, friction=0.03, static_friction=0.39)
    r = sim(proj([{"character": "kai", "type": "walk_to", "target_x": -500}], [box],
                 placements=[{"character": "kai", "x": 0, "facing": -1, "z": 10}]))
    assert ev(r, "sidestep") and not ev(r, "prop_block") and not ev(r, "shoved")
    x = r.prop_tracks["box"][:, 0]
    assert abs(x[-1] - x[0]) < 1e-6  # never touched
    c = r.controllers["kai"]
    assert abs(c.s - -500) < 2.0 and abs(c.z - 10) < 1e-6  # arrived, and back in its own lane


def test_planned_sidestep_tracks_every_blocker_and_returns_home():
    # Opposite depth lanes, same horizontal route. Both are physically passable
    # via a third lane. The lane choice must remain safe for both containers.
    box = dict(kind="container", size=[100, 100], mass=110, friction=0.03,
               static_friction=0.39, depth=40)
    props = [dict(box, id="near", position=[-200, 51], z=-10),
             dict(box, id="far", position=[-420, 51], z=30)]
    r = sim(proj([{"character":"kai","type":"walk_to","target_x":-650}], props,
                 dur=9.0, placements=[{"character":"kai","x":0,"facing":-1,"z":10}]))
    steps = ev(r, "sidestep")
    assert steps and {"near","far"} <= set(steps[0].data["props"])
    assert not ev(r,"prop_block") and not ev(r,"shoved")
    for pid in ("near","far"):
        xs = r.prop_tracks[pid][:,0]
        assert abs(xs[-1]-xs[0]) < 1e-6
    c = r.controllers["kai"]
    assert abs(c.s+650) < 2.0 and abs(c.z-10) < 1e-6


def test_avoidance_events_are_available_to_native_story_contracts():
    from apex.scene.goals import check_event
    for event in ("sidestep","prop_block","body_block","shoved"):
        check_event(event,"movement")


def test_live_route_refresh_for_new_moving_container(monkeypatch):
    """A container outside the route at action start later slides into it."""
    from apex.physics.world import PhysicsWorld
    box = dict(kind="container", id="late", position=[-650, 51],
               size=[100, 100], mass=110, friction=0.01, depth=40)
    original = PhysicsWorld.step
    launched = False

    def step(world, dt):
        nonlocal launched
        if not launched and world.t >= 0.2:
            world._bodies["late"].velocity = (220.0, 0.0)
            launched = True
        return original(world, dt)

    monkeypatch.setattr(PhysicsWorld, "step", step)
    r = sim(proj([{"character": "kai", "type": "walk_to", "target_x": -500,
                   "speed": 100}], [box], dur=7))
    assert launched
    refreshed = [e for e in ev(r, "sidestep") if e.data.get("refreshed")]
    assert refreshed and refreshed[0].data["prop"] == "late"
    assert not ev(r, "prop_block") and not ev(r, "shoved")
    assert abs(r.controllers["kai"].s + 500) < 2.0


def test_moving_container_is_anticipated_before_entering_route(monkeypatch):
    from apex.physics.world import PhysicsWorld
    box = dict(kind="container", id="incoming", position=[-680, 51],
               size=[100, 100], mass=110, friction=0.01, depth=40)
    original = PhysicsWorld.step
    launched = False

    def step(world, dt):
        nonlocal launched
        if not launched and world.t >= 0.2:
            world._bodies["incoming"].velocity = (220.0, 0.0)
            launched = True
        return original(world, dt)

    monkeypatch.setattr(PhysicsWorld, "step", step)
    r = sim(proj([{"character": "kai", "type": "walk_to",
                   "target_x": -500, "speed": 100}], [box], dur=7))
    event = next(e for e in ev(r, "sidestep") if e.data.get("refreshed"))
    index = min(round(event.t * 240), len(r.prop_tracks["incoming"]) - 1)
    # The prop's leading face is still beyond the original route boundary.
    assert r.prop_tracks["incoming"][index, 0] + 50 < -511
    assert not ev(r, "prop_block") and not ev(r, "shoved")
    assert abs(r.controllers["kai"].s + 500) < 2.0


def test_carried_depth_expands_existing_lane_clearance():
    # Native pickup, then inspect the actual controller's lane chooser.
    item = dict(kind="crate", id="item", position=[-65, 31],
                size=[60, 60], mass=2, depth=80)
    r = sim(proj([{"character":"kai","type":"pick_up","target":"prop:item"},
                  {"character":"kai","type":"idle","duration":2}], [item], dur=4))
    c = r.controllers["kai"]
    assert c.carrying == "item"
    assert c._route_half_depth() == 40
    lane = c._free_lane([("hypothetical", 0.0, 10.0)])
    assert lane is not None and abs(lane) >= 53


def _carry_blocked_project(duration=8):
    item = dict(kind="crate", id="item", position=[-65, 31],
                size=[60, 60], mass=2, depth=80)
    wall = dict(kind="container", id="wall", position=[-260, 90],
                size=[90, 180], mass=110, friction=0.5, depth=150)
    return proj([{"character":"kai","type":"pick_up","target":"prop:item"},
                 {"character":"kai","type":"walk_to","target_x":-500,"speed":100}],
                [item, wall], dur=duration)


def test_carried_load_waits_if_no_clear_lane():
    r = sim(_carry_blocked_project())
    c = r.controllers["kai"]
    assert c.carrying == "item"
    assert any(e.data["prop"] == "wall" for e in ev(r, "route_wait"))
    assert not ev(r, "route_resume")
    assert c.s > -260
    # The held load remains outside the wall's horizontal face.
    assert r.prop_tracks["item"][-1, 0] - 30 >= r.prop_tracks["wall"][-1, 0] + 45 - 1


def test_carried_load_resumes_after_native_obstacle_removal(monkeypatch):
    from apex.physics.world import PhysicsWorld
    original = PhysicsWorld.step
    removed = False

    def step(world, dt):
        nonlocal removed
        if not removed and world.t >= 4.0:
            world.deactivate("wall")
            removed = True
        return original(world, dt)

    monkeypatch.setattr(PhysicsWorld, "step", step)
    r = sim(_carry_blocked_project(duration=12))
    assert removed and ev(r, "route_wait") and ev(r, "route_resume")
    assert ev(r, "route_resume")[0].t >= 4.0
    assert abs(r.controllers["kai"].s + 500) < 2
