# Benchmark analysis: `Gravity_Switch_30s_FINAL_1080p.mp4`

The benchmark is the 30 s film produced earlier in this workstream: 1920×1080, 24 fps, 720 frames, H.264 + AAC.

It was made with a **one-off** procedural pipeline: a single JavaScript file that rendered in headless Chromium canvas, with per-scene hand-written keyframe sections. APEX re-architects that work into reusable, tested systems.

## What works and is preserved

- **Look:** a charcoal cutaway chamber with a cyan perspective grid, glossy floor, glowing red switch, and a yellow character with a cyan visor. Bloom and vignette. The cutaway framing makes wall-running legible. APEX reuses this visual language in `render/skia_renderer.py`.
- **Gravity readability:** the console arrow shows the gravity direction, a light sheet sweeps in the new direction, props and dust fall with gravity, and gravity never rotates the room. APEX keeps all of these, and makes gravity a physical vector the simulation actually uses.
- **Staging:** the switch press as an insert, wide shots for gravity changes, a camera roll so the wall reads as floor, and a hold on the empty doorway for the comic beat.
- **Event-synchronized sound:** each cue was placed from the animation's event list. APEX formalizes this as event bindings with a QA check.

## What needs improvement (and how APEX addresses it)

| Weakness in the benchmark | Cause | APEX approach |
|---|---|---|
| Falls, landings and the vault were keyframed paths (e.g. `x(t) = x0 + ½at²` written by hand) | No physics engine | pymunk rigid bodies under a gravity vector; landing is triggered by real contact events |
| Each scene's pose code was bespoke, not reusable | Monolithic file | Rig, gait, controller, animator and actions are library modules driven by data (`ProjectSpec`) |
| Foot sliding was checked by eye only | No measurement | Planted-interval declarations plus a QA foot-drift metric |
| Shot timings were hand-tuned to the animation | Animation and cuts not linked | Exit conditions and event-based cues; the planner retimes shots from simulation |
| No automated QA beyond ffprobe and black frames | – | 24+ numeric and structural checks per scene |
| Hard to regenerate one scene | Single global timeline | Scene-level runtime and render jobs |
| Scarf, panels, vault and door unique to that film | One-off code | Planned as reusable actions and props (Milestone 1D) |

## Reference films (creative benchmarks only)

*Animation vs. Math*, *Animation vs. Geometry Dash* and *The Dark Age (AvA 14)* set the bar for movement intelligence, choreography and long-form continuity. No characters, shots or assets are reproduced.

The gap from today's engine to that level is large. It lies mainly in:
- multi-character contact choreography (Phase 5);
- richer action vocabularies: acrobatics, climbing, combat;
- long-form continuity across scenes (Phase 6).
