# APEX Studio & EDU Foundation V2 — native integration

Status of integrating the `apex_extension` kit into the native APEX engine. The engine (schema, runtime, physics,
autochoreo, math_stage, character_brain) remains the physical and mathematical **authority**; the extension is an
additive adapter layer. Nothing native is overwritten. The AI Director may consume **only verified** capabilities
(`apex_extension.registry`).

Branch: `apex-studio-edu-v2` (based on `apex-math-balance` / PR #11). Install: `python install.py <engine> --apply`
copies `src/apex_extension/` only; rollback = delete that directory. Native file inventory (hashes) is recorded by the
same command.

## Principle: intelligence is independent of appearance
Character decisions come from perception and recorded outcomes, never from how the character is drawn:
- `apex_extension.character` (`Affect`, `Experience`, `native_brain` → `apex.ai.character_brain.CharacterBrain`) operates
  on reward/threat/observed outcomes.
- `apex_extension.rig` (`Rig.retarget`) maps **semantic** joint angles onto any role set, so the same intelligence drives
  a stick figure, an illustrated/cartoon rig, an animal or a future rendering backend (proven by
  `test_rig_is_appearance_independent`). Full IK, skinning and cartoon rendering are future adapters, not yet implemented.

## Capability registry (`apex_extension.registry`)
The single reconciled source of truth. `product_sdk.Capability` refuses `verified=True` without evidence.

| Capability | Verified | Native evidence |
|---|---|---|
| autonomous_choreography | ✅ | `autochoreo.search` (physics-verified tactic); `build_impossible_crossing.py` render; `test_autochoreo.py` |
| physical_math_symbols | ✅ | `math_stage.compile_math_stage`; `test_math_stage.py` |
| math_equation_transform | ✅ | `math_stage.plan_balance` + `compile_proven_math_pair` (SymPy-gated); `test_math_balance.py`; `build_balance_equation.py` render (PR #11) |
| fixed_glyph_morph | ✅ | `physics/world.reshape` morphs a fixed (kinematic) glyph upright; `test_apex_extension_native.py` |
| world_perception | ✅ | `apex_extension.world.from_project` vs `structures.obstacle_bounds`; `test_apex_extension_native.py` |
| character_memory | ✅ | `character.native_brain` → `CharacterBrain` (outcome memory); `test_apex_extension_native.py` |
| illustrated_rig_retarget | ⬜ | rig interface present; not proven on an illustrated backend |
| dialogue_srt, ensemble_scheduling, chart_visualization, lesson_release_gate, story_beat_validation, shot_audio_cues | ⬜ | kit interfaces present; native evidence pending |

## Module boundaries (reuse native, don't duplicate)
- **math_world** → `math_stage.plan_balance` / `compile_proven_math_pair`; exact `Fraction` arithmetic cross-checks the
  SymPy proof. Contact evidence must come from authenticated native runtime events, not the kit dictionary alone.
- **planning** → `autochoreo.search` (physics-verified); the kit's uniform-cost `plan()` proposes symbolic sequences
  only, each mapped to a native `ActionSpec` and verified through `SceneRuntime`. `autochoreo.search` is preserved.
- **world** → `structures.obstacle_bounds` for static bounds; dynamic positions/occlusion come from runtime frame state.
- **character** → `CharacterBrain`; wire only observed outcomes at decision boundaries (no per-frame LLM).
- **acting** → timing/pose-blend utilities for the motion controller; never blend world position across solid geometry.
- **quality** → bounded diagnostics/repair; connects to existing QA and reruns only on measured improvement.
- **rendering** → native `apex` CLI (validate + render); no alternate backend. Proven by an MP4 produced through
  `rendering.render_native` (`out/balance_via_extension.mp4`).
- **education / assessment / visualization** → EDU gates: a lesson releases only with reviewed, sourced, approved claims;
  charts preserve real data. Math/scientific accuracy, source traceability and expert review are required and are human
  evidence, not automated fact-checks.

## Verification run (this branch)
- `python -m unittest discover -s tests` in the kit: 18 isolated tests pass.
- Native: `pytest tests/test_apex_extension_native.py` — 10 pass (every bridge against the real engine).
- Native regression subset (schema, qa, math_stage, math_balance, autochoreo, character_brain): pass; additive install
  changes no native file.
- Rendering bridge: an MP4 produced via `rendering.render_native` (native `apex validate` + `render`).

## Not done / next
- Prove one identical action objective on a stick **and** an illustrated rig (the "Lost Companion" brief) → verify
  `illustrated_rig_retarget`.
- EDU briefs (Understanding Gravity, Journey of a Red Blood Cell, Liquidity Trap) with verified quantities, expert-reviewed
  claims and supplied chart data.
- 1080p renders of Equation Vault / Pulse Runner / CORE RUN with contact, continuity and independent artistic review.

No production-readiness claim is made from these tests. Each capability is verified in isolation against the native
engine; artistic quality and film certification require human review and are not inferred from unit tests.
