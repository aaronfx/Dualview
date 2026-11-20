# Development roadmap

Status key: ✅ done · 🟡 partial · ⬜ not started

| Phase | Scope | Status |
|---|---|---|
| 1. Animation runtime | Scene graph/schema, skeleton, timeline evaluation, rendering | ✅ |
| 2. Motion intelligence | Locomotion ✅, IK ✅, gravity ✅, collisions ✅, impacts and recovery ✅, balance 🟡 (springs + support cone; no COM/support-polygon controller yet), climbing/rolling/push/pull ⬜ | 🟡 |
| 3. Cinematic production | Cameras ✅ (static/follow/track/dolly, shot kinds, gravity-aligned roll, shake, exact roll-aware framing), lighting and effects 🟡 (light shafts, dust, soft shadow; no depth of field), sound effects ✅, adaptive music 🟡 (synthesized), character acting 🟡 (gaze, notice, hesitation, point, follow-through; no face), secondary motion ✅ (scarf, dust), shot transitions 🟡 (cuts only) | 🟡 |
| 4. AI animation direction | Provider abstraction ✅, schema-validated planning with repair loop ✅, offline template ✅, rich story interpretation and multi-scene escalation ⬜ | 🟡 |
| 5. Advanced action | Multi-character, interaction constraints, fight choreography (attacker/target/contact timing/momentum transfer), acrobatics, weapons | ⬜ |
| 6. Long-form production | Cross-scene continuity, reusable assets, chapter rendering, job recovery/resume | ⬜ |
| 7. Professional application | React/TypeScript dashboard, visual editor, previews, asset library | ⬜ |
| 8. Quality improvement | Scene diagnostics ✅ (per-frame JSON and chart), contact sheets ✅, full-decode check ✅, continuity checks ✅; image-space checks, controlled regeneration, comparative evaluation ⬜ | 🟡 |

## Immediate next steps (Milestone 1D)

The scarf, `point`, the insert/close-up presets, roll transitions and music were delivered in 1C. What remains for 1D is in `docs/MILESTONE_1D_PLAN.md`:
1. Actions `duck_slide`, `jump_to` (with an airborne press), `grab_swing`, `reach_exit`.
2. Door state machine (sealed → open), crate in the path, slide clearance.
3. A second (180°) gravity reversal with a continuity-preserving camera roll.
4. Author the 30 s story, render, run QA, and write a separate artistic review. Start only after the 1C review sign-off.

## Fighting system (Phase 5) — design notes, not implemented

Each `CombatAction` will declare: attacker, target, preparation pose, contact effector and target body region, contact time window, a reaction clip chosen by impulse, momentum transfer (impulse applied to the target's physics root), recovery, camera emphasis and a sound cue. Contact must be verified geometrically: an effector capsule must intersect the target capsule within the window. Inter-character penetration will be prevented by per-limb capsules in the physics layer. **This document doesn't claim the feature exists.**

## Production hardening

- PostgreSQL `Repository` implementation and migrations.
- Job queue with retries and resumable chunked rendering (render frame ranges, concatenate).
- GPU or 3D rendering backend behind the same `FrameState` interface (Skia stays the reference).
