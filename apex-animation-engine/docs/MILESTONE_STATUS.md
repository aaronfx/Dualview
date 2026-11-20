# Milestone status report

All numbers below come from actual runs. Raw evidence is in `docs/evidence/`: `pytest_results.txt`, `*_qa.json` and `ffprobe_demos.txt`.

| Milestone | Status |
|---|---|
| 1A Rig and motion | **Done**, verified |
| 1B Physical interaction | **Done**, verified |
| 1C Character acting + cinematic direction | **Implemented, technically verified** (37/37 QA checks, 66/66 tests, full decode). **Artistic quality: self-reviewed, awaiting owner review**; see the separate assessment below. Not claimed as professional quality on the strength of numeric tests. |
| 1D Full 30 s Gravity Switch | **Prepared, not started**; gated on 1C review. Plan in `docs/MILESTONE_1D_PLAN.md` |

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

## Milestone 1C — Character acting and cinematic direction

**Problem statement.** The engine moved AXEL correctly, but AXEL didn't *act*, and the camera filmed without directing. 1C adds the following, verified on a 14 s sequence that must read without narration:
- anticipation, gaze, weight shift and follow-through;
- secondary motion that responds to velocity and gravity;
- a shot vocabulary (establishing, close, insert, tracking);
- justified camera roll and continuity checks.

**The review sequence** (`examples/gravity_switch_1c.json`, 14.0 s, 6 shots):

| Shot | Time | Beat | Engine events |
|---|---|---|---|
| s1_establish (static wide) | 0–1.75 | Room, entry door, switch, crates, sealed exit (high on the right wall); AXEL walks in | footsteps |
| s2_notice (medium close, upper body) | 1.75–2.85 | Stops, glances, **double take** at the switch, eyes widen, hand to chin | `notice` 2.30 |
| s3_approach (follow) | 2.85–6.40 | **Cautious approach**: crouched, hands raised, shorter steps, eyes on the switch | footsteps |
| s4_insert (switch insert) | 6.40–8.00 | **Hesitant press**: reach, doubt (pull back, hand to chin), commit; the hand visibly lands on the dome; red alarm; startle | `press_contact` 7.492, `switch_activated` |
| s5_shift (wide tracking, shake) | 8.00–9.75 | Gravity swings to the right wall; loses support, flails, **braces**, lands feet-first on the wall | `gravity_shift` 8.392, `lost_support` 8.529, `brace` 9.008, `impact` 9.392 (1341 u/s) |
| s6_recover (follow, gravity-aligned roll) | 9.75–14.0 | The camera **rolls 0→90°** so the wall becomes the floor. Recovers, looks around, **notices the exit**, **points** at it | `recovered` 9.842, `notice` 11.296, `point` 11.996 |

**Implementation.**
- **Acting.**
  - `motion/animator.py`, `motion/controller.py`:
    - `notice`/`look_at` actions with a scripted double take: eye opening, a stretch, the hand rising to the chin.
    - `_gaze()` aims the neck and head at any target (`switch:<id>`, `exit:<id>`, `point:x,y`) and turns the head when the target is behind.
    - A `cautious` locomotion style.
    - A hesitant press clip (`hesitate: true`, contact at 1.55 s instead of 0.95 s).
    - A `point` action with auto-turn.
    - Torso and hip twist (`Pose.twist`, shoulder/hip offsets in the rig).
    - Idle weight shift.
    - A lagged spring follow-through on arms, chest and head driven by root acceleration.
    - Flail twist and gaze toward the predicted impact point while airborne.
- **Secondary motion** (`motion/secondary.py`):
  - `ScarfSim` is a two-tail verlet rope at 240 Hz, anchored to the neck, pushed by the live gravity vector and clamped to the room.
  - `DustField` is 170 particles at 60 Hz that fall along gravity and get impulses from impacts and the switch.
- **Camera** (`camera/director.py`):
  - Shot kinds; framing by focus region (body, upper body, head).
  - `align_gravity` roll, which springs from the authored roll to the gravity-down angle, wraps to (−180, 180] and turns the short way.
  - Event-driven noise shake.
  - An **exact roll-aware framing guard**: the subject's corners are projected into rolled screen space; the view widens or shifts by the minimum needed.
- **Renderer.** Exit door with red seal bars, volumetric light shafts, depth-sorted dust streaks, Chaikin-smoothed scarf ribbons, and a soft back-wall shadow.
- **Audio.** Adaptive synthesized music (calm, then tension from the press, resolving at `point`); notice, startle and chime cues; a rising hum between switch and shift.
- **Schema.** `ExitSpec`; actions `look_at`/`notice`/`point`; `target`, `style`, `hesitate`; camera `roll_end`, `roll_mode`, `focus`, `shake`; shot `kind`. Target references are validated.
- **Review tooling** (`qa/media.py`, `apex render --review-dir`): a full-decode check, a timestamped contact sheet every 0.5 s (labelled with shot, state and gravity), per-frame diagnostics JSON and a chart.

**Evidence.**
- `APEX_1C_gravity_switch_cinematic_1080p.mp4`: 1920×1080, 24 fps, 336 frames, 14.000 s, H.264 + AAC, 3-sample motion blur.
- Contact sheet: `docs/media/gravity_switch_1c_contact_sheet.jpg`.
- Diagnostics: `docs/evidence/gravity_switch_1c_diagnostics.json` and chart `docs/media/gravity_switch_1c_diagnostics.jpg`.
- QA: `docs/evidence/gravity_switch_1c_qa.json`. Decode report: `docs/evidence/gravity_switch_1c_decode.json`.

**Technical results (QA of the 1080p render): 37/37 PASS.**

| Check | Result |
|---|---|
| Bone-length ratio | 0.935–1.116 (limit 1.13) |
| Planted-foot drift | 0.63 (limit 1.5) |
| Max joint speed | 2835 u/s at t = 8.000, the authored startle (limit 3200) |
| Surface penetration | 1.56 (limit 4) |
| Airborne acceleration vs gravity | 1.90° (limit 3°) |
| Subject in frame (shot-aware: focus region for close-ups, the switch for the insert) | **100 %** (was 93.5 % before the exact roll-aware guard) |
| Camera roll speed | max 106°/s (limit 150) |
| Roll vs gravity at end of s6 | 0.003° error |
| Gravity indicator vs physics | 0° |
| Screen-direction flips across cuts | 0 |
| Static layout | room, switch and exit are constants |
| Scarf | max segment stretch 1.258 (limit 1.35), anchor error 0, inside room |
| Dust | inside room |
| Exit conditions | 6/6 |
| Audio cues on event times | 19/19 |
| Frames | 336/336 |
| A/V duration difference | 0.000 s |
| Full decode | 336/336 frames, no decoder or audio errors |
| Deterministic replay | identical hash |

**Regression.** 1A (`motion_test`) and 1B (`gravity_switch_1b`) were re-inspected with the 1C code: both PASS, with metrics unchanged from the reports above.

**Defects found and fixed during 1C review.**
- **`wait_grounded` finished at once:** it ended before the fall even started, so `look_around` ran mid-air. It now waits while any gravity transition is pending, and loss of support re-queues it.
- **Close-ups framed the whole body:** the guard used the body box; it now uses the focus region.
- **Gravity roll was invisible:** the camera started already rolled. It now springs visibly from the authored roll.
- **Exit out of frame when pointed at:** fixed with the s6 offset and width.
- **Subject left frame mid-roll:** 22 frames at 10.0–10.9 s, from the approximate rolled-frame guard. Replaced by the exact screen-space guard (with unit tests at six roll angles).
- **`gravity_roll` not wrapped:** gravity to the left produced +270° instead of −90°, which would spin the camera the long way. Not visible in 1C, but it would have hit the 1D reversal. Fixed, tested, and the inspector compares angles modulo 360°.
- **Back-wall shadow read as a second figure:** perspective-shrunk to wall depth, it looked like a small dark stick figure standing on the switch in the insert shot. Found by eye on full-resolution frames, not by any numeric check. It's now drawn at the character's scale and heavily blurred.

### Artistic assessment (separate from numeric tests)

This is my review of the rendered video, frame by frame plus the contact sheet. It is not a substitute for the owner's review, and **1C is not marked as professional animation quality** until that review.

| Dimension | Assessment | Verdict |
|---|---|---|
| **Acting** | The double take, the cautious crouched approach, and doubt during the press (reach, retract, hand to chin, commit) all read as intent. Startle, flailing fall, feet-first brace and the look-around read clearly. The notice-exit / point beat is clear. Limits: there's no face, so emotion rests on posture and eye opening only; beats come from a procedural clip library, so timing is uniform rather than hand-tuned per shot; the startle rise (pelvis +22 u in about 0.08 s) is snappier than it should be. | Readable; below hand-keyed quality |
| **Action clarity** | Cause → effect is unambiguous: hand on the dome in the insert, red alarm, gravity sweep, fall toward the wall, impact ring. The fall is fast (0.86 s airborne) but readable with motion blur and the wide tracking framing. | Good |
| **Camera staging** | Wide → medium close → follow → insert → wide tracking → rolled follow is a conventional, legible grammar. Cuts land on action (the notice, the contact, the shift). Weak points: in the establishing shot AXEL is small (about 16 % of frame height) and at the far left, and the switch's red light is the only pull toward the story object; in the last 2 s of s6 AXEL sits near the left edge with a lot of empty frame. | Good, with composition notes |
| **Continuity** | The room never moves. The roll is motivated (gravity) and shown on screen rather than cut. The gravity indicator always matches physics. Screen direction holds across all 5 cuts. The exit door is visible both before (s1) and after (s6) the shift, so the viewer can relocate it. | Good |
| **Emotional readability** | Curiosity → caution → doubt → shock → recovery → discovery reads without narration; the music arc supports it. "Relief" after landing is the weakest beat: there's no breath or settle, it goes straight into look-around. | Readable |

### Remaining defects and limitations (1C)

1. No facial features beyond a visor and eye opening. Emotional range is limited to body language.
2. The startle rise is too fast (it's the 2835 u/s max joint speed); it should be eased over about 0.15 s.
3. No breath or settle beat after landing; relief is under-played.
4. The establishing shot could use a slow push-in, or a briefer hold, to give AXEL more presence.
5. Late s6 composition: AXEL is close to the left edge. Within the safe area, but unbalanced.
6. The scarf rope has no bending stiffness. Tip speed peaks at about 2.2k u/s during the startle and fall; ribbon smoothing hides kinks, but very fast whips can look rubbery.
7. Press contact timing is still authored (`PRESS_H_CONTACT_T`), not solved from hand-to-button collision. Limbs don't collide individually (single capsule).
8. The back-wall shadow is a screen-space drop shadow, not a projected light shadow. There is no depth of field.
9. Music and SFX are procedural synthesis: functional and in sync, not production audio.
10. Skia "Default font" deprecation warnings appear in the review-sheet code (cosmetic).

---

## Also delivered ahead of plan (foundations only)

- **AI Story Director** (`ai/director.py`). Provider-agnostic. The model must return schema-valid JSON, which is then dry-run simulated. Validation errors are fed back for up to two repair attempts. Tested with a fake provider. **No live LLM call was made** in this environment (no API key configured).
- **Offline TemplatePlanner.** Rule-based, clearly labelled as not AI. It retimes shots from a dry-run simulation. Proven end-to-end: "Nova sprints … gravity swings to the left wall" plans, simulates, renders and passes QA (`docs/evidence/planned_nova_qa.json`). QA found two planner bugs here (shots not matching the simulation; a dropped final frame from non-frame-aligned durations), both fixed and covered by regression tests.
- **FastAPI backend** with SQLite storage, scene-level render jobs, progress and error capture, and video download. Tested end-to-end with `TestClient`.

## Test results

`pytest -v`: **66 passed**, 0 failed, in about 60 s (Python 3.13, Linux). This is 39 from 1A/1B plus 27 new in `tests/test_cinematic_1c.py`. Full list in `docs/evidence/pytest_results.txt`.

## Next milestone (1D)

Prepared but not started: see `docs/MILESTONE_1D_PLAN.md`. Per the assignment's sequencing rule, it begins only after the 1C review sequence is signed off. The 30 s milestone will not be declared complete without a delivered and reviewed render.
