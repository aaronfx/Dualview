"""APEX motion-quality proof checks, all grounded in the existing rig and physics.

These are objective structural/simulation tests. Human artistic scores come
from review packets, never from this test module.
"""
from __future__ import annotations

import math
from apex.motion.library import Performance, get_clip
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime


def test_antcipation_clip_contains_distinct_recoil_and_load():
    clip = get_clip("doubt_to_dash")
    assert clip.duration == 1.18 and len(clip.keys) >= 7
    assert clip.phase_at(0.75) == "anticipation"
    assert clip.phase_at(1.1) == "follow_through"
    recoil = clip.sample(0.19)
    load = clip.sample(0.87)
    assert recoil["lean"] < -0.10
    assert load["lean"] > 0.20
    assert load["crouch"] - recoil["crouch"] > 0.14
    assert clip.sample(0.19)["eye"] >= 1.3
    assert abs(clip.sample(1.18)["crouch"]) < 0.05
    assert 0.0 < clip.length(Performance(tempo=1.2)) < clip.length()


def test_recovery_clip_has_real_contact_stability_and_settle():
    clip = get_clip("impact_to_grin")
    assert len(clip.keys) >= 6
    assert {"follow_through", "reaction", "settle"} <= {phase[0] for phase in clip.phases}
    assert len(clip.contacts) == 2
    for c in clip.contacts:
        assert c.on.startswith("joint:knee_")
        assert c.t0 == 0.0 and c.t1 > 0.70
        assert c.t1 <= clip.duration
    absorb = clip.sample(0.17)
    finale = clip.sample(1.22)
    assert absorb["crouch"] - finale["crouch"] > 0.20
    assert absorb["lean"] > finale["lean"] + 0.60
    assert finale["eye"] >= 1.0
    assert not any(not math.isfinite(v) for t in (0, 0.19, 0.44, 0.71, 1.15) for v in clip.sample(t).values())


def test_original_threshold_scene_is_real_physics_and_shots_follow_events():
    # Import the user-facing builder by path, not a copied golden JSON.
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "examples" / "build_motion_performance_probe.py"
    spec = importlib.util.spec_from_file_location("build_motion_performance_probe", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    project, events = module.build()
    assert isinstance(project, ProjectSpec)
    scene = project.scenes[0]
    assert 7.0 < scene.duration <= 17.0
    assert len(scene.shots) == 4
    assert all(b.start == a.end for a,b in zip(scene.shots, scene.shots[1:]))
    assert scene.shots[0].start == 0 and scene.shots[-1].end == scene.duration
    assert {e for e in ("takeoff", "impact", "pick_up")} <= {k[0] for k in events}
    result = SceneRuntime(project, scene.id).simulate(physics_only=True)
    key = [(e.type, e.t) for e in result.events if e.character == "iko" and
           e.type in ("takeoff", "impact", "pick_up")]
    assert any(x[0] == "takeoff" for x in key)
    assert any(x[0] == "impact" for x in key)
    assert any(x[0] == "pick_up" for x in key)
    pick = next(e for e in result.events if e.type == "pick_up" and e.character == "iko")
    assert pick.data["prop"] == "spark"
