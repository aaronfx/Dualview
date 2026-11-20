# Professional quality upgrade: report

**Scope:** the six tasks in the owner's "Professional Quality Upgrade" brief. The reference films (*Animation vs. Math*, *Animation vs. Geometry Dash*, *The Dark Age*) were studied for principles only:

- readable silhouettes;
- weight carried through anticipation, impact and recovery;
- a camera that keeps the viewer oriented;
- environments with a distinct look.

None of their characters, sequences or designs is reproduced.

**This report does not claim professional (9/10) quality.** Passing technical checks proves that the animation is valid, not that it is good. A quality score has to come from human reviewers using `docs/REVIEW_RUBRIC.md`. Section 7 gives my visual evaluation with its limits stated.

## 1. Deliverables

| Deliverable | Where |
|---|---|
| Original-vs-improved motion comparison (5 s, 1080p): both versions side by side, pose timeline, contact bars, pelvis-height and speed curves | `APEX_motion_test_landing_1080p.mp4` (delivered with this report); tool `scripts/motion_test.py` |
| Full 30 s film, rerendered with the upgrade (1080p) | `APEX_1D_v3_gravity_switch_escape_30s_1080p.mp4` |
| Generalization sequence: new character and new environment (1080p) | `APEX_T6_foundry_flip_generalization_1080p.mp4` |
| Test results | Section 8; `docs/evidence/pytest_results.txt` |
| Character-motion diagnostics | Motion-test `diag.json`; render `--review-dir` diagnostics JSON and chart; QA JSON files in `docs/evidence/` |
| Visual evaluation | Section 7 |
| Defect report | Section 6 |
| Quality-improvement table | Section 5 |
| Human review rubric and packet | `docs/REVIEW_RUBRIC.md`, `apex review` |
| Renderer evaluation | `docs/RENDERER_EVALUATION.md` |

## 2. Task 1: character performance system

### Motion library (`src/apex/motion/library.py`, `src/apex/motion/clips/*.json`)

Performances are no longer hard-coded tracks in the animator. They are **editable JSON clips** made of named key poses: for example contact → impact → impact_hold → absorb → push_off → rise → hands_on_knees.

**Channels.** They are relative to the rig, so the same clip plays on AXEL and on PIP, whose legs are 0.8× as long:

- `crouch` and `shift`, as fractions of the standing pelvis height;
- `lean`, `chest`, `head`, `twist`, `hip_twist`;
- the arm swing and elbow flexion for each arm;
- the free-leg offsets;
- `eye`, `squash`, `gaze`.

**Interpolation, chosen per key:**

- `smooth`: a monotone Fritsch–Carlson cubic, so there is no overshoot between keys;
- `ease`;
- `snap`: fast start, long settle, used for the action after an anticipation;
- `slow_in`: used for falling into a pose;
- `back`: overshoot, then settle, for follow-through;
- `linear` and `hold`.

**Phases** (`anticipation`, `impact`, `absorb`, `follow_through`, `settle`, …) mark parts of a clip that a performer can exaggerate or soften.

**Contacts** declare where an effector must touch during a window. Two examples:

- the near hand planted on the surface in a hard landing (`s 0.62, h 0.03, 0.05–0.7 s`);
- both hands on the knees while catching breath (`on: joint:knee_n`, slid toward the hip).

**Customisation.** An animator or the AI Director requests a clip by name, with a `Performance`:

- `tempo`;
- `intensity` (scales every spatial channel's deviation from neutral);
- `mirror` (swaps the leading limbs);
- `emotion`: `neutral`, `afraid`, `determined`, `relieved`, `tired`, `excited` or `curious`. Each adds channel offsets and scales timing and amplitude.

### Clips authored

| Clip | Use |
|---|---|
| `lose_balance` | Arms thrown out and torso pitching as support goes |
| `fall_flail` | Looping airborne flail, played `afraid` |
| `brace` | Feet toward the surface before impact |
| `land_hard` | Above 1100 u/s: three-point compact impact, held absorb, push-off, rise, hands on knees |
| `land_medium` | Lighter landings. Intensity and tempo come from the impact speed |
| `recover_relief`, `recover_relief_shake` | Breath and head-shake variants |

### Weight and timing

- `landing_clip(approach)` picks the clip and its intensity from the impact speed.
- The controller's landing duration now equals the length of the performed clip, so physics time and acting time agree.
- Heavier landings last longer, crouch deeper and recover later.
- A balance-twist wobble rides on top.

### Contact-aware motion

- Contacts are enforced with IK after the pose is built. They blend in position space, which avoids angle flips across ±π.
- **New joint-level collision constraint:** a knee may touch a surface (kneeling) but may not pass through it. The pelvis rises by the deficit and the legs are re-solved; up to 4 iterations.
- Grabbing keeps the earlier hard grip constraint: the wrist is held exactly on the rail (`grip_attachment` error 5.7e-14).
- The hand reaching for the bar is solved in position space.

## 3. Task 2: five-second motion test (the weakest sequence)

The weakest sequence was the **first hard landing** (G1 wall impact, 1341 u/s). In v2 the character rebounded upright in about half a second. The impact had no weight.

`scripts/motion_test.py` exports both revisions of the engine over the same window, aligned on the impact event:

- the original from a git worktree at the pre-upgrade commit;
- the improved version from the working tree.

It then composes them into a 1080p comparison with:

- the state bands;
- the library key-pose ticks;
- the contact bars (feet and hands);
- the pelvis-height and root-speed curves;
- a playhead.

| Measure (same impact) | Original | Improved |
|---|---|---|
| Landing phase length | 0.55 s | 0.93 s (held absorb, push-off, rise) |
| Hand in contact with the surface | 0.04 s (incidental) | 0.46 s (planted, IK-held) |
| Lowest pelvis height | 42.0 | 39.5 (compact three-point) |
| Follow-through | none: upright, then idle | hands on knees, then a relief breath (`recover_relief`) |

It took four rounds of visual review, not just the numbers, to get here:

1. The hand plant read as cramped and the arm rose again after contact. The contact target moved to `s 0.62` and the window was extended to 0.7 s.
2. The far arm swung up after the impact. Its keys were settled.
3. The mechanics were hard to read in a world-fixed view. The test camera got a `--roll` option (90°).
4. A deep crouch at the 1D second landing pushed a knee 6 units through the wall. This led to the knee-clearance constraint.

## 4. Task 3: camera for action clarity

**Before.** The v2 swing rolled the camera 180° while AXEL dangled from the rail. Viewers lost track of which way was down, and the rail was off screen during the catch.

**Restaged (v3):**

- `s12_reestablish`: a world-fixed wide in the film's home orientation, showing AXEL on the right wall, the rail mid-room and the far wall.
- `s13_catch_swing`: a follow shot with **no roll**. `include: ["bar:rail"]` keeps the rail in frame through the catch, the dangle, the pumping and the release.
- `s14_drop_land`: no roll.
- `s15_relief_door`: **one** quarter-turn to the new gravity, while AXEL is still during the relief beat. `include: ["exit:door1"]` keeps the door in shot.
- The rail point-of-view insert and the dangle-turn shots were removed. The dangle (`hang`) went from 1.85 s to 1.0 s.

**Composition rules, enforced by the camera director and checked by QA:**

- `composition_subject_size`: a minimum on-screen subject size per shot kind (establishing 7 %, wide 12 %, tracking 16 %, medium 18 %, close 30 % of frame height). `min_subject_frac` overrides it.
- `composition_required_objects`: the `include` objects stay in frame (the margin boxes are unioned into the framing guard).
- `no_roll_during_fast_action`: no camera roll while the subject moves faster than 260 u/s.

The 1C film's s5/s6 cut moved from 9.75 s to 10.4 s so that its roll also starts after the landing.

## 5. Quality-improvement table

| Problem (from the owner's review or my own) | Fixed? | How | What remains |
|---|---|---|---|
| Landings rebound upright too fast; no weight | Yes | `land_hard` / `land_medium` clips scaled by impact speed: held absorb, push-off, hands on knees, relief breath; landing time tied to clip length | Two landing clips only. A side-on or rolling landing would need new clips |
| Contacts float (hands never touch, knees pass through surfaces) | Yes | Declared IK contacts; knee-clearance collision constraint | The elbows and the head have no collision constraint. Hands are only checked against room surfaces, not props |
| Confusing 180° roll during the swing; rail not visible at the catch | Yes | World-fixed restaging; `include` targets; roll only in the still relief beat | The re-establishing wide (0.95 s) is short. A first-time viewer may want more time there |
| Camera moves without motivation | Partly | QA rules for subject size, included objects and roll during fast action | The shot choice is still authored per scene. The rules check it but do not choose shots |
| The character dissolves against bright light (doorway) | Yes | Dark under-stroke silhouette (D7) | The open-door bloom still blows out to white for about 0.5 s as the door opens (1D, 24.0 s) |
| Fast limbs strobe at 24 fps | Partly | Motion trails (ghost limbs) plus 3-sample temporal blur | A velocity-buffer blur would be smoother |
| Impacts look thin | Yes | Burst effect (streaks, debris, glow), layered impact sound, panned stereo, room reverb | The sound is synthesised. No licensed library was available offline |
| Only one look; colours hard-coded | Yes | `EnvironmentSpec.theme` | The open-door light is not themed yet (it stays cyan) |
| No reusable performance system | Yes | Motion library with key poses, interpolation, phases, contacts and `Performance` | Locomotion and the press/point/notice acting are still procedural (in code), not clips |
| No way to judge quality beyond QA | Yes | `apex review`: objective metrics separate from the human rubric; AI text advisory only | No human scores have been recorded yet. That needs the owner and reviewers |
| Stance widths in AXEL's units (found by Task 6) | Yes | Scaled by leg length; AXEL unchanged | Other thresholds are still in world units (section 6) |

## 6. Defect report

| # | Defect | Severity | Status |
|---|---|---|---|
| D1 | The knee went 6 units into the wall at the 1D second landing (deep crouch from the scaled intensity) | High: visible penetration | **Fixed** (knee-clearance constraint); `surface_penetration` passes |
| D2 | The v2 shot plan failed the new composition rules: it rolled during the dangle and during the landing | High: disorienting | **Fixed** (restaged) |
| D3 | Landing plants hard-coded for AXEL's 86-unit leg; PIP's far foot could not reach its plant, so it drifted 1.51 units (QA limit 1.5) | Medium: foot sliding | **Fixed** (scaled by leg length) |
| D4 | An action interrupted by a gravity change resumes on the new surface in that surface's coordinates. A `walk_to` begun on the floor continued on the ceiling toward the mirrored target | Medium: wrong direction of travel | **Open**. Worked around in Foundry Flip by choreography (a held `look_at` instead of a walk). Fix: cancel or re-target surface-relative actions when the support frame changes |
| D5 | Switches must have a gravity effect: there is no plain lever or door switch | Low: limits stories | Open (schema) |
| D6 | The open-door light is cyan whatever the theme | Low: art direction | Open |
| D7 | In the exit shots the light character dissolves into the white doorway light during the look-back (found in the visual review of the first v3 render) | Medium: the final acting beat was unreadable | **Fixed**: a dark under-stroke beneath the figure. It cannot be seen against the dark rooms but keeps the silhouette against bright light. Both films were rerendered with it |
| D8 | Thresholds in world units tuned on AXEL: grab clearance 125 u, mid-air slap reach (shoulder-to-button), `KNEE_CLEARANCE` 2 u | Low: they worked for PIP (0.8× legs) but are not proportional | Open (architectural; see section 9) |
| D9 | The renderer Protocol has data members, so `issubclass(SkiaRenderer, Renderer)` raises a `TypeError` | Cosmetic | Use `isinstance`, as the tests do |

## 7. Visual evaluation (my review of the renders, not a quality score)

Method: I reviewed the timestamped contact sheets (every 0.5 s), stills at the key beats and the side-by-side motion test. These are frame reviews, not playback with sound at full speed, and I am not one of the human reviewers the rubric asks for. The notes below say what reads and what does not. They are not scores.

### Motion test (landing)

- **Reads:** the improved landing has a clear impact pose (three points: both feet and the near hand). The held absorb is visibly lower and longer than the original's. The push-off has a readable line of action. The hands-on-knees breath tells you the fall hurt.
- **Does not read yet:** the head is the same circle throughout, so the "relief" depends on body language alone, with no face.

### 1D v3 (30 s)

- **Clearer than v2:**
  - The re-establishing wide (19.0–19.95 s) puts AXEL, the rail and the far wall in one frame before the fall.
  - Through the catch and swing (20.0–22.0 s) the rail stays beside his hands and the horizon stays put.
  - The quarter-turn happens only while he catches his breath (24.0–25.0 s).
  - The first relief beat (10.0 s) now shows hands on knees.
- **Still weak:**
  - AXEL is small in the establishing and re-establishing wides, by design but at the limit.
  - The open-door bloom blows out to white for about half a second (24.0 s).
  - The swing is short (one pump), so it reads as a quick catch-and-drop rather than a showpiece.
  - The acting between beats (walks, turns) is still procedural and uniform next to the library-driven falls and landings.
- Before the outline fix, the look-back in the doorway (26.5–27.5 s) was unreadable. With the under-stroke it now reads.

### Foundry Flip (generalization)

- **Reads:**
  - The amber theme makes it a different place.
  - PIP's proportions and quicker gait read as a different character.
  - The slide under the duct, the mid-air slap with the red alert flash, the world-fixed fall up to the ceiling and the turn-over during the relief all read.
- **Weaker:**
  - In the wide flip shot PIP is small during the fall.
  - The hatch light is cyan, not themed (D6).
  - The 180° turn passes through frames where the upright PIP appears horizontal. That is inherent to rotating the camera with gravity, and it is why the turn sits in the still beat.

### Overall

The weakest sequence improved clearly, and the camera now preserves orientation through the hardest part of the film. The films are still recognisably a procedural engine's output: there is no facial acting, the walk cycles are uniform and the sound is synthesised. I would not present them as reaching the reference films' level until human reviewers score them.

## 8. Test results

| Check | Result |
|---|---|
| `pytest -v` | **115 passed**, 0 failed (about 150 s). It includes 18 new tests in `tests/test_quality_upgrade.py`: library clips and interpolation, performance parameters, contacts, the knee constraint, composition rules, `include` framing, the renderer registry, motion trails, stereo panning, the review packet, the generalization story and its QA, stance scaling and theme defaults. The two 1D camera tests were rewritten for the v3 staging |
| 1D v3 film (30 s, 1080p, stereo) | QA **63/63 PASS** (43 engine/video checks plus 20 shot exit conditions; the new composition checks are included). Full decode: 720/720 frames |
| Foundry Flip (19.5 s, 1080p, stereo) | QA **51/51 PASS** (37 plus 14). Full decode: 468/468 frames |
| 1A, 1B and 1C scenes | QA passes without video, after the 1C s5/s6 cut moved to 10.4 s |
| Motion test (5 s, 1080p) | Composed from the event-aligned exports of the pre-upgrade engine (git worktree) and the improved one |

Evidence:

- `docs/evidence/`: `gravity_switch_1d_v3_{qa,decode,diagnostics}.json`, `foundry_flip_{qa,decode,diagnostics}.json`, `motion_test_landing_{original,improved}_diag.json`, `ffprobe_quality_upgrade.txt`, `pytest_results.txt`.
- `docs/media/`: contact sheets, diagnostics charts, the motion-test MP4 and frame sheet, and the outline-fix stills.
- `docs/review/`: unscored review packets for both films.

The motion-test MP4 was rendered before the outline fix (D7). It compares motion, and the outline does not change it in those dark frames.

## 9. Task 6: generalization (a new character, environment and sequence)

**Foundry Flip** (`examples/foundry_flip.json`, rebuilt by `examples/build_foundry_flip.py`) is about 19.5 s long.

**The character, PIP:**

- shorter legs (35 + 33, against AXEL's 44 + 42), a bigger head (30 against 24) and thinner arms;
- a faster cadence (1.22×), shorter stride and more lean and arm swing;
- no scarf;
- white and violet with a pink visor, against AXEL's yellow and cyan.

**The environment, a foundry:**

- a wide, low hall (1800 × 900, against the lab's 1200 × 1400);
- an amber and charcoal theme;
- a low duct to slide under, a wall-mounted lever and a sealed hatch high on the right wall.

**The sequence:**

1. PIP walks in, notices the hatch and points at it.
2. PIP spots the lever, sprints, slides under the duct and jumps to slap the lever mid-air.
3. Gravity flips **−180°**, sweeping through "left" so the arc carries PIP away from the wall.
4. PIP loses balance, falls up, braces and lands hard on the ceiling (1534 u/s).
5. The relief beat plays while the camera turns over. The hatch, now at PIP's feet, opens.
6. PIP walks to it, looks back and leaves. The hatch closes.

### What was reused unchanged

- every action (`walk_to`, `notice`, `point`, `run_to`, `duck_slide`, `look_at`, `jump_to` with the mid-air press, `wait_grounded`, `reach_exit`);
- the controller;
- the physics;
- the door state machine;
- all the motion-library clips (`lose_balance`, `fall_flail`, `brace`, `land_hard`, `recover_relief`);
- the camera modes and the composition rules;
- the QA inspector and the sound director.

QA: **45 checks pass** (one skip without audio).

### Capabilities that needed new code

| New code | Why | Size |
|---|---|---|
| `ThemeSpec` on `EnvironmentSpec`; the renderer reads its colours from it | The room colours were module constants, so a second environment could not have its own look | Schema 12 lines; renderer about 15 lines |
| `obstacle:<id>` target kind | A camera `include` could not name a beam | 3 lines |
| Stance widths scaled by leg length (D3) | Plants were authored in AXEL's units | 8 lines |

Everything else is data: about 120 lines of JSON-building script.

### Architectural limitations found (not fixed here)

1. **Actions are surface-relative and survive a change of support frame (D4).** After a gravity change the queue continues with targets in the new surface's coordinates. The choreography has to avoid moving actions that straddle a flip.
2. **Gravity is the only thing a switch can do (D5).** A plain door lever needs a schema change.
3. **Some controller thresholds are in world units (D8).** They held for a rig 0.8× AXEL's size. A much larger or smaller character would need them made proportional.
4. **Acting outside the library is procedural.** Locomotion and the press/point/notice acting are tuned by code and `CharacterStyle` scales, not by clips. A character with a very different personality, such as a heavy, slow brute, can only be pushed so far by those scales.

No extensive hard-coding was needed for the new sequence. The three code changes above are general fixes, not scene-specific hacks.

## 10. Status

All six tasks are implemented and rendered. What is still needed is human review: the rubric scores, with their spread, from the owner and at least one other reviewer. I am not claiming a quality level. The motion test shows a clear improvement in weight and contact on the weakest sequence. Whether the films as a whole reach the reference level is for that review to decide.
