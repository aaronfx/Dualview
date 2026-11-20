# Development roadmap

Status key: ✅ done · 🟡 partial · ⬜ not started

| Phase | Scope | Status |
|---|---|---|
| 1. Animation runtime | Scene graph/schema, skeleton, timeline evaluation, rendering | ✅ |
| 2. Motion intelligence | Locomotion ✅, IK ✅, gravity ✅ (signed rotations), collisions ✅, impacts and recovery ✅ (with relief beat), slide ✅, aimed jump ✅, hanging/swinging on a rail ✅ (pivot joint, pumping), balance 🟡 (springs + support cone; no COM/support-polygon controller yet), climbing/rolling/push/pull ⬜ | 🟡 |
| 3. Cinematic production | Cameras ✅ (static/follow/track/dolly, shot kinds, gravity-aligned roll, shake, exact roll-aware framing), lighting and effects 🟡 (light shafts, dust, soft shadow; no depth of field), sound effects ✅, adaptive music 🟡 (synthesized), character acting 🟡 (gaze, notice, hesitation, point, follow-through; no face), secondary motion ✅ (scarf, dust), shot transitions 🟡 (cuts only) | 🟡 |
| 4. AI animation direction | Provider abstraction ✅, schema-validated planning with repair loop ✅, offline template ✅, rich story interpretation and multi-scene escalation ⬜ | 🟡 |
| 5. Advanced action | Multi-character, interaction constraints, fight choreography (attacker/target/contact timing/momentum transfer), acrobatics, weapons | ⬜ |
| 6. Long-form production | Cross-scene continuity, reusable assets, chapter rendering, job recovery/resume | ⬜ |
| 7. Professional application | React/TypeScript dashboard, visual editor, previews, asset library | ⬜ |
| 8. Quality improvement | Scene diagnostics ✅ (per-frame JSON and chart), contact sheets ✅, full-decode check ✅, continuity checks ✅; image-space checks, controlled regeneration, comparative evaluation ⬜ | 🟡 |

## Status after Milestone 1D

The 30 s Gravity Switch story is implemented and rendered (`docs/MILESTONE_1D_PLAN.md`). Per the owner's instruction, **no further engine features are added until 1D has been reviewed.** Candidate next steps, which depend on that review, are listed as remaining defects in `docs/MILESTONE_STATUS.md`. The main ones:
1. Facial expression (brows and mouth shapes).
2. Per-limb physics capsules, so that limb contacts are simulated rather than clamped in the pose.
3. Leg-driven (torque) pumping instead of a COM impulse.
4. Smoother staging of the 180° camera roll during the swing (or a cut alternative).

## Fighting system (Phase 5) — design notes, not implemented

Each `CombatAction` will declare: attacker, target, preparation pose, contact effector and target body region, contact time window, a reaction clip chosen by impulse, momentum transfer (impulse applied to the target's physics root), recovery, camera emphasis and a sound cue. Contact must be verified geometrically: an effector capsule must intersect the target capsule within the window. Inter-character penetration will be prevented by per-limb capsules in the physics layer. **This document doesn't claim the feature exists.**

## Production hardening

- PostgreSQL `Repository` implementation and migrations.
- Job queue with retries and resumable chunked rendering (render frame ranges, concatenate).
- GPU or 3D rendering backend behind the same `FrameState` interface (Skia stays the reference).
