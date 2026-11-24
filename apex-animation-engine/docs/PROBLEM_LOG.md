# CORE RUN problem log

A permanent record of the engine defects found while making CORE RUN (the Director's Cut), each linked to its root
cause, the fix, the regression test that now guards it, and how it was verified. New problems are appended; nothing is
removed. "Benchmark" means the frozen film `examples/core_run_r4.json`, re-simulated by `apex.qa.benchmark` (see
`docs/QA_SYSTEMS.md`); the small isolated cases are in `tests/test_core_run_regressions.py`.

The point of this log is explainability: when a check fails, the engineer should be able to trace it to a known class of
problem and its fix, not rediscover it. Technical QA passing never implies the film is good — only that these specific
failures do not recur.

| # | Problem | Root cause | Fix (file) | Regression test | Verified |
|---|---------|-----------|-----------|-----------------|----------|
| 1 | The stolen core was left hanging in mid-air whenever the thief jumped between buildings | The carried prop was re-posed only while the carrier was grounded (`_carry_tick`); in the air nothing moved it | `_carry_free()` holds the prop body-relative through flight, swing and fall (`motion/controller.py`) | `test_carried_core_stays_in_hands_through_a_jump`; QA `carried_object_continuity` | Benchmark tower/canyon carry spans PASS; continuity worst < 60 u |
| 2 | At a scene-exit gate the core floated where the carrier vanished | A carried prop was never handed out of the level with its carrier; it stayed kinematic at the last hold pose | At the exit crossing, if carrying, `world.deactivate(pid)` + a `carried_out` event; `SimulationResult.carried_out`, `alive()` hides it (`motion/controller.py`, `scene/runtime.py`) | `test_carried_core_leaves_through_the_exit_and_is_gone`; QA `props_not_floating` | `carried_out` emitted, prop not `alive()` after; float check PASS |
| 3 | A thrown prop (the X) struck a character standing in a different depth lane | The thrown-prop vs body test ignored the depth lane | Lane gate in the body loop: skip when `abs(oc.z - self.z) >= BODY_PASS_Z` (`motion/acrobatics.py`) | Benchmark canyon `props_not_through_bodies` PASS; pairwise matrix `lane=split` rows | Canyon PASS; transitions `--pairwise` split-lane rows OK |
| 4 | A hand grab on a raised surface reached to the wrong height | The hand link point was measured from the room floor, not the surface stood on | `_link_point` uses `max(a.y - stand_h, b.y - o.stand_h)` (`motion/interaction_anim.py`) | Benchmark (helped get-up) + `test_milestone6`; QA `hands_meet` | `hands_meet` PASS on the benchmark |
| 5 | Helping a fallen character up, the helper's hand appeared behind the body | `offer_hand` approached from a fixed side; the grab fired before the hands met | Offer from the supine character's facing side; grab delayed to SIT*T+0.25 (`motion/interaction.py`, `combat.py`) | Benchmark arena helped get-up; QA `hands_meet` | arena PASS |
| 6 | A QA leg-strike target sat on the world floor (a ~751 u phantom miss) | The leg target height used world Y where it should have used the struck body point | Legs target `ry - (thigh+shin) + ankle_height + 8` (`motion/combat_anim.py`) | Benchmark `strike_contact`; `test_combat` | strike_contact within tolerance on the benchmark |
| 7 | Picking a prop off a waist-high holder, the crouch was computed from mixed coordinates | Pick-up height compared a frame-local height against a world height | Compare in frame height; stand at 0.74×stand_h, `dip` in segment data (`motion/acrobatics.py`, `acro_anim.py`) | Benchmark pick-up; `test_acrobatics` | benchmark pick-up PASS |
| 8 | A vault clipped the top with toes, knees or a hand | The vault arc did not keep the extremities above the surface | `_vault_clear` keeps feet, knees and hands above the top (`motion/acro_anim.py`); plant at y1+7 | Benchmark + transitions `vault > strike`; QA `obstacle_clearance` | clearance PASS on the benchmark |
| 9 | A disarm sent the staff through the disarmed fighter's body | The knocked-loose weapon's flight direction pointed into the body | Disarm flight `fly=(oc.facing*(160+…), 480+…)` away from the body; X dropped with a small spin (`motion/acrobatics.py`) | Benchmark arena disarm; QA `props_not_through_bodies` | arena PASS; `narrative_causality` links the disarm to its cause |
| 10 | A guard recoil slid the fighter's planted feet | The recoil was a root translation, not a step | Guard stun opens a stepping "hurt" block segment, then re-opens guard (`motion/combat.py`) | Benchmark `foot_sliding`; `test_combat` | foot_sliding PASS on the benchmark |
| 11 | A held prop was knocked loose but stayed glued to the falling carrier | On knockdown the carry was not released | Drop on knockdown via `_release_carry` (`motion/combat.py`) | `test_knockdown_drops_the_carried_core` | carry span ends on the knockdown |
| 12 | `place` left the core hovering above its holder | — (new capability; the rest position had to sit the prop on the surface) | `_place_rest` seats the prop just clear of the top (`motion/acrobatics.py`) | `test_place_seats_the_core_on_a_holder_not_floating`; QA `props_not_floating` | place event fires; float check PASS |
| 13 | Glass panes used a material the schema rejected | `material` had no `glass` value | `material: "glass"` added (`scene/schema.py`); glass drawing (`render/skia_renderer.py`) | `test_glass_material_accepted_by_schema` | schema validates |
| 14 | A strike at a prop was refused by the schema, though the engine supports it | The strike-target validation predated prop targets | `prop:` allowed as a strike target (not flying_kick/sweep/swing_weapon) (`scene/schema.py`) | `tests/test_combat.py::test_strike_schema` | schema test updated and passing |
| 15 | `last_retry` regressed when derived goals were checked in order | Derived goals are per-character waits in action-list order, not story order | `progress(goals, …, ordered=bool(sc.goals))` — derived goals unordered (`scene/goals.py`) | Benchmark `last_retry` | last_retry goals met, no regression |

## Non-defects (authoring guidance, recorded so they are not "fixed" again)

- **Thrown-prop lane placement.** Putting the X on lane z=40 or z=-48 to "stage" it either blocked VEX or caused a flip,
  because the lane then collided with a body. The prop belongs on z=0 where it is thrown along the fighters' plane. This
  is a staging choice the dry run already reports; it is not an engine bug. (A deterministic choreography stager — the
  next priority — should own this kind of placement instead of hand-tuning.)
- **Fragile choreography.** Small edits (lanes, throw origins, timing) cascade through the physics. Change one thing at a
  time and re-run the benchmark before QA. This fragility is the motivation for the choreography stager.

## How the benchmark is frozen

`examples/core_run_r4.json` is r4 verbatim and must never be re-choreographed — it is the reference. Its baseline in
`docs/evidence/regression_baseline.json` records its two **known** shortfalls (PELL's reach-exit actions in `city`, and
`exit_reached@pell` in `arena`), so they are reported as `known`, not as fresh regressions, while any *new* failure
still trips the benchmark.
