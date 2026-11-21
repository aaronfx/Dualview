"""Build examples/the_rescue.json: "The Rescue" (hand-authored scene, physics-driven outcomes).

Two characters, MILO and JUNO, in a workshop:
1. MILO pushes a heavy container. It breaks loose (stick-slip friction) and outruns him; he stumbles and falls.
2. A ratchet strap ties the container to a top-heavy support post. The strap snaps taut, yanks the post over and
   snaps. The post lands on MILO and pins him (detected from contact impulses).
3. JUNO, at the bench, reacts to the `pinned` event and runs over. Her hand lift fails: the force is clamped to her
   strength.
4. JUNO grabs a pry bar from the rack, places it over the toolbox as a fulcrum under the post's end and bears down.
   The mechanical advantage lifts the load, and MILO crawls out.
5. JUNO offers a hand and pulls MILO up. A fist bump.

Every outcome comes from the simulation; the shot cuts are placed from the simulated event times.

    PYTHONPATH=src python examples/build_rescue.py examples/the_rescue.json
"""
import json, math, sys, os
P = dict(cont_x=-40.0, post_x=-340.0, post_h=270.0, slack=80.0, tool_x=2.0, bar_x=300.0, bar_l=175.0, milo_x=-300.0, juno_x=-380.0,
         bench_x=130.0, duration=20.0, push_effort=1.25, cont_m=110.0, kin_f=0.028, stat_f=0.39, post_w=18.0, com_y=70.0, break_f=900000.0)
def project(shots=None, **over):
    p = dict(P, **over)
    cont_w, cont_h = 120.0, 100.0
    post_w, post_h = p["post_w"], p["post_h"]
    top_l = (0.0, post_h / 2 - 6.0); back_l = (-cont_w / 2 + 4.0, cont_h / 2 - 8.0)
    pt = (p["post_x"] + top_l[0], post_h / 2 + 1 + top_l[1]); cb = (p["cont_x"] + back_l[0], cont_h / 2 + 1 + back_l[1])
    rope_len = math.dist(pt, cb) + p["slack"]
    D = p["duration"]
    return {
        "schema_version": "0.1", "id": "the_rescue", "title": "The Rescue", "fps": 24, "width": 1920, "height": 1080, "seed": 21,
        "characters": [
            {"id": "milo", "name": "MILO", "strength": 52000,
             "proportions": {"spine": 31, "chest": 29, "head": 25, "upper_arm": 32, "forearm": 30, "thigh": 43, "shin": 41},
             "style": {"body_color": "#ff9d2e", "far_color": "#b8651a", "visor_color": "#7df3ff", "glow_color": "#ffb45a",
                       "has_scarf": False, "limb_width": 8.0, "cadence_scale": 0.95, "stride_scale": 1.05, "lean_scale": 1.2}},
            {"id": "juno", "name": "JUNO", "strength": 45000,
             "proportions": {"spine": 28, "chest": 26, "head": 23, "upper_arm": 30, "forearm": 28, "thigh": 45, "shin": 43},
             "style": {"body_color": "#5ef0c8", "far_color": "#2b9c80", "visor_color": "#ffe15a", "glow_color": "#7cffd8",
                       "scarf_color": "#ffe15a", "has_scarf": True, "limb_width": 7.0, "cadence_scale": 1.15, "stride_scale": 0.95,
                       "lean_scale": 0.9, "arm_swing_scale": 1.25}}],
        "environments": [{
            "id": "workshop", "room": {"width": 1700, "height": 700, "depth_back": 520, "grid_spacing": 85},
            "theme": {"accent": "#7fd1ff", "alert": "#ff4b3a", "back": "#1a1d22", "floor": "#0d0f12", "side": "#15181c",
                      "ceiling": "#0a0b0d", "background": "#060708", "dust": "#d6e9ff"},
            "gravity": [0, -1568],
            "props": [
                {"id": "container", "kind": "container", "position": [p["cont_x"], cont_h / 2 + 1], "size": [cont_w, cont_h], "mass": p["cont_m"], "friction": p["kin_f"], "static_friction": p["stat_f"]},
                {"id": "post", "kind": "post", "position": [p["post_x"], post_h / 2 + 1], "size": [post_w, post_h], "mass": 80, "friction": 0.9,
                 "com": [0.0, p["com_y"]]},
                {"id": "toolbox", "kind": "toolbox", "position": [p["tool_x"], 23], "size": [46, 44], "mass": 40, "friction": 0.9,
                 "collide_characters": False, "solid": False, "z": 38, "depth": 34},
                {"id": "bar", "kind": "bar", "position": [p["bar_x"], 118], "size": [p["bar_l"], 7], "mass": 9, "friction": 0.9,
                 "angle": 1.5708, "collide_characters": False, "solid": False, "z": 30, "depth": 7}],
            "ropes": [{"id": "strap", "a": "prop:post", "a_local": list(top_l), "b": "prop:container", "b_local": list(back_l), "length": rope_len,
                       "break_force": p["break_f"]}],
            "dust": 90}],
        "scenes": [{
            "id": "rescue", "title": "The Rescue", "environment": "workshop", "duration": D,
            "goals": ["push_lost@milo", "rope_snap@strap", "pinned@milo[by=post]", "notice@juno", "lift_fail@juno", "lever_engage@juno",
                      "freed@milo", "hand_grab@milo", "stood_up@milo", "fist_bump@juno"],
            "placements": [{"character": "milo", "x": p["milo_x"], "facing": 1}, {"character": "juno", "x": p["juno_x"], "facing": 1}],
            "actions": [
                {"character": "milo", "type": "walk_to", "target_x": -230.0, "speed": 150},
                {"character": "milo", "type": "look_at", "target": "prop:container", "duration": 0.35},
                {"character": "milo", "type": "push", "target": "prop:container", "effort": p["push_effort"]},
                {"character": "milo", "type": "look_at", "target": "prop:post", "duration": 1.6},
                {"character": "milo", "type": "struggle", "until": "event:lever_engage@juno"},
                {"character": "milo", "type": "crawl_out", "distance": 40},
                {"character": "milo", "type": "get_up", "target": "char:juno"},
                {"character": "milo", "type": "gesture", "target": "char:juno", "gesture": "fist_bump"},
                {"character": "milo", "type": "idle", "duration": 3.0},
                {"character": "juno", "type": "walk_to", "target_x": p["bench_x"], "speed": 165},
                {"character": "juno", "type": "wait_for", "until": "event:pinned@milo"},
                {"character": "juno", "type": "notice", "target": "char:milo", "duration": 0.6},
                {"character": "juno", "type": "run_to", "target": "char:milo"},
                {"character": "juno", "type": "lift", "target": "prop:post", "effort": 1.0, "duration": 1.8},
                {"character": "juno", "type": "notice", "target": "prop:bar", "duration": 0.35},
                {"character": "juno", "type": "use_lever", "tool": "prop:bar", "fulcrum": "prop:toolbox", "target": "prop:post",
                 "until": "event:get_up_start@milo", "speed": 330},
                {"character": "juno", "type": "offer_hand", "target": "char:milo"},
                {"character": "juno", "type": "gesture", "target": "char:milo", "gesture": "fist_bump"},
                {"character": "juno", "type": "idle", "duration": 3.0}],
            "shots": shots or [{"id": "wide", "start": 0.0, "end": D, "kind": "wide",
                                "camera": {"mode": "static", "center": [-100, 300], "view_height": 760}}]}]}
def event_times(proj):
    from apex.scene.schema import ProjectSpec
    from apex.scene.runtime import SceneRuntime
    r = SceneRuntime(ProjectSpec.model_validate(proj), "rescue").simulate()
    ev = {}
    for e in r.events:
        ev.setdefault(f"{e.type}@{e.character}", []).append(e.t)
        ev.setdefault(e.type, []).append(e.t)
    return ev, r


def shots_from(ev, D):
    f = lambda k, i=0: ev[k][i]
    c = [0.0,
         round(f("push_start@milo") - 0.35, 2),        # 1 establishing -> push
         round(f("push_lost@milo") + 0.12, 2),         # 2 push -> accident wide
         round(f("pinned@milo") + 0.35, 2),            # 3 accident -> juno notices
         round(f("lift_start@juno") - 0.2, 2),         # 4 notice+run -> lift attempt
         round(f("lift_fail@juno") + 0.55, 2),         # 5 lift -> the idea (bar)
         round(f("lever_place@juno") - 0.25, 2),       # 6 fetch -> lever + crawl
         round(f("get_up_start@milo") + 0.2, 2),       # 7 crawl -> help up
         round(max([x for x in ev.get("turn@milo", []) if x > f("stood_up@milo")][:1] + [f("stood_up@milo")]) + 0.4, 2),  # 8 help -> friendship (after he turns to her)
         D]
    S = [
        dict(id="s01_establish", kind="establishing", description="the workshop: a heavy container, a tall support post strapped to it; MILO and JUNO walk in",
             camera=dict(mode="dolly", center=[-140, 250], center_end=[-110, 210], view_height=640, view_height_end=540)),
        dict(id="s02_push", kind="medium", description="MILO braces and strains against the container",
             camera=dict(mode="follow", target="milo", view_height=330, offset=[60, 10], lead=0.1, stiffness=4.0, include=["prop:container"]),
             sound_cues=[], exit_conditions=["event:push_start", "event:push_lost"]),
        dict(id="s03_accident", kind="wide", description="it breaks loose; MILO falls; the strap snaps taut and yanks the post over onto him",
             camera=dict(mode="static", center=[-160, 150], view_height=430, shake=1.0, include=["prop:post"]),
             exit_conditions=["event:rope_snap", "event:body_fall", "event:pinned"]),
        dict(id="s04_notice_run", kind="tracking", description="JUNO hears it, turns, sees MILO pinned and runs to him",
             camera=dict(mode="follow", target="juno", view_height=360, offset=[-40, 20], lead=0.25, stiffness=5.0, include=["char:milo"]),
             exit_conditions=["event:notice"]),
        dict(id="s05_lift", kind="medium", description="two-shot: JUNO tries to lift the post by hand and cannot",
             camera=dict(mode="static", center=[-60, 90], view_height=300, include=["char:juno"]),
             exit_conditions=["event:lift_start", "event:lift_fail"]),
        dict(id="s06_idea", kind="tracking", description="JUNO spots the pry bar on the rack, grabs it and runs back",
             camera=dict(mode="follow", target="juno", view_height=380, offset=[0, 20], lead=0.3, stiffness=5.0),
             exit_conditions=["event:pick_up"]),
        dict(id="s07_lever", kind="medium", description="the bar goes over the toolbox, JUNO bears down, the post rises, MILO crawls free",
             camera=dict(mode="static", center=[0, 85], view_height=310, include=["char:milo", "char:juno"]),
             exit_conditions=["event:lever_place", "event:lever_engage", "event:crawl_start", "event:freed"]),
        dict(id="s08_help_up", kind="medium", description="JUNO lets the post down and offers a hand; MILO takes it and is pulled to his feet",
             camera=dict(mode="follow", target="milo", view_height=300, offset=[45, 25], lead=0.05, stiffness=3.0, include=["char:juno"]),
             exit_conditions=["event:hand_grab", "event:stood_up"]),
        dict(id="s09_friends", kind="medium", description="a breath of relief, then a fist bump",
             camera=dict(mode="follow", target="milo", view_height=270, offset=[45, 35], lead=0.0, stiffness=2.5, include=["char:juno"]),
             exit_conditions=["event:fist_bump"], fade_out=0.8),
    ]
    for i, s in enumerate(S):
        s["start"], s["end"] = c[i], c[i + 1]
    return S


if __name__ == "__main__":
    import json as _json
    import sys as _sys
    out = _sys.argv[1]
    over = _json.loads(_sys.argv[2]) if len(_sys.argv) > 2 else {}
    proj = project(**over)
    ev, _ = event_times(proj)
    proj = project(shots=shots_from(ev, proj["scenes"][0]["duration"]), **over)
    _json.dump(proj, open(out, "w"), indent=1)
    for s in proj["scenes"][0]["shots"]:
        print(f"{s['id']:16s} {s['start']:6.2f} - {s['end']:6.2f}  {s['description']}")
