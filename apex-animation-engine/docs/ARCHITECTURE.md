# APEX Architecture (v0.1)

## Design principles

1. **The animation logic is ours.** LLMs plan; the engine simulates, animates, directs, renders and verifies. No frame comes from a text-to-video service.
2. **Every frame is a pure function of time.** A fixed-step, deterministic simulation records physical state. The animator turns the records into poses, and `evaluate(t)` works for any t. This gives arbitrary-timestamp evaluation, deterministic re-rendering, scene-level regeneration, and QA sampling at any rate.
3. **Backends sit behind interfaces.** Physics (`PhysicsWorld`), rendering (`SkiaRenderer` consumes only `FrameState` and `CameraState`) and AI (`Provider`) are replaceable without touching motion code.
4. **Structured data everywhere.** Scene plans are validated `ProjectSpec` objects (pydantic). Cameras, sound and QA consume the same data.
5. **Verify, don't assume.** Every render can be inspected numerically: bones, contacts, gravity, sync, frames, determinism.

## Data flow

```
story text ──► AI Story Director ──► ProjectSpec (validated JSON; dry-run simulated before acceptance)
                 (Provider: OpenRouter/OpenAI/Anthropic, or the offline TemplatePlanner)
                                     │
                                     ▼
                 SceneRuntime.simulate()      fixed 240 Hz, deterministic
                   ├─ GravityField            vector + timed transitions (caused only by switch events)
                   ├─ PhysicsWorld (pymunk)   static room colliders, rigid props, character capsule
                   └─ CharacterController     state machine per character:
                         grounded (kinematic, on a GroundFrame) ─ actions: walk/run/turn/press/jump/look
                         airborne (dynamic body) ─ ray-cast impact prediction → brace (angular control)
                         landing  (kinematic) ─ spring-damped compression, balance wobble → recover
                       → segments + per-step records + events
                                     │
                                     ▼
                 Animator (per character)     pose_at(t): gait legs (planted IK), action keyframes,
                                              airborne flail/tuck/brace, landing compression; cross-blends
                                     │
                     ┌───────────────┼──────────────────┬──────────────────┐
                     ▼               ▼                  ▼                  ▼
              CameraDirector    SkiaRenderer       SoundDirector       Inspector (QA)
              (per-shot rigs,   (2.5D room,        (event-bound        (24+ numeric /
               frame guard)      characters, FX)    synthesized cues)   structural checks)
                     └───────────────┴─────► VideoWriter (FFmpeg pipe) ◄──┘
                                              → MP4 + QA JSON
```

## Key concepts

- **GroundFrame:** any support surface (floor, `wall_right`, `wall_left`, ceiling) defines `(s, h)` coordinates: distance along the surface and height above it. Locomotion, plants and IK are written once in `(s, h)` and work on every surface. That is how AXEL walks on a wall after gravity changes, without rotating the scene.
- **Segments:** controller states over time (`idle`, `loco`, `turn`, `press`, `airborne`, `landing`), carrying the data the animator needs, such as foot plants, gait, contact data and intent.
- **Events:** time-stamped facts (`footstep`, `press_contact`, `switch_activated`, `gravity_shift`, `lost_support`, `brace`, `impact`, `recovered`, `takeoff`, `prop_impact`). Sound cues, visual effects, exit conditions and QA all bind to events, never to guessed times.
- **Planted intervals:** the animator declares when and where each foot must be fixed. QA measures the actual evaluated ankle against that point.

## Motion intelligence implemented

| Principle | Mechanism |
|---|---|
| Anticipation | Press clip leans back and lifts the hand before reaching; jump prep crouches and swings the arms back; turns lead with the head |
| Weight and acceleration | Lean ∝ acceleration (forward when speeding up, back when braking); speed-dependent cadence, stride and pelvis height |
| Momentum | Speed is integrated with acceleration and braking limits; physics carries velocity through falls and jumps; tangential slide on landing decays |
| Balance | Loss of support when gravity leaves a 55° cone around the surface normal; tip-over torque from the tangential gravity component; post-landing wobble from a damped spring; settle steps put the feet back under the pelvis |
| Foot placement | Footfalls are planted world points; stance is centred under the pelvis; a reach constraint lowers the hips instead of dragging feet; toes are clamped above the surface |
| Joint constraints | Per-bone limits; IK stretch capped at 6–8 %; QA bone-length bounds |
| Impact and recovery | Approach speed drives compression depth (spring, ζ = 0.55); squash on impact; arms follow through; recovery when the spring settles |
| Arcs and secondary motion | Swing-foot arcs, arm swing, lagged follow-through (arms, chest, head), verlet scarf driven by gravity (`motion/secondary.py`), reactive dust |

## Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python ≥ 3.11 | AI orchestration, numerics and backend in one language |
| Schema | pydantic 2 | Strict validation, JSON Schema export for LLM prompting |
| Physics | pymunk (Chipmunk2D) behind `PhysicsWorld` | Mature, deterministic, MIT-licensed, Windows wheels; 2D matches the current side-view staging. A 3D backend (e.g. Bullet) would implement the same interface |
| Rendering | Skia CPU raster behind `render/` | Anti-aliased vectors, gradients, blur and blend modes; headless; no GPU needed; Windows/Linux/macOS wheels. EEVEE/Blender was evaluated earlier in this environment and failed headless (no GPU/EGL), and CPU Cycles is too slow for iteration |
| Encoding | FFmpeg over a pipe | Industry standard; no temporary PNGs |
| Backend | FastAPI + thread-pool jobs | Async API, OpenAPI docs, simple job progress |
| Storage | SQLite (dev) behind `Repository` | Zero setup locally. PostgreSQL is planned for production by implementing the same interface |
| Frontend | not yet built | Deliberately deferred until the runtime is validated (Phase 7) |

## Determinism

Fixed 240 Hz physics steps, no wall-clock inputs, seeded synthesis and pure evaluation. QA's `deterministic_replay` re-simulates and compares a SHA-256 of joint positions at 12 timestamps. `tests/test_runtime.py::test_deterministic_replay` does the same at 28 timestamps.

## Scene-level regeneration

Scenes are independent units: `render_scene(project, scene_id, ...)`, `POST /projects/{pid}/scenes/{sid}/render`. Editing one scene and re-rendering it never touches the others. Cross-scene continuity, such as carrying the end state into the next scene, is a Phase 6 item.
