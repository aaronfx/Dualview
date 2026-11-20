# Development roadmap

Status key: ✅ done · 🟡 partial · ⬜ not started

| Phase | Scope | Status |
|---|---|---|
| 1. Animation runtime | Scene graph/schema, skeleton, timeline evaluation, rendering | ✅ |
| 2. Motion intelligence | Locomotion ✅, IK ✅, gravity ✅, collisions ✅, impacts and recovery ✅, balance 🟡 (springs + support cone; no COM/support-polygon controller yet), climbing/rolling/push/pull ⬜ | 🟡 |
| 3. Cinematic production | Cameras ✅ (static/follow/track/dolly), lighting and effects 🟡, sound effects ✅, music ⬜, shot transitions 🟡 (cuts only) | 🟡 |
| 4. AI animation direction | Provider abstraction ✅, schema-validated planning with repair loop ✅, offline template ✅, rich story interpretation and multi-scene escalation ⬜ | 🟡 |
| 5. Advanced action | Multi-character, interaction constraints, fight choreography (attacker/target/contact timing/momentum transfer), acrobatics, weapons | ⬜ |
| 6. Long-form production | Cross-scene continuity, reusable assets, chapter rendering, job recovery/resume | ⬜ |
| 7. Professional application | React/TypeScript dashboard, visual editor, previews, asset library | ⬜ |
| 8. Quality improvement | Image-space checks, scene diagnostics, controlled regeneration, comparative evaluation | ⬜ |

## Immediate next steps (Milestone 1D)

1. Scarf and secondary-motion module (verlet chain bound to rig anchors, driven by the gravity field).
2. Actions: `point`, `duck_slide`, `grab_swing`, `reach_handle`, `vault`. Each action is defined by its preparation, contact and recovery phases plus its IK constraints.
3. Props: door (lock/unlock/open state), loose panels (pymunk), ledge (static grab target).
4. Camera: insert and close-up presets, roll transitions, depth staging.
5. Music layer with event-aware structure.
6. Author the full 30 s Gravity Switch story as a `ProjectSpec`; render; QA; compare with the benchmark.

## Fighting system (Phase 5) — design notes, not implemented

Each `CombatAction` will declare: attacker, target, preparation pose, contact effector and target body region, contact time window, a reaction clip chosen by impulse, momentum transfer (impulse applied to the target's physics root), recovery, camera emphasis and a sound cue. Contact must be verified geometrically: an effector capsule must intersect the target capsule within the window. Inter-character penetration will be prevented by per-limb capsules in the physics layer. **This document doesn't claim the feature exists.**

## Production hardening

- PostgreSQL `Repository` implementation and migrations.
- Job queue with retries and resumable chunked rendering (render frame ranges, concatenate).
- GPU or 3D rendering backend behind the same `FrameState` interface (Skia stays the reference).
