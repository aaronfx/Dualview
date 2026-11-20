# Milestone status report

All numbers below come from actual runs. Raw evidence is in `docs/evidence/`: `pytest_results.txt`, `*_qa.json` and `ffprobe_demos.txt`.

| Milestone | Status |
|---|---|
| 1A Rig and motion | **Done**, verified |
| 1B Physical interaction | **Done**, verified |
| 1C Cinematic rendering | **Partial**: environment, cameras, lighting effects, event-bound sound effects. Missing: music, scarf and cloth secondary motion, insert and close-up shot vocabulary, camera roll transitions |
| 1D Full 30 s Gravity Switch | **Not started** (next) |

---

## Milestone 1A — Rig and motion

**Problem statement.** Build a reusable articulated character whose locomotion reads as weight-bearing, not sliding: walk, run, jump and land, with planted feet and IK.

**Implementation.**
- `rig/skeleton.py`: hierarchical bones with parent attachment, joint limits and FK.
- `rig/ik.py`: analytic two-bone IK with a bend side and a stretch cap.
- `rig/stickman.py`: the 16-bone stickman (Proportions), `Pose` (root, body angle, facing, local angles, squash, head direction, expression, hand shapes), angle-aware blending, leg/arm/fingertip IK in world space.
- `motion/gait.py`: speed-driven cadence and stride. Walk/run blend via stance fraction (double support down to flight). Footfalls are planted surface points, centred under the pelvis. Swing arcs, pelvis bob.
- `motion/animator.py`: lean from acceleration, arm counter-swing, the reach constraint (hips lower instead of feet dragging), toe-above-surface clamp, settle steps after stopping.
- `motion/controller.py`: run-up jump with prep crouch, physics ballistic flight, landing with compression that continues into the run.

**Evidence.** `out/motion_test.mp4` (1920×1080, 24 fps, 204 frames, 8.5 s; H.264 + AAC). Sequence: idle → walk → accelerate to run → crouch → jump → tuck → brace → land (impact ring) → run → brake → settle → idle. Reviewed as contact sheets during development, including the jump section frame by frame.

**Tests.** `tests/test_rig.py` (hierarchy, FK lengths for 50 random poses, IK for 200 random targets, world-space leg IK at four facing/rotation combinations, blend shortest arc). `tests/test_motion.py` (feet static in stance, alternating and advancing footfalls, stance centred within 6 units, walk has double support and run has flight). `tests/test_runtime.py::test_motion_scene_jump_is_ballistic_and_lands`.

**Results (QA of the 1080p render).**

| Check | Result |
|---|---|
| Bone-length ratio | 1.000–1.080 (limit 0.86–1.13) |
| Foot drift during stance | 4e-14 (limit 1.5) |
| Max joint speed | 2441 u/s (limit 3200) |
| Floor penetration | 0.07 (limit 4) |
| Airborne acceleration vs gravity | 6e-11° |
| Frames | 204/204 |
| A/V duration difference | 0.000 s |
| Deterministic replay | identical hash |

All 24 checks PASS.

**Defects found and fixed during this milestone.** The inspector found each of these on real renders:
- **Direction re-decided mid-move:** the move direction was recomputed every step, so overshooting a target reversed the character.
- **Stance not centred:** stance wasn't centred under the pelvis, leaving a foot behind (67.6-unit slide when braking).
- **Stale plant after landing:** the first post-landing footfall reused an old plant (34.6-unit slide).
- **Toe in floor:** the toe went 6.4 units into the floor during swing.

**Limitations.**
- Only one character style (proportions are configurable).
- No turn-in-place blending beyond a 2D snap turn with head anticipation.
- Climbing, rolling, pushing, pulling, dodging and fighting are **not implemented**.
- The jump is supported only from a run-up.

---

## Milestone 1B — Physical interaction

**Problem statement.** The character presses a physical switch. The switch changes the gravity vector. The character loses support, falls on an understandable trajectory, braces, lands with compression on the new surface and recovers, with no teleporting and no scene rotation.

**Implementation.**
- `physics/gravity.py`: gravity vector with timed transitions and G-state labels.
- `physics/world.py`: `PhysicsWorld` interface over pymunk (static room colliders, rigid props, character capsule, ray-casts, contact events with normal and approach speed).
- `motion/controller.py`:
  - **Press:** fingertip contact at a scripted instant raises `press_contact`, which schedules the gravity transition.
  - **Support test:** the character is unsupported once gravity leaves a 55° cone around the surface normal. The body then becomes dynamic with lift and tip-over torque.
  - **Brace:** a velocity ray-cast predicts the impact surface and time to contact; under 0.65 s an angular controller aligns the feet to that surface.
  - **Landing:** on contact the body switches to a kinematic landing, with spring compression driven by approach speed, tangential slide decay, balance wobble and recovery into idle in the new `GroundFrame`.
- `motion/animator.py`: feet plant exactly where they touched; foot pitch is relative to the surface; the rebound is capped at leg reach.

**Evidence.** `out/gravity_switch_1b.mp4` (1920×1080, 24 fps, 252 frames, 10.5 s).
- Press contact at t = 4.583 s; a full-resolution still shows the fingertip on the dome.
- Gravity rotates from (0, −1568) to (1568, 0) between 5.033 and 5.233 s.
- `lost_support` at 5.142 s, `brace` at 5.662 s, wall impact at 6.000 s (approach 1335 u/s), `recovered` at 7.133 s.
- Both crates slide into the same wall (`prop_impact` events).

**Tests.** `tests/test_physics.py` (rotation, labels, no overlapping transitions, body acceleration purely along a sideways gravity vector, collision normal and speed, kinematic bodies unaffected). `tests/test_runtime.py`:
- causal event order: press → switch → gravity shift → lost support → brace → impact(wall_right) → recovered;
- the transition's cause is the switch id;
- the character ends standing on `wall_right`, upright within 1°;
- 200 random-time evaluations are finite;
- deterministic replay.

**Results (QA of the 1080p render).**

| Check | Result |
|---|---|
| Foot drift during planted intervals | max 0.90 (limit 1.5) |
| Bone-length ratio | 0.929–1.115 |
| Max joint speed | 2816 u/s (limit 3200) |
| Wall penetration | 0.0 |
| Airborne acceleration vs gravity | 2.05° worst (limit 3°), magnitude error 0.000 %; the residual comes from sampling inside the 0.2 s rotation |
| Gravity transition caused by the switch | PASS |
| Geometry identical across runs, never moved | PASS |
| Subject in frame | 98.4 % |
| Exit conditions | 5/5 |
| Frames | 252/252 |
| A/V duration difference | 0.000 s |

All 26 checks PASS.

**Defects found and fixed.**
- **Feet re-targeted on impact:** landing feet were re-targeted on impact (95-unit jump in 2 frames, joint-speed spike 5237 u/s). They now plant where they touched.
- **Rebound lifted the feet:** the spring rebound overshot leg reach.
- **Knee through the wall:** a knee penetrated the wall at full compression (minimum compression raised, brace strengthened).

**Limitations.**
- The press is a keyframed action whose fingertip is IK-targeted. Contact timing is authored, not solved from hand-to-button collision.
- The character is a single capsule in physics; limbs don't collide individually.
- Brace alignment is cartoon "air control" (an angular-velocity controller), not momentum-conserving.

---

## Milestone 1C — Cinematic rendering (partial)

**Done.**
- 2.5D cutaway chamber with a perspective grid, entry door, console with live gravity-direction display and red button.
- Bloom, floor reflection, contact shadows, vignette, optional multi-sample motion blur.
- Effects bound to events: red alarm wash, floor shockwave rings, gravity sweep, wall impact ring, dust.
- Camera rigs: static, follow, track_x, dolly; smoothing resets at cuts; keep-in-frame guard.
- Event-bound synthesized sound effects with ambience.

**Not done (next).**
- Music.
- Scarf and cloth secondary motion.
- Camera roll transitions, the insert-shot vocabulary and per-shot depth of field.
- Volumetric light shafts.

---

## Also delivered ahead of plan (foundations only)

- **AI Story Director** (`ai/director.py`). Provider-agnostic. The model must return schema-valid JSON, which is then dry-run simulated. Validation errors are fed back for up to two repair attempts. Tested with a fake provider. **No live LLM call was made** in this environment (no API key configured).
- **Offline TemplatePlanner.** Rule-based, clearly labelled as not AI. It retimes shots from a dry-run simulation. Proven end-to-end: "Nova sprints … gravity swings to the left wall" plans, simulates, renders and passes QA (`docs/evidence/planned_nova_qa.json`). QA found two planner bugs here (shots not matching the simulation; a dropped final frame from non-frame-aligned durations), both fixed and covered by regression tests.
- **FastAPI backend** with SQLite storage, scene-level render jobs, progress and error capture, and video download. Tested end-to-end with `TestClient`.

## Test results

`pytest -v`: **39 passed**, 0 failed, in about 12 s (Python 3.13, Linux). Full list in `docs/evidence/pytest_results.txt`.

## Next milestone (1D) — plan

1. Port secondary motion: a verlet scarf on the rig's neck anchor, driven by the gravity field.
2. Add a music layer (event-aware), insert and close-up shot types, and camera roll transitions to the camera director.
3. New actions: `point`, `duck_slide`, `grab_swing` (hands IK-locked to a ledge, pendulum about the grip), `reach_handle`.
4. A G2 (ceiling) reversal in the same scene, a door prop with unlock state, and falling obstacle panels as pymunk bodies.
5. Author the full 30 s story as a `ProjectSpec` (several scenes or shots), render, QA, and review frames against `Gravity_Switch_30s_FINAL_1080p.mp4`.
