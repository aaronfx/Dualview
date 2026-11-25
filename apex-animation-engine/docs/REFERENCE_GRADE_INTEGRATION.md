# APEX P1–P5 reference-grade integration + signed-term math correction

Branch `apex-reference-grade`, based on the package's audited base `apex-studio-edu-v2 @ f5b28cc`. Additive: all
upgrades are opt-in and legacy appearance/behaviour remains the default.

## What was integrated
1. **PR #13 native signed-term transposition** (pinned commits `39ecad5b`, `cedcf8dc`), cherry-picked cleanly.
2. **P1–P5 package** via the supplied `apply.py` (5 anchor patches + 17 payload modules): P1 ink character, P2
   performance helpers, P3 industrial-depth world, P4 continuity profile + visual-prop audit, P5 ensemble direction,
   and the `math_rehearsal` layer routing the example's `project()` through `rehearse()`.

## Defects found and fixed (root cause, with regression evidence)
- **Final grouped morph blocked (the 2 documented failures).** The original math staging left the actor overlapping
  the combined evaluation glyph, emitting a real `morph_blocked` event (~t=8.2s), so the final morph never completed.
  The rehearsal's bounded retreat variant (`clear_rhs_110_0.25`) moves the actor clear after the evaluation request;
  the native morph then completes. Dwell (≥1s) preserved, collisions untouched. `test_math_transposition.py` passes.
- **Sign-inversion morph pop (new render-QA defect).** `+2 → -2` fires while the actor carries the term. The morph
  kept the centre of mass fixed; because `+` is heavier than `-`, that translated the whole glyph ~12.8px to recentre,
  moving the digit and producing a pop at the swap (`morphs_no_pop` 13.28 > 6). Fix: a sign inversion keeps the glyph
  **origin** fixed (digit geometry preserved; only the sign flips in place), recording the expected COM displacement
  (`com_shift`) separately for the hold-centre check. Pop 13.28 → **0.46**. See `glyphs.is_sign_inversion`, the runtime
  morph swap, and `morphs_hold_centre`.

## Verification (native, this checkout)
- **Full native regression: 366 passed, 0 failures** (335 pre-existing baseline on `f5b28cc` + 31 from the package).
- Signed-term math acceptance: **6 × 1080p MP4** (x+2=5→3, x+4=9→5, x−4=9→13; legacy + ink styles), every frame
  decoded, **0 QA failures** across all six; proof JSON per case (SymPy-verified intermediate + result).
- The teaching sequence is the required one: pick up the complete signed term → sign inverts only on the native
  crossing → seat by the RHS and hold the readable intermediate (`x = 5 − 2`) ≥1s → a real point event requests
  evaluation → both operands merge and morph into the proven result. Nothing is thrown away.

## Known remaining deficiencies (honest; not artistic certification)
- **P5 `relay` (emergency extraction) does not yet produce a valid native plan.** `direct_ensemble` rejects every
  tactic: the barrier is 230u high (too high to vault, max 84), and the climb / crate-shift tactics are rejected by the
  native Inspector for `obstacle_clearance`. Reproduce: `python examples/build_reference_grade.py OUT --case relay`.
  The relay world geometry / tactic set needs tuning before this showcase renders. `combat` and `rescue` build cleanly.
- The math example uses a fixed 14s duration (idle tail after `x = 3`); event-derived trimming is a follow-up.
- **A numerical QA PASS is not artistic acceptance.** The 1080p MP4s are submitted for human visual review against the
  reference films before any reference-grade claim.
