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

## Known defects (honest list)

| # | Defect | Severity |
|---|---|---|
| A1 | **Standing on a moving glyph** is not supported. Only fixed glyphs and platforms can be stood on | Medium |
| A2 | **The wall kick is short:** two steps up the wall, not a sustained wall-run. It is not in the film; it is covered by `tests/test_acrobatics.py` | Low |
| A3 | **A held glyph is drawn mirrored** when the character faces left: the prop axis is flipped, so an asymmetric glyph such as a 7 would show back to front | Low |
| A4 | **Pauses while walking to props.** The approach walks to the staff and to RHO take about 1.5–2 s each. There is no automatic choreographer to tighten them | Low |
| A5 | **Flips and rolls are keyed rotations.** The somersault is physics-driven along a planned profile, not a full-body ragdoll simulation. Momentum through the roll is approximate | Low |
| A6 | **No hit-stop, slow motion or smears** (Milestone 3) | Medium |
| A7 | **Choreography is written by hand** (as in Milestone 1) | — |

**No quality level is claimed.** These are technical results, and the score in the roadmap is an estimate until a human reviews it.
