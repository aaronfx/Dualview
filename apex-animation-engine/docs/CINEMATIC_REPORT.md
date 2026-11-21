# Milestone 3: hit-stop, slow motion, smears, impact camera and screen effects

Combined with the Milestone 2 closure, as requested in the owner's final review of *Glyph Duel*. Test film: *Glyph Duel* (revised), `examples/glyph_duel.json`. Schema: `docs/SCENE_SCHEMA.md` (`time_fx`).

## Part 1: Milestone 2 closure (the owner's final review)

| Review item | Priority | What changed | Evidence |
|---|---|---|---|
| **7.5–8.1 s: the roll passes through the opponent's space; excluding 26 frames proves nothing** | High | The exemption is gone. **Depth lanes can now change over time:** an action can carry a `lane`, and the body moves in depth at 70 units/s. **The engine stops bodies in the same lane from passing through each other:** two standing bodies whose lanes are less than 28 apart (two half-depths) cannot pass, whatever moves them (walk, lunge, roll, knockback), and a `body_block` event marks it. A falling ragdoll collides with standing bodies in its lane. In the film, KAI rolls into the near lane (−50) and passes in **front** of RHO | QA **`body_clearance`**, geometry-aware with no exemptions: torso, head and legs as capsules with a depth extent; legs as thick as drawn. Deepest intersection over the whole film is **1.0** units (limit 3), with the bodies never intersecting during the roll. Tests: `test_bodies_in_the_same_lane_never_pass_through_each_other` (a same-lane roll stops at the body; a lane-changing roll passes in front) and `test_body_clearance_qa_proves_the_pass` |
| **25–29 s: carried weapons not protected against structures** | High, engine-level | A carried prop is posed only if the new pose is not inside a structure, tested against the exact geometry (glyph strokes as capsules, boxes as boxes), with resting contact allowed. A blocked swing **stops at the structure and cannot reach the target** (whiff, `prop_blocked`). Walking with a prop stops where the **prop** meets the structure, not just the body | QA **`held_props_outside_structures`**: **0.0** (2 carries). Tests: `test_a_carried_prop_is_stopped_by_a_structure` and `test_a_swing_into_a_structure_is_stopped_and_misses` (a beam over his head stops the raised staff; the swing misses) |
| **3.9 s and 22.5 s: crowding** | Medium | A **blocked strike now rebounds the attacker** off the guard. That opens the space after the blocked flying kick, which is what led to the crowded duck. The duck also sits back further (0.2 of body height instead of 0.12) | New readability check **`silhouettes_readable`**: the on-screen gap between two upright fighters' torsos and heads in the same depth plane, worst **19.1** units (limit 10). Frames where they are in separate lanes are counted and reported, not hidden |
| **The *Rescue* container reversal (PR #7)** | Tracked | **Not fixed.** On this branch standing characters do not collide with props at all (no reversal, but props ghost past standing bodies). The PR #7 branch made them collide as infinite-mass kinematic bodies, which caused the 294-unit reversal. A correct fix needs a **bounded-force body proxy** (a body that holds a prop with at most the character's strength). It stays open, as the review asked. Related: *The Rescue*'s opening walk passed JUNO *through* MILO, which the new body rule now stops. They are staged in separate depth lanes (MILO −14, JUNO +16), so she passes behind him | `docs/MILESTONE_STATUS.md` known issues; *The Rescue* still passes its QA test |
| 30–34 s: knockdown recovery looks mechanical | Low | Not addressed (deferred, as the review allowed) | — |

## Part 2: Milestone 3

| Capability | How it works | Where |
|---|---|---|
| **Film clock vs story clock** | The simulation is never changed. The film samples it through a monotonic **time warp**. `sim_at(film_t)` drives the picture; `film_at(story_t)` places sounds and effects | `render/timewarp.py` |
| **Hit-stop** | At each blow (`hit`, `block_hit`, `prop_hit`) story time holds for 3 frames × (0.6 + 0.6 × power), up to 6. Blocks hold half as long. One blow's several events count once | `build_warp` |
| **Slow motion** | Around a chosen beat (event syntax, e.g. `flip@kai[dir=back]`), story time runs at `rate` (0.1–1) with eased ramps. A low whoosh marks the slow-down | `TimeFxSpec.slowmo` |
| **Motion smears** | A fast limb segment leaves a tapered quad from where it was 1/48 s earlier, bright at the leading edge. Fast props (a thrown glyph) leave fading ghosts | `skia_renderer._smear`, `_prop_ghost` |
| **Impact camera** | In film time: the shake keeps going through a hit-stop. Heavy blows punch the camera in (up to −10% view height). Slow motion pushes in (−12%) | `pipeline.film_camera` |
| **Screen effects** | A 1–2 frame flash on heavy blows only. A chromatic split on the held impact frame. A vignette pulse on every blow. Radial speed lines in slow motion | `pipeline.screen_effects`, `chroma_split`, `skia_renderer._screen_fx` |
| **Effects on the film clock** | Impact stars, sparks, rings and swooshes keep animating while the frame holds, and stretch with slow motion | `pipeline.warp_effects` |
| **Sound** | Every cue sits at its event's film time, so audio stays in sync through every warp | `pipeline.warp_events` |
| **QA** | `time_warp_valid` (monotonic, covers the story); `hit_stop_frames` (every blow holds its frames); `flash_safety` (at most 3 bright flashes in any second); `slowmo_bounds`. Frame-count, duration and audio-sync checks use the film clock | `qa/inspector.check_time_fx` |

## *Glyph Duel* (revised): results

| | |
|---|---|
| Video | 720p draft, 24 fps. Story 38.8 s, **film 44.2 s** (five hit-stops, three slow-motion sections: the back flip, the front flip off the π, the final throw). H.264 + AAC |
| QA | **58 PASS / 1 SKIP / 0 WARN / 0 FAIL** (`docs/evidence/glyph_duel_m3_qa.json`). Body clearance 1.0 (limit 3, no exemptions); carried props in structures 0.0; readability gap 19.1 (limit 10); strike contact 19.4 (limit 24); throw momentum 14% (limit 25%); flips land within 0.035 rad; 5 hit-stops holding 16 frames; 1 bright flash in any second (limit 3); audio and video match within 0.1 ms; all frames decode. The skip is `gravity_direction[rho]` (RHO is never airborne) |
| Tests | **188 passed** (24 in `test_acrobatics.py`, 6 in `test_time_fx.py`) |

**Evidence:**
- `docs/media/glyph_duel_m3_key_moments.jpg`
- `docs/media/glyph_duel_m3_contact_sheet.jpg`
- `docs/evidence/glyph_duel_m3_qa.json`

## Revision 1: the owner's Milestone 3 review

| Review note | Change | Result |
|---|---|---|
| **Crowded jab (about 4 s) and duck (about 26 s)** | A strike can set the distance it engages from (`distance`). The jab now starts at the edge of reach (116, against 107) and is still stopped by the guard; the hook starts from 112. The duck sits back 0.3 of body height (was 0.2) | At contact, jab: pelvis gap 83 → **92**, torso gap 40 → **49**, head gap 32 → **40**. Duck: pelvis 106 → **119**, torso 47 → **59**, head 35 → **46** (world units). **Still close contact on screen:** a guarded jab and a hook passing over a ducked head are contact moves, and the tighter two-shots magnify them |
| **Depth changes must be visually obvious** | **Floor shadows at each character's own depth lane**, so a character in a nearer lane casts its shadow nearer. **Distance tinting:** the farther lane is drawn darker, the nearer one brighter. This adds to the existing perspective scale and draw order | During the roll in front, the nearer KAI is larger, brighter and lower on screen, with his shadow in front of RHO's |
| **The flash at about 32.8 s washes out the scene** | Peak brightness 0.4 → **0.26** (second frame 0.12). The flash is now **radial, centred on the blow**, fading toward the edges so the characters keep their detail. The QA count uses a lower "bright" threshold (0.2) | `flash_safety`: at most 1 bright flash in any second |
| **Camera direction: track flips, change scale deliberately, close-ups only when they help** | **Airborne tracking:** a follow camera tightens up to 2.6× while its subject is in the air. **Knockdown close-up:** on knockdown-class blows (the engine's own `knockdown` verdict), the camera closes in 30% during the hit-stop and re-centres on the blow. **Restaged shots:** 12 instead of 9, each scale chosen for a reason: wide to establish and for travel; medium two-shots for exchanges; close shots only for the pick-up of the symbol and the reconciliation | `subject_in_frame` 0.977. Tests: `test_knockdown_hold_closes_in_on_the_blow` and `test_strike_distance_engages_from_further_out` |
| *Rescue* container collision | Stays open (PR #7) | — |

**Revised film QA: 58 PASS / 1 SKIP / 0 WARN / 0 FAIL. 190 tests pass.**

Evidence:
- `docs/media/glyph_duel_m3r_key_moments.jpg`
- `docs/media/glyph_duel_m3_contact_sheet.jpg`
- `docs/evidence/glyph_duel_m3_qa.json`

## Engine corrections found while building it

- **Kicking leg in the clearance check:** the check counted the kicking leg as body. It is now treated like the arms (the weapon) during its own strike segment only.
- **Leg thickness:** the clearance check had legs too thick (5 units). They now use the drawn width (half the limb width).
- **Hand pop at a flip's start:** the hands could snap from overhead to the shins between two frames (a joint-angle blend; 3,300 units/s). They now travel in position space, and a flip drives the arms up-forward, not overhead. Peak joint speed in the film is 2,692 units/s (limit 3,200).
- **Ragdoll falling through a standing body:** a falling ragdoll passed through a standing body in the same lane. It now collides.

## Known limits

- **Crowding is improved, not solved.** After revision 1 the jab and the duck have 11–25% more space, but they still read as close contact (an arm over the opponent's guard or head). The readability check excludes a crouched body, so it does not cover the duck.

- **Smears are drawn, not simulated:** they show where a limb was 1/48 s earlier, not true motion-blur integration. The draft preset renders 1 sample per frame.
- **The chromatic split is uniform:** a channel offset across the whole frame, not a lens model.
- **No full-screen distortion:** there is no shockwave warp; the impact ring is drawn.
- **The character-versus-heavy-prop collision (PR #7) remains open** (see Part 1).
- **The knockdown recovery** still looks somewhat mechanical.

**No quality level is claimed.** These are technical results, and the score in the roadmap is an estimate until a human reviews it.
