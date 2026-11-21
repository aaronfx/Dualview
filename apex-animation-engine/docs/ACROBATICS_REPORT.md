# Milestone 2: acrobatics and symbols as physical objects

Toward the benchmark film (a character fighting a symbolic world) and the 80/100 target. Design and audit: `docs/ACROBATICS_AUDIT.md`. Schema: `docs/SCENE_SCHEMA.md`, "Structures, acrobatics and symbols".

## What was built

| Capability | How it works | Where |
|---|---|---|
| Glyphs as geometry | 21 symbols (`+ - x ÷ = < > ! ? π √ 0-9`), each a set of strokes in a unit box. One definition drives physics (rounded segments), standable tops and rendering | `scene/glyphs.py` |
| Structures you can stand on | `platform` boxes, and fixed `glyph` symbols whose flat strokes are standable. Each top is a support surface **with ends**, so walking past an end steps off and drops under physics | `scene/structures.py`, `motion/frames.py` |
| No walking through structures | A walk into a structure is rejected in the dry run, naming the structure and suggesting `vault`, `climb` or `jump_to … onto` | `acrobatics._check_walk` |
| Jumps onto, off and between tops | `jump_to … onto`: the ballistic solution includes the height difference. It refuses a jump whose apex cannot clear the rise | `controller._takeoff_to` |
| Flips | `flip: front\|back` on `jump_to` and `wall_kick`. The physics body follows a planned somersault that completes at 80% of the flight; the animation tucks, with hands on the shins, then opens out to land | `acrobatics._flip_control`, `animator._eval_airborne` |
| Roll | Forward roll as a tucked ball, with the hips over the top when inverted. Directly after a jump it starts at touchdown (landing roll) | `acrobatics._roll_tick`, `acro_anim._eval_roll` |
| Vault | Over anything lower than 0.95 × body height: hand plant on the top, knees tucked over, landing | `_vault_tick`, `_eval_vault` |
| Ledge climb | Jump, hang from the edge with both hands locked on it, pull up (hips stay outside the end face), mantle a knee onto the top, stand | `_climb_tick`, `_eval_climb` |
| Wall kick | Run at a wall (a room wall or a structure's side), two steps up it, push off on a ballistic arc, optionally with a back flip | `_wall_kick_tick`, `_launch` |
| Flying kick | A strike move: a jumping lunge with contact near the top of the arc | `combat.MOVES["flying_kick"]`, `acro_anim._eval_flying_kick` |
| Glyph props | Dynamic compound bodies made from the glyph's strokes (mass spread along the strokes) | `physics/world.add_compound` |
| Pick up, carry | Light props only (mass × g ≤ 0.9 × strength). Both hands hold the glyph whatever the body does | `_pick_up_tick`, `acro_anim._hold_carried` |
| Throw | Wind-up, release on a ballistic arc at a character or a point. In flight, contact with a body is a **hit** (reaction from the momentum) or **blocked** (guarding and facing); a dodge can make it miss. Decided geometrically in the simulation | `_throw_tick`, `_thrown_tick` |
| Wield | `swing_weapon` while carrying: the prop follows a swing arc in the simulation, so contact happens at the prop, and the reach is the arm plus the prop | `combat._weapon_angle`, `acrobatics._hold_pose` |
| Rendering | Platforms are dark slabs with a glowing front edge. Glyphs are extruded, glowing strokes, split at the character plane so depth reads correctly | `render/skia_renderer.py` |
| Sound | Whoosh for flips, throws and the wall push-off; hand slap on a vault; clank on a ledge grab; footsteps on wall contacts; clang when a thrown glyph hits | `audio/sound_director.py` |
| QA | `body_outside_structures`, `feet_on_tops`, `flips_land_upright`. `strike_contact` now also measures thrown and wielded glyphs at the prop | `qa/inspector.check_acrobatics` |
| AI Director | The prompt documents the new actions, fields and events | `ai/director.py` |

**Engine corrections made along the way**
- A strike's whiff test used the move's full lunge even when the attacker had not yet covered it. It now measures from where the attacker actually is at contact. This changes nothing in *First Exchange* (verified: identical shot timings).
- `subject_in_frame` required *every* character to be visible in *every* shot. It now checks each following shot's own subjects: its target and any characters it explicitly includes.

## Test film: *Symbol Run* (original, hand-authored)

| | |
|---|---|
| Video | 720p draft (the building preset), 24 fps, 25.9 s, H.264 + AAC. Delivered separately; MP4s are not committed |
| Source | `examples/symbol_run.json` (built by `examples/build_symbol_run.py`) |
| Who wrote it | **Hand-authored choreography.** The engine decides the outcomes and the timing. No AI planning was used |
| QA | **50 PASS / 1 SKIP / 0 WARN** (`docs/evidence/symbol_run_qa.json`). The skip is `gravity_direction[rho]`: RHO is never airborne. Strike and throw contact 0 units at the prop; no body point inside a structure; the flip lands within 0.001 rad of upright. Audio and video durations match within 0.7 ms, and every frame decodes |
| Tests | **168 passed**, including 10 in `tests/test_acrobatics.py` |

**What happens in it, as decided by the simulation:**

| Time | Event |
|---|---|
| 1.7 s | KAI vaults a minus sign lying on the floor |
| 3.9 s | He grabs the end of the bar of a giant π |
| 5.3 s | He pulls up and stands on the bar |
| 6.7 s | He runs along it and front-flips off the end |
| 7.6 s | Landing roll |
| 9.5 s | He picks up a plus sign |
| 10.2 s | He throws it |
| 10.6 s | RHO **blocks** it, and the plus glances off and clatters to the floor |
| 12.2 s | RHO's flying kick |
| 12.6 s | It **whiffs**: KAI has stepped back |
| 14.9 s | KAI picks up a second minus sign |
| 16.8 s | He swings it like a staff: a **hit**, and RHO goes down (ragdoll) |
| 18.1 s | RHO settles on the floor |
| 19.6 s | RHO stands up |
| 20.3 s | KAI tosses the staff aside |
| 23.3 s | They bump fists |

Seven shots, each cut placed at a simulated event (`cut_on`).

**Evidence:**
- `docs/media/symbol_run_key_moments.jpg`
- `docs/media/symbol_run_contact_sheet.jpg`
- `docs/evidence/ffprobe_symbol_run.txt`
- `docs/evidence/symbol_run_decode.json`

## Acceptance: the owner's review and *Glyph Duel*

The review asked for five weaknesses to be fixed in the engine, and for one 30–45 s film that chains everything: fight, dodge with acrobatics, land, climb a symbolic structure, pick up a symbol, fight with it, and throw it at the opponent.

| Review concern | What changed in the engine | Evidence |
|---|---|---|
| **Kinematic movement:** an authoring error is not enough; nothing may pass through objects *in simulation* | Every step of grounded or landing motion goes through `_enforce_solid`, whatever caused it: walks, strike lunges, dodges, knockbacks, landing slides, rolls. The body stops at a structure's face, with a `bump` event. The dry-run error for walks stays as an early warning | `test_knockback_never_passes_through_a_structure` (a stagger into a slab stops at its face). QA `body_outside_structures` = 0 in both films |
| **Flips:** a planned rotation profile is not angular momentum | Flips are now **conservation of angular momentum**. At takeoff the legs give the body a momentum L, chosen so that, with the tuck it will make, it turns once by touchdown. In the air L is conserved: the spin rate is L / I(tuck), faster tucked (I = 0.4) and slower opening out. Nothing steers the angle. A contact that changes the spin changes L, and an early or late landing lands under- or over-rotated. The animation uses the same tuck curve | `test_flip_spin_follows_angular_momentum`: peak spin > 1.9× the takeoff spin, slower again before landing, total turn within 0.35 rad of 2π. QA `flips_land_upright` 0.035 rad |
| **Throws:** mass, velocity, direction and response must be consistent | Impact is an **impulse exchange** along the contact normal: J = (1+e)·m_prop·m_body/(m_prop+m_body)·v_n, with e = 0.35 and m_body 35 kg (struck part) or 70 kg (braced guard). J is applied to the prop at the contact point (rigid-body response with spin). The reaction is sized from J alone; `power` only sets the throw speed. Every hit records J, the normal, the masses and the prop's velocities before and after | `test_thrown_glyph_exchanges_momentum` (Δv·n = J/m, 0 < e < 1). New QA `throw_momentum` compares against the *tracked* motion: within 14% |
| **Landing transitions into combat** | A landing whose next action is combat (strike, guard, dodge) goes straight into the fighting stance after 0.2 s, with no relief beat. Rolls hand over directly. A roll now evades head and body strikes (rolled under), and an airborne body is never hit | `test_landing_goes_straight_into_combat` (`recovered` with `into=strike` < 0.35 s after touchdown). `test_rolling_under_a_strike`. In the film: `recovered into guard` twice |
| **Glyph edges** | Edge checks now run after *every* grounded step (walks, lunges, dodges, knockbacks), not only walks. Tops of real glyph strokes are tested at both ends | `test_glyph_tops_stand_and_step_off_both_ends` for `7`, `π`, `=` and `-`. `test_dodging_back_off_a_platform_edge_steps_off`. QA `feet_on_tops` |

**Fixes found while building the film**
- **Limbs in the floor:** a hand or elbow of a body lying face down could sink into the floor. Hands and elbows are now placed on the floor, and knees lifted, for every lying pose.
- **Framing check:** `subject_in_frame` now judges each following shot by its target and the characters it includes, rather than requiring every character in every shot.
- **Overlap check:** `fighters_do_not_overlap` no longer counts frames inside a roll, because the roll passes under the opponent by design. It reports how many frames it excluded: 26 in this film.

### *Glyph Duel* (original, hand-authored; the acceptance film)

| | |
|---|---|
| Video | 720p draft, 24 fps, **39.3 s**, H.264 + AAC (`docs/evidence/ffprobe_glyph_duel.txt`). Delivered separately; MP4s are not committed |
| Source | `examples/glyph_duel.json` (built by `examples/build_glyph_duel.py`) |
| QA | **51 PASS / 1 SKIP / 0 WARN** (`docs/evidence/glyph_duel_qa.json`): strike contact worst 19.4 (limit 24); throw momentum 14% (limit 25%); flips land within 0.035 rad of upright; no body inside a structure; fighters stay at least 67.7 apart outside the roll; both knockdowns settle; audio and video match within 0.3 ms; all 944 frames decode |
| Tests | **178 passed** (20 in `tests/test_acrobatics.py`) |

| Time | Event (decided by the simulation) |
|---|---|
| 3.9 s | KAI's jab is **blocked** |
| 4.8 s | RHO's roundhouse; KAI **back-flips** |
| 5.0 s | The roundhouse whiffs: KAI is airborne |
| 5.9 s | KAI lands **straight into his guard** |
| 7.4 s | RHO's cross; KAI **rolls under it** |
| 7.6 s | The cross whiffs; KAI comes out past RHO |
| 11.7 s | KAI grabs the ledge of the giant **π** |
| 13.1 s | He climbs onto it |
| 14.9 s | He **picks up** the times sign resting on the bar |
| 15.9 s | He **throws** it down at RHO |
| 16.6 s | Falling from the bar, it gathers speed: an impulse of 6,300 knocks RHO down (ragdoll) |
| 16.5 s | KAI **front-flips** off the bar. He throws before he jumps; the times sign lands just after the flip starts |
| 17.7 s | KAI lands in his guard |
| 20.6 s | RHO gets up |
| 21.5 s | KAI's **flying kick** is **blocked** |
| 22.5 s | RHO's counter-hook; KAI **ducks** it |
| 25.2 s | KAI **picks up** a minus sign |
| 27.0 s | First **staff swing**: RHO steps back, a whiff |
| 28.4 s | Second swing **lands** (stagger) |
| 29.4 s | KAI **throws** the staff: knockdown |
| 33.5 s | RHO gets up |
| 36.7 s | Fist bump |

Nine shots, each cut placed at a simulated event. One wide shot is static, framing both fighters while KAI is up on the π.

**Evidence:**
- `docs/media/glyph_duel_key_moments.jpg`
- `docs/media/glyph_duel_contact_sheet.jpg`
- `docs/evidence/glyph_duel_decode.json`

*Symbol Run* was re-simulated on the updated engine: `examples/symbol_run.json` is regenerated, and its acrobatics, combat and contact checks all pass (flip lands within 0.02 rad).

**Correction (owner's final review).** The *Rescue* container reversal is real. It was documented on PR #7 (branch `gpt-apex-prop-character-collisions`): a kinematic character drove a heavy container about 294 units backward. My acceptance note wrongly said no such defect was recorded; I had searched only this branch. The Milestone 2 structure fixes do **not** cover character-versus-dynamic-prop contact, so the issue stays tracked (`docs/CINEMATIC_REPORT.md`, Part 1).

The roll-through-body and held-prop issues from that review are fixed in Milestone 3's Part 1 (`docs/CINEMATIC_REPORT.md`).

## Known defects (honest list)

| # | Defect | Severity |
|---|---|---|
| A1 | **Standing on a moving glyph** is not supported. Only fixed glyphs and platforms can be stood on | Medium |
| A2 | **The wall kick is short:** two steps up the wall, not a sustained wall-run. It is not in the film; it is covered by `tests/test_acrobatics.py` | Low |
| A3 | **A held glyph is drawn mirrored** when the character faces left: the prop axis is flipped, so an asymmetric glyph such as a 7 would show back to front | Low |
| A4 | **Pauses while walking to props.** The approach walks to the staff and to RHO take about 1.5–2 s each. There is no automatic choreographer to tighten them | Low |
| A5 | *Flips fixed in acceptance: now conserved angular momentum.* **The roll is still a keyed rotation,** with approximate momentum through it. A flip's tuck is a moment-of-inertia curve on one rigid body, not a full-body simulation | Low |
| A8 | **Close exchanges still crowd the frame** in places: the jab at 3.9 s and the duck at 22.5 s (C1 from Milestone 1) | Medium |
| A9 | **A carried prop can pass through a structure** while held, because it is kinematic until it is thrown. Thrown props collide with everything | Low |
| A6 | **No hit-stop, slow motion or smears** (Milestone 3) | Medium |
| A7 | **Choreography is written by hand** (as in Milestone 1) | — |

**No quality level is claimed.** These are technical results, and the score in the roadmap is an estimate until a human reviews it.
