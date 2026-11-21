# Milestone status report

All numbers below come from actual runs. Raw evidence is in `docs/evidence/`: `pytest_results.txt`, `*_qa.json` and `ffprobe_demos.txt`.

| Milestone | Status |
|---|---|
| 1A Rig and motion | **Done**, verified |
| 1B Physical interaction | **Done**, verified |
| 1C Character acting + cinematic direction | **Accepted** by the owner as a technically validated foundation. Startle and recovery fixed in 1D |
| 1D Full 30 s Gravity Switch | **Accepted by the owner as a technically validated milestone.** Revision 1 (owner's Part A review: swing staging, rail visibility, acting, impact weight, ending, QA count) rendered as v2: 58/58 QA checks, 97/97 tests, full decode. Artistic quality: improved, awaiting owner review; not claimed as professional. |
| Professional quality upgrade (Tasks 1–6) | **Implemented and rendered; awaiting human review.** Motion library with contacts, 5 s original-vs-improved motion test, swing restaged without roll plus composition rules, renderer adapter, themes and audio polish, human review rubric, and the generalization scene (PIP / Foundry Flip). Report: `docs/QUALITY_UPGRADE.md`. No quality level is claimed. |
| The Rescue (two-character physical interaction) | **Rendered (1080p, 20 s); QA 58 PASS / 2 SKIP / 1 WARN.** New general interaction layer: bounded-force push, lift and lever; straps; pinning; crawl; helped get-up; gestures; `wait_for`. The film is **hand-authored**: the real OpenRouter AI Director runs are preserved, and none produced a plan that plays the whole story (`docs/RESCUE_REPORT.md` §5). No quality level claimed. |

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

## Milestone 1D: the 30-second Gravity Switch story

**Owner's brief.**
1. Fix the abrupt startle, the post-landing recovery and the framing.
2. Retime the opening.
3. Implement `duck_slide`, `jump_to`, `grab_swing`, `reach_exit` and the door state machine.
4. Clarify gravity angles: relative to the preceding state vs the original.
5. Keep the hands on the rail; make releases, landings and contacts coherent.
6. Keep 1A–1C passing.
7. Render 30 s at 1080p/24 with sound.
8. Deliver a contact sheet, QA, an artistic assessment and a defect list.

The full story, the deviations from the plan, and why each one was made are in `docs/MILESTONE_1D_PLAN.md`.

**Evidence.**
- `APEX_1D_gravity_switch_escape_30s_1080p.mp4`: 1920×1080, 24 fps, 720 frames, 30.000 s, H.264 + AAC, 3-sample motion blur. Full decode 720/720, no decoder or audio errors (`docs/evidence/gravity_switch_1d_decode.json`).
- Contact sheet every 0.5 s: `docs/media/gravity_switch_1d_contact_sheet.jpg`.
- Diagnostics: `docs/evidence/gravity_switch_1d_diagnostics.json`, chart `docs/media/gravity_switch_1d_diagnostics.jpg`.
- QA: `docs/evidence/gravity_switch_1d_qa.json`.

### Fixes requested after the 1C review

| Item | Before | After |
|---|---|---|
| Startle after the press | Pelvis +22 u in 0.08 s (~634 u/s peak root speed) | Eased over ~0.2 s; peak pelvis speed ~320 u/s (test `test_startle_is_eased`) |
| Post-landing recovery | The "settle" clip was replaced by the next action the same instant, so it **never played** (found while implementing 1D) | After any hard landing (> 900 u/s) a 1.15 s relief beat always plays: exhale slump, hands on knees (arm IK to the knees), blink, straighten up |
| Framing | AXEL small in the establishing shot; empty frame late in s6 | The establishing shot pushes in and shows every story object (switches, beam, rail, sealed door). The new POV inserts frame the door and the second switch. Every follow shot was re-offset. |

### Retiming of the 1C opening

| Beat | 1C | 1D | Change |
|---|---|---|---|
| Start walk | x = −560, 150 u/s | x = −520, 150 u/s | −0.27 s |
| Notice (double take) | 2.30 | 2.03 | — |
| Cautious approach | 90 u/s | 105 u/s | −0.5 s |
| Press contact | 7.49 | 6.69 | −0.80 s |
| Wall landing | 9.39 | 8.59 | |
| look_around 0.9 s (filler) | yes | replaced by the relief beat (1.15 s, a real acting beat) | |
| Notice exit → point | 11.30 → 12.00 | 10.75 → 11.25 | |
| Final idle 1.0 s | yes | removed: straight into "spots the second switch" and the run | |

### Gravity angles: relative to the previous state vs the original

| State | When | World direction | vs previous | vs original | Camera roll |
|---|---|---|---|---|---|
| G0 | 0 s | −90° (down) | — | 0° | 0° |
| G1 | settles 7.84 s | 0° (right wall) | **+90°** (counter-clockwise) | +90° | 0 → +90° (s06, springs, ≤ 110°/s) |
| G2 | settles 19.25 s | 180° (left wall) | **−180°** (clockwise, back through the original "down") | **−90°** | +90 → −90° (s13, capped at 120°/s) |

- **Signed sweeps.** Each transition stores a signed sweep, so a 180° reversal has an explicit direction (`rotate_deg: -180`).
- **Unwrapped roll.** The camera follows the *unwrapped* angle, so it turns the same way as the physics.
- **QA coverage.** `gravity_angle_report` and `camera_roll_follows_gravity_direction` check both of these.
- **Consequence for the viewer.** Because G2 sweeps through the original "down", AXEL first slides toward the original floor and then falls across the room. Sweeping +180° would have thrown him into the ceiling.

### Technical results: 58/58 QA checks PASS on the 1080p render (corrected; first reported as 57)

40 engine and video checks plus 18 shot exit conditions. **Reconciliation:** the QA JSON (`docs/evidence/gravity_switch_1d_qa.json`) has 58 entries, all PASS: 40 engine and video checks plus 18 exit conditions. The earlier "57" came from counting log lines by hand and missing one. QA reports now compute and print their own totals (`QAReport.counts()`), and the documents quote those totals.

| Check | Result |
|---|---|
| Bone-length ratio | 0.929–1.098 (limit 1.13) |
| Planted-foot drift | 1.12 (limit 1.5) |
| Max joint speed | 3130 u/s at the catch (limit 3200) |
| Surface penetration | 3.8 (limit 4) |
| Airborne acceleration vs gravity | 2.2° (limit 3°), magnitude error 0.08 % |
| Landings | wall_right 1341 u/s, wall_right 644 (after the slap), wall_left 1524 (drop from the rail); all on supporting surfaces |
| Hand on the button at contact | 0.003 units (both presses, including mid-air) |
| Wrist-to-rail distance while hanging | 6e-14 (limit 1.5) |
| Swing energy not accounted for by pumping work | 0.77 % of peak kinetic energy (limit 2 %) |
| Beam clearance during the slide | 16.6 units (including a 2.5-unit limb margin) |
| Door state machine | sealed → switch 17.15 → unlock 19.25 → open 22.65 → exit 26.65 |
| Camera | subject in frame 100 %; roll ≤ 120°/s; aligned-roll error 1.0–1.5°; no screen-direction flips across 14 cuts |
| Scarf | max stretch 1.25, anchor error 0 |
| Audio | 45 cues, each at its engine event time; A/V difference 0.000 s |
| Frames | 720/720; full decode OK |
| Deterministic replay | identical hash |

**Regression.** 1A, 1B and 1C re-inspected with the 1D engine: all PASS. `pytest`: **88 passed** (66 earlier plus 22 in `tests/test_escape_1d.py`).

**Physics defects found and fixed while building 1D.** Each was found by QA or the event trace, not by eye.
- **Grip at the waist.** The grip pinned whatever body point was beside the bar (near the waist), so AXEL spun like a propeller (radius 26). The grip now requires the bar overhead at near-straight arms (radius ~95).
- **Catch fast enough to loop.** A head-first catch looped over the bar (1300 u/s). The catch is now feet-first and partly inelastic (arms absorb 45 %), and pumping is booked as muscular work.
- **Phantom ceiling landing.** Grazing the ceiling while gravity pointed at a wall was treated as a landing on the ceiling. Only surfaces that can support the body under the current gravity now count as landings (others emit `graze`).
- **Tumble into the end wall.** The tumble steered toward the gravity of that instant and swung the head into the end wall. It now orients toward the transition's end state, picks the free side, and waits until there is room (clearance gating).
- **Release into the ceiling.** Letting go mid-swing threw AXEL into the ceiling. He now dismounts at the top of the swing.
- **Hand through the end wall.** After the slap landing, a hand went through the end wall. Hands now brace on surfaces (limb–environment constraint).
- **Leg through the floor.** Blending slide → run dipped a leg through the floor. A ground clamp is applied after blending.
- **QA timing artifact.** Gravity-direction QA sampled gravity half a step late inside a 720°/s rotation (a 4.4° artifact). It now compares with the gravity actually applied.
- **Scarf jerk.** The scarf jerked to a 1.38 stretch at the 1420 u/s impact. A follow-the-leader length cap was added.

### Artistic assessment (separate from the numeric tests)

This is my review of the final 1080p render (the 0.5 s contact sheet plus full-resolution frames at the key beats). **It is not a substitute for the owner's review, and the film is not claimed to be professional animation quality.**

| Dimension | Assessment | Verdict |
|---|---|---|
| **Acting** | The 1C beats carry over (double take, caution, doubt, startle), and the eased startle now reads as a flinch rather than a pop. The new relief beat (hands on knees, exhale) is the clearest emotional moment after each fall. The looks are motivated: AXEL notices → POV → points → notices the second switch. Weak spots: still no face; the tense wait before the reversal is subtle; the pumping kicks are small; the "looks back at the rail" beat is easy to miss. | Readable; clearly below hand-keyed character animation |
| **Action clarity** | Each action has a visible cause and effect: the slide under a hazard-striped beam, the slap with a red flash, the fall "up" the screen after the reversal, the catch with a clank and spark, the drop, the door opening with light. The catch (19.65 s) is the least clear moment: the rail runs into the depth of the scene, so at the catch it reads as a glow at the hands rather than a bar. | Good, except the catch |
| **Camera staging** | 15 shots, with cuts on action and POV inserts that make the "where is the exit / how do I reach it" logic readable without words. The establishing shot shows every story object. Weaknesses: the 180° camera roll during the swing (s13) is motivated but disorienting, because the body appears sideways mid-roll; the reversal wide (s12) keeps AXEL small; the final hold on the empty doorway (~3 s) is long. | Good structure; s13 is the weakest shot |
| **Continuity** | The room never moves. Each gravity change is caused by a pressed switch, and the console arrows always match physics. Both camera turns follow the direction of the gravity rotation. The door is the same object throughout: high and sealed (G0/G1), unlocking at G2, then open. Screen direction reverses between G1 and G2; this is inherent to a 180° reversal and is shown by the roll rather than hidden by a cut. | Good |
| **Emotional readability** | Curiosity → caution → shock → relief → "there's the way out" → determination (sprint, slide, leap) → shock again → relief → hope (the door opens) → release (walks into the light, music resolves to D major). The arc reads without narration. Its weakest link is the reversal-to-catch stretch, where the camera motion competes with the action. | Readable |

### Remaining defects (1D): explicit list

1. **No face.** Emotion relies on posture, eye size and blinks only.
2. **The swing shot rolls 180°** while AXEL swings. It is motivated by gravity, but it is the most disorienting moment in the film. A cut, or a slower pre-roll, should be compared.
3. **The rail is drawn as a depth-spanning bar.** At the catch the camera sees it end-on, so the grab reads as a glow at the hands. It needs brackets or a different angle at the catch.
4. **Physics is still a single capsule.**
   - Hands bracing on walls and feet kept above the floor are pose-level constraints, not simulated contacts.
   - The rail is a grip anchor, not a collider.
5. **The catch and pumping are approximations.**
   - Arm absorption is a velocity scale (`CATCH_KEEP` 0.55).
   - Pumping is a centre-of-mass impulse, booked as work but not driven by leg torque.
   - Air control (tumble, brace, reaching for the bar) is cartoon angular steering.
6. **The landings are superhuman.** 1341 and 1524 u/s (roughly 7–8 m drops at 1 u ≈ 1 cm, with gravity at 1.6 g) are absorbed by a spring and the relief beat.
7. **The geometry is tuned to the simulation.** The rail's position was placed on AXEL's simulated fall path. Upstream timing changes can make him miss it; the engine then falls back to brace-and-land (`grab_missed`), but the story beat is lost.
8. **The ending holds ~3.3 s** on the empty glowing doorway, which is long. It could be tightened, or used for a final shot.
9. **The door sits on a surface seen edge-on** by the front camera. It reads from a distance or from the POV insert; at other angles it is a bright slit.
10. **The relief clip is identical after both hard landings.** There is no per-instance variation.
11. **Music and SFX are procedural synthesis.**
12. **Two scarf limits.** The scarf has no bending stiffness, and the follow-the-leader cap is a non-physical correction at impacts.
13. **Skia "Default font" deprecation warnings** in the review-sheet code (cosmetic).

**Per the owner's instruction, engine work stops here for review.** No further features are added until 1D has been reviewed.

---

## Milestone 1D revision 1: response to the owner's review

**Brief (Part A).**
1. Make the swing readable despite the 180° roll.
2. Make the rail visible at the catch.
3. Improve the acting (reactions, anticipation, landing recovery).
4. Give impacts more weight.
5. Shorten the final doorway hold and strengthen the ending.
6. Keep all tests passing.
7. Reconcile the QA count.

The engine was not rebuilt. Every change is an extension of the 1D code, plus a revised scene file. That file is now generated by a committed script (`examples/build_gravity_switch_1d.py`) so its tuning is reproducible.

**Deliverable.** `APEX_1D_v2_gravity_switch_escape_30s_1080p.mp4`: 1920×1080, 24 fps, 720 frames, 30.000 s, with sound. QA: **58/58 PASS** (39 engine/video checks plus 19 shot exit conditions, as computed by the report itself in `docs/evidence/gravity_switch_1d_v2_qa.json` → `counts`). Full decode 720/720, no errors. Contact sheet: `docs/media/gravity_switch_1d_v2_contact_sheet.jpg`. Before/after comparison: `docs/media/gravity_switch_1d_v1_vs_v2.jpg`.

### What changed, and how each change improved the animation

| # | Review problem | Change | Why it reads better | Verified by |
|---|---|---|---|---|
| 1 | The 180° camera roll during the swing hid the action | **The turn was moved out of the swing.** The reversal shot keeps the old orientation, so AXEL clearly falls "up" the screen, then tumbles and catches the rail. A new dangle shot (`s14_turn`, 1.9 s) turns the room around him while he hangs **still** (sine-eased, ≤ 149°/s). Pumping starts only after the turn is complete (`grab_swing.duration` = 1.85 s hang). The swing, release, drop and landing all play under a **fixed** camera with the pendulum hanging straight down. | The viewer only ever tracks one moving thing at a time: the room while AXEL is still, or AXEL while the room is still. | `test_camera_turn_happens_while_dangling_not_while_swinging` (roll change < 1° while pumping, releasing and dropping); QA `camera_roll_rate` 148.7°/s; `camera_roll_follows_gravity_direction` (now also covers eased-roll shots) |
| 2 | The rail read as a glow at the hands at the catch | **The rail is now an object, and it is introduced.** It is rendered as a steel tube with yellow grip bands, a bolted bracket on the back wall and an end cap at the front. A **POV insert** (`s12_rail_pov`) shows AXEL eyeing it before the reversal. The reversal and dangle shots are framed so the rail sits off-centre, where perspective draws it as a long bar. | The catch now pays off something the viewer was shown; at the moment of the catch the rail projects to a clear diagonal bar ending in his hands. | `test_rail_is_long_on_screen_at_the_catch` (> 90 px at 1080p from bracket to hands) |
| 3 | Acting | **Reversal "whoa":** when the floor starts tilting away, his arms fly out, knees give and eyes widen, before support is lost. **Catch:** his head snaps with the jolt; while dangling he looks down at the drop (wide eyes, small leg kicks), then at the door (determined), then pumps. **Relief beats vary:** their depth and duration scale with impact speed, and the second one adds a disbelieving head shake and panting. **Threshold look-back:** he stops in the doorway, turns his head and shoulders back to the room he escaped (toward the rail), then steps into the light. | Every big event gets a readable reaction, and the two reliefs are no longer identical. The film gets a character beat at the very end. | `test_reversal_reaction_before_losing_support`, `test_relief_beats_vary`, `test_threshold_look_back_holds_still` |
| 4 | Weight on impact | **Hard landings (> 1100 u/s) are three-point landings:** the near hand slams down ahead of the feet while the far arm stays thrown back. **Heavier spring:** lower frequency and more damping as impact speed rises, so he stays down longer and rises more slowly. **Squash is held longer** (depth unchanged to respect bone limits). The **head keeps travelling** into the impact. | Mass reads through *time spent compressed* and a body that has to catch itself with a hand. | `test_hard_landing_is_three_point`, `test_heavier_landing_recovers_more_slowly`; QA bone ratio 0.907–1.082, foot drift ≤ 1.24 |
| 5 | Ending | The empty-doorway hold (v1: 3.35 s after the exit) became an ending with an action: look back → step through → fade into the light → **the door closes behind him** (new `closing`/`closed` door states, `door_close` event and sound) → **fade to black** (`ShotSpec.fade_out` 0.9 s) on the resolving chord. AXEL exits at 28.44 s; the door shuts by 29.69 s. | The story closes visibly: the room seals again with him outside it. | `test_door_closes_behind_him`, `test_final_shot_fades_out`, QA `door_state_machine` |
| 6 | Preserve everything | 1A, 1B and 1C re-inspected: all pass (1B peak joint speed *dropped* from 2816 to 2596 u/s). | | `pytest`: **97 passed** (88 earlier plus 9 new) |
| 7 | 57 vs 58 QA checks | The 1D JSON has 58 entries (40 engine/video checks plus 18 exit conditions). "57" was a hand-counting error in the report. `QAReport` now computes totals itself (`counts()` in the JSON, printed in the summary line), and reports quote those numbers. | | `docs/evidence/gravity_switch_1d_v2_qa.json` → `counts` |

**Problems found and fixed during the revision (all caught by QA or the tests, not by eye).**
- **Squash slid the planted feet.** A longer, wider squash moved them 1.7–2.6 units, because horizontal squash scales about the pelvis. Landing squash is now nearly vertical, which removes a latent flaw.
- **Arms whipped through blends.** The landing far arm, and the bar-reach arm while falling, blended between angles about half a turn apart. The shortest-arc direction flipped mid-blend and produced 3,600–4,400 u/s spikes. The far arm now keeps its touchdown orientation, and the bar reach blends in **position** space before solving IK.
- **The authored roll eased too steeply.** The cubic in-out ease peaks at 3× the average rate (285°/s), so a sine ease was added.
- **The offline planner rounded durations.** It rounded scene durations to 6 decimals, so they were not exact frame multiples. This was exposed when landing timing changed, and fixed.

### Timeline, v1 → v2 (seconds)

| Beat | v1 | v2 |
|---|---|---|
| Slap on the second switch | 17.15 | 17.25 |
| Reversal begins | 18.75 | 19.10 |
| Catch | 19.65 | 20.00 |
| Camera turn | 19.75–21.4, during the swing | 20.05–21.95, while dangling |
| Pumping starts | ≈19.8 | 21.85 |
| Release (at the top of the swing) | 21.22 | 23.35 |
| Hard landing | 22.19 (1524 u/s) | 24.31 (1494 u/s), three-point |
| Door opens | 22.65 | 24.91 |
| Look-back in the doorway | — | 27.47 |
| Exit | 26.65 | 28.44 |
| Door closes | — | 29.19–29.69 |
| Hold after the exit | 3.35 s, empty doorway | 1.56 s: fade into the light, door closes, fade to black |

### Artistic assessment of v2 (separate from the numeric checks)

| Dimension | Change from v1 | Verdict |
|---|---|---|
| Acting | More reactive: "whoa", dangle fear → determination, two different reliefs, the look-back. Still no face, and the look-back is partly washed out by the doorway glare. | Improved; still below hand-keyed animation |
| Action clarity | The catch is now legible: the rail is introduced by the POV insert and drawn as a bar into his hands. The swing is no longer under a moving camera. | Improved |
| Camera staging | The 180° turn is isolated in its own shot. The swing shot keeps AXEL fairly small in a wide frame. | Improved |
| Continuity | The turn still follows the gravity direction. The rail and door are established before they matter. | Good |
| Emotional readability | The ending now resolves: a look back, the exit, the door shutting, a fade on the major chord. | Improved |

**Remaining defects.** See the 1D list above. Items 2, 3 and 8 are addressed by this revision. Still open:
- no face;
- single-capsule physics;
- approximations in the catch and pumping;
- superhuman landing speeds;
- geometry tuned to the simulation;
- the edge-on door;
- synthesized audio;
- scarf limits.

New in v2:
- The dangle adds 1.85 s in which AXEL mostly hangs still. It is intentional staging, but it slows the middle of the film.
- The swing shot frames AXEL small.
- The look-back reads mostly as a silhouette against the light.

---

## Also delivered ahead of plan (foundations only)

- **AI Story Director** (`ai/director.py`). Provider-agnostic. The model must return schema-valid JSON, which is then dry-run simulated. Validation errors are fed back for up to two repair attempts. Tested with a fake provider. **No live LLM call was made** in this environment (no API key configured).
- **Offline TemplatePlanner.** Rule-based, clearly labelled as not AI. It retimes shots from a dry-run simulation. Proven end-to-end: "Nova sprints … gravity swings to the left wall" plans, simulates, renders and passes QA (`docs/evidence/planned_nova_qa.json`). QA found two planner bugs here (shots not matching the simulation; a dropped final frame from non-frame-aligned durations), both fixed and covered by regression tests.
- **FastAPI backend** with SQLite storage, scene-level render jobs, progress and error capture, and video download. Tested end-to-end with `TestClient`.

## Test results

`pytest -v`: **128 passed**, 0 failed, in about 160 s (Python 3.13, Linux). That is 39 for 1A/1B, 27 for 1C, 31 for 1D, 21 for the quality upgrade and sound samples, and 10 for The Rescue (`tests/test_rescue.py`). Full list in `docs/evidence/pytest_results.txt`.

## Next step

Human review of The Rescue and the upgraded films with `docs/REVIEW_RUBRIC.md`: the 1D v3 film, the Foundry Flip generalization and the motion test. Then fix the open defects D4–D8 in `docs/QUALITY_UPGRADE.md`, in the order the review ranks them.
