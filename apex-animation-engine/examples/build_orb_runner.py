"""Build examples/orb_runner.json: "Orb Runner" (Milestone 4 test film).

A level drawn as a grid (the level builder), played to a 120 bpm beat:
1. IKO waits for the bar, then runs. A launch pad throws him up; a jump orb at the top of the arc gives him a
   second jump with a front flip; he takes a star at its apex and lands on a block.
2. He runs off the block into a floor portal and comes out of its partner on a high ledge, at full speed.
3. Off the end of the ledge he jumps for the floor; a boost orb in the air carries him over the pit onto the far
   tower instead.
4. PELL, on the floor, throws a "+" into a portal in the wall; it comes out of its partner above the tower and lands
   by IKO, who picks it up on the beat.

Every outcome is simulated: the orbs change the body's velocity, the portals move bodies with their momentum, the
grid becomes ordinary platforms. Cuts are placed from the simulated events and snapped to the beat.

    PYTHONPATH=src python examples/build_orb_runner.py examples/orb_runner.json
"""
import json
import sys

CELL = 60.0


def _grid(n_rows: int, n_cols: int, items) -> list:
    """Rows from (row, col, text) placements (easier to read and to edit than counting spaces)."""
    g = [[" "] * n_cols for _ in range(n_rows)]
    for r, c, txt in items:
        for k, ch in enumerate(txt):
            g[r][c + k] = ch
    return ["".join(row) for row in g]


ROWS = _grid(10, 30, [
    (1, 25, "b"),                      # boost orb, on the boosted jump's way down from the ledge
    (2, 20, "a"),                      # exit of the floor portal, standing on the high ledge
    (3, 12, "*"), (3, 20, "======"),   # a star at the second apex; the high ledge
    (5, 9, "o"),                       # jump orb at the top of the pad's arc (with a front flip)
    (7, 27, "###"), (8, 27, "###"), (9, 27, "###"),   # the far tower
    (8, 14, "####"), (9, 14, "####"),  # the landing block
    (8, 0, "C"), (0, 28, "c"),         # PELL's throw goes into the wall here ...
    (9, 1, "1"), (9, 3, "2"), (9, 6, "^"), (9, 20, "A"),
])
LEGEND = {"^": {"power": 150.0}, "o": {"power": 120.0, "flip": "front"}, "b": {"power": 260.0},
          "A": {"angle": 180.0}, "a": {"angle": 0.0},
          "C": {"angle": 0.0, "height": 120.0},
          "c": {"angle": -90.0, "height": 110.0, "center": [790.0, 600.0]}}  # ... and drops out above the tower


def project(shots=None, duration=14.5, bpm=120.0):
    D = duration
    return {
        "schema_version": "0.1", "id": "orb_runner", "title": "Orb Runner", "fps": 24, "width": 1280, "height": 720, "seed": 31,
        "characters": [
            {"id": "iko", "name": "IKO", "strength": 48000,
             "proportions": {"spine": 29, "chest": 27, "head": 23, "thigh": 45, "shin": 43},
             "style": {"body_color": "#ffd84a", "far_color": "#b8962a", "visor_color": "#7cf6ff", "glow_color": "#ffe07a",
                       "scarf_color": "#ff5ab4", "has_scarf": True, "limb_width": 7.5, "cadence_scale": 1.05}},
            {"id": "pell", "name": "PELL", "strength": 52000,
             "proportions": {"spine": 31, "chest": 29, "head": 24, "thigh": 43, "shin": 41},
             "style": {"body_color": "#6fe3ff", "far_color": "#3d93ad", "visor_color": "#ffd166", "glow_color": "#a8f0ff",
                       "has_scarf": False, "limb_width": 8.0, "cadence_scale": 0.95}}],
        "environments": [{
            "id": "grid", "room": {"width": 1800, "height": 820, "depth_back": 520, "grid_spacing": 60, "entry_door": False},
            "theme": {"accent": "#ff5ab4", "alert": "#ffd84a", "back": "#141026", "floor": "#0b0916", "side": "#120e22",
                      "ceiling": "#08060f", "background": "#05040a", "dust": "#ffd9f2"},
            "dust": 70,
            "level": {"cell": CELL, "origin": [-900.0, 0.0], "rows": ROWS, "legend": LEGEND},
            "portals": [],
            "props": [{"id": "plus", "kind": "glyph", "glyph": "+", "position": [-630.0, 20.0], "size": [40.0, 40.0], "mass": 3.0,
                       "weight": 10.0, "color": "#ffd84a", "z": 40, "depth": 20}]}],
        "scenes": [{
            "id": "run", "title": "Orb Runner", "environment": "grid", "duration": D,
            "music": {"bpm": bpm, "offset": 0.0, "snap_cuts": True},
            "goals": ["orb_pad@iko", "orb_jump@iko", "collect@iko", "portal_enter@iko", "portal_exit@iko", "orb_boost@iko",
                      "throw@pell", "portal_exit@plus", "pick_up@iko"],
            "placements": [{"character": "iko", "at": "1", "facing": 1, "z": -10}, {"character": "pell", "at": "2", "facing": 1, "z": 40}],
            "actions": [
                {"character": "iko", "type": "wait_beat", "beats": 4},
                {"character": "iko", "type": "run_to", "target_x": 860.0},  # ends where he runs into the floor portal
                {"character": "iko", "type": "run_to", "target_x": 615.0},  # out of its partner, along the high ledge
                {"character": "iko", "type": "jump_to", "target_x": 690.0, "height": 50.0},  # aimed at the floor ...
                {"character": "iko", "type": "walk_to", "target_x": 770.0},  # ... the boost puts him on the tower
                {"character": "iko", "type": "wait_for", "until": "event:portal_exit@plus"},
                {"character": "iko", "type": "pick_up", "target": "prop:plus"},
                {"character": "iko", "type": "idle", "duration": 3.0},
                {"character": "pell", "type": "wait_for", "until": "event:orb_boost@iko"},
                {"character": "pell", "type": "pick_up", "target": "prop:plus"},
                {"character": "pell", "type": "wait_beat", "beats": 2},
                {"character": "pell", "type": "throw", "target": "point:-1000,60"},
                {"character": "pell", "type": "idle", "duration": 4.0}],
            "shots": shots or [{"id": "wide", "start": 0.0, "end": D, "kind": "wide",
                                "camera": {"mode": "static", "center": [0, 330], "view_height": 760}}]}]}


def event_times(proj):
    from apex.scene.runtime import SceneRuntime
    from apex.scene.schema import ProjectSpec
    r = SceneRuntime(ProjectSpec.model_validate(proj), "run").simulate(physics_only=True)
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
    return ev


def shots_from(ev, D):
    f = lambda k, i=0: ev[k][i]
    c = [0.0,
         round(f("beat_wait_end@iko") - 0.25, 2),   # 1 the level -> IKO sets off
         round(f("portal_enter@iko"), 2),           # 2 pad, flip orb, star, block -> into the floor portal
         round(f("impact@iko", 2) + 0.45, 2),       # 3 out on the ledge, the boosted jump, onto the tower
         round(f("throw@pell") + 0.2, 2),           # 4 PELL picks up the plus and throws it into the wall
         D]                                          # 5 it drops out above the tower; IKO picks it up
    S = [
        dict(id="s01_level", kind="establishing", description="the grid level: pad, orbs, portals, the far tower; IKO waits for the bar",
             camera=dict(mode="dolly", center=[-60, 380], center_end=[-200, 330], view_height=900, view_height_end=760)),
        dict(id="s02_run", kind="tracking", description="IKO runs: the pad launches him, the jump orb flips him, he takes the star, lands, drops into the portal",
             camera=dict(mode="follow", target="iko", view_height=470, offset=[90, 40], lead=0.3, stiffness=4.5)),
        dict(id="s03_ledge", kind="tracking", description="out of the partner portal on the high ledge; the jump for the floor, the boost, the tower",
             camera=dict(mode="follow", target="iko", view_height=560, offset=[110, -20], lead=0.25, stiffness=4.0, include=["point:780,180"])),
        dict(id="s04_throw", kind="medium", description="PELL picks up the plus and throws it at the wall portal",
             camera=dict(mode="follow", target="pell", view_height=380, offset=[-90, 40], lead=0.1, stiffness=4.0,
                         include=["point:-870,120"])),
        dict(id="s05_drop", kind="medium", description="the plus drops out of the ceiling portal onto the tower; IKO picks it up on the beat",
             camera=dict(mode="static", target="iko", center=[400, 380], view_height=580, include=["point:790,600"]), fade_out=0.8),
    ]
    for i, sh in enumerate(S):
        sh["start"], sh["end"] = c[i], c[i + 1]
        sh["camera"]["bound_to_room"] = True  # never look past the walls
    return S


if __name__ == "__main__":
    out = sys.argv[1]
    proj = project()
    proj = project(shots=shots_from(event_times(proj), proj["scenes"][0]["duration"]))
    json.dump(proj, open(out, "w"), indent=1)
    for sh in proj["scenes"][0]["shots"]:
        print(f"{sh['id']:12s} {sh['start']:6.2f} - {sh['end']:6.2f}  {sh['description']}")
