# APEX Animation Engine

A standalone, AI-directed procedural animation engine. It turns structured scene plans, which an LLM can generate from a story, into physically grounded stick-figure animation. It renders 1080p MP4s with synchronized sound and automatically checks every render for animation defects.

> **Status:** Milestones 1A–1D are complete; 1C and 1D were accepted by the owner as technically validated milestones. The 30-second Gravity Switch film has been revised after review (v2: restaged swing and camera turn, visible rail, more acting, heavier impacts, a new ending). Its artistic quality is awaiting the owner's review (see `docs/MILESTONE_STATUS.md`).

The engine is **independent of Creator Studio**. It has its own backend (FastAPI), storage (SQLite now, PostgreSQL planned), character system, physics layer, camera system, renderer, QA and export. The only shared concern is access to AI provider credentials, which are read from backend environment variables. Providers are interchangeable: OpenRouter, OpenAI, Anthropic, or any OpenAI-compatible endpoint.

## What works today (verified)

| Capability | Where | Evidence |
|---|---|---|
| Articulated stickman rig: 16 bones, hierarchical FK, joint limits | `src/apex/rig/` | `tests/test_rig.py` |
| Analytic two-bone IK: legs (knees forward), arms (elbows back), fingertip targeting | `rig/ik.py`, `rig/stickman.py` | IK reaches 200 random targets with error <1e-6 |
| Locomotion: walk, run and the blend between them, with planted feet, stance centred under the pelvis, pelvis bob, acceleration lean, arm counter-swing, settle steps after stopping | `motion/gait.py`, `motion/animator.py` | foot-slide QA ≤1.5 units |
| Jump: anticipation crouch, ballistic flight (physics), tuck, brace before landing, compression on landing, run continuation | `motion/controller.py` | `out/motion_test.mp4` |
| Physical button press: fingertip IK to the button, contact event triggers the switch | `motion/animator.py` (PRESS) | frame at t=4.583 s |
| Gravity as a configurable vector with timed transitions caused by the switch; the room never moves | `physics/gravity.py` | QA `gravity_transitions_caused_by_switch` |
| Loss of support, then a physics fall (pymunk), impact prediction by ray-cast, brace that aligns feet to the surface, feet-first landing, spring-damped compression, balance wobble, recovery on the new surface | `motion/controller.py` | `out/gravity_switch_1b.mp4` |
| Rigid-body props reacting to the gravity change | `physics/world.py` | crates slide to the wall |
| Cameras: static, follow, track_x and dolly, with smoothing that resets at cuts and a keep-in-frame guard | `camera/director.py` | QA `subject_in_frame` = 100 % |
| 2.5D cutaway room renderer (Skia CPU raster) with glow, bloom, reflection, contact shadows, effects and motion blur | `render/skia_renderer.py` | demo MP4s |
| Event-bound sound (footsteps, click, pulse, whoosh, impacts, clangs), all synthesized | `audio/sound_director.py` | QA `audio_event_sync` |
| Acting layer: notice/double take, gaze at targets, cautious approach, hesitant press (reach, doubt, commit), startle, point, torso twist, weight shift, lagged follow-through | `motion/animator.py`, `motion/controller.py` | `tests/test_cinematic_1c.py` |
| Secondary motion: two-tail verlet scarf that hangs along gravity, room dust that reacts to impacts and the switch | `motion/secondary.py` | QA `scarf_integrity`, `dust_inside_room` |
| Shot vocabulary (establishing, close, insert, tracking), gravity-aligned camera roll, event-driven camera shake, exact roll-aware framing guard | `camera/director.py` | QA `camera_roll_rate`, `gravity_aligned_roll`, `subject_in_frame` |
| Continuity checks: gravity indicator vs physics, screen direction across cuts, static layout | `qa/inspector.py` | QA `check_continuity` |
| Adaptive synthesized music (calm, tension, resolve) and new cues (notice, startle, chime, rising hum) | `audio/sound_director.py` | `tests/test_cinematic_1c.py` |
| Review outputs: full-decode check, timestamped contact sheet, per-frame diagnostics JSON and chart | `qa/media.py`, `render/pipeline.py` (`--review-dir`) | `docs/evidence/gravity_switch_1c_*` |
| 1D actions: feet-first `duck_slide`, ballistic `jump_to` with a mid-air switch slap, `grab_swing` (hands-overhead catch on a pivot joint, absorbed catch, pumping, release at the top of the swing), `reach_exit` | `motion/controller.py`, `motion/animator.py` | `tests/test_escape_1d.py` |
| Exit door state machine (sealed → unlocking → unlocked → opening → open → exited) with rendered states and the walk into the light | `scene/runtime.py`, `render/skia_renderer.py` | QA `door_state_machine` |
| Signed gravity rotations: each state is reported relative to the previous one and to the original, and the camera roll follows the physical direction | `physics/gravity.py`, `camera/director.py` | QA `gravity_angle_report`, `camera_roll_follows_gravity_direction` |
| Motion library: editable key-pose clips (JSON) with per-key interpolation (monotone cubic, ease, snap, slow-in, back, hold), phases, declared contacts and `Performance(tempo, intensity, mirror, emotion, ...)`; rig-relative channels, so the clips play on any proportions | `motion/library.py`, `motion/clips/` | `tests/test_quality_upgrade.py` |
| Contact-aware motion: IK-enforced hand plants and hands-on-knees contacts, knee-clearance collision constraint, stance widths scaled to leg length | `motion/animator.py` | `tests/test_quality_upgrade.py`, QA `surface_penetration` |
| Composition rules: minimum subject size per shot kind, `include` objects kept in frame, no camera roll during fast action | `camera/director.py`, `qa/inspector.py` | QA `composition_*`, `no_roll_during_fast_action` |
| Per-environment art direction (`theme`), motion trails, impact bursts, stereo-panned sound with room reverb | `render/`, `audio/sound_director.py` | `docs/RENDERER_EVALUATION.md` |
| Human review packet: objective metrics kept apart from a 7-criterion human rubric; AI Director suggestions labelled advisory, never scored | `qa/review.py` (`apex review`) | `docs/REVIEW_RUBRIC.md` |
| Motion-test tool: original vs improved side by side with a pose timeline, contact bars and diagnostic curves | `scripts/motion_test.py` | `docs/QUALITY_UPGRADE.md` |
| Physical interaction between two characters and props: bounded-force `push` with stick-slip friction, `lift` clamped to a character's strength, `use_lever` (pick up, carry, place over a fulcrum, press), straps that go taut and snap, falling loads that pin a lying character, `crawl_out`, `get_up` helped by another character's `offer_hand`, `gesture` (fist bump, shoulder pat), `wait_for` events | `motion/interaction.py`, `motion/interaction_anim.py`, `physics/world.py` | `tests/test_rescue.py`, `examples/the_rescue.json` |
| AI Director with simulation feedback: a prompt generated from the schema, a dry run that reports unfinished story steps with physics numbers, and every raw response preserved (`apex plan --log-dir`) | `ai/director.py` | `docs/ai_runs/` |
| Automated QA, 24–61 checks per scene | `qa/inspector.py` | `docs/evidence/*_qa.json` |
| Schema-validated scene plans; AI director with validation and repair loop; offline template planner | `scene/schema.py`, `ai/` | `tests/test_ai_api.py` |
| REST API with background render jobs, progress and error capture | `api/` | `tests/test_ai_api.py` |

## Install and run on Windows (PowerShell)

```powershell
# 1. Prerequisites (one time)
winget install -e --id Python.Python.3.12
winget install -e --id Gyan.FFmpeg          # provides ffmpeg + ffprobe on PATH (restart the terminal afterwards)
winget install -e --id Git.Git

# 2. Get the code and create a virtual environment
git clone https://github.com/aaronfx/Dualview.git
cd Dualview\apex-animation-engine
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 3. Run the automated tests (about 2 minutes)
pytest -v

# 4. Render the milestone demos (1080p, 3-sample motion blur, QA report)
apex render examples\motion_test.json       -o out\motion_test.mp4       --samples 3 --qa-json out\motion_test_qa.json
apex render examples\gravity_switch_1b.json -o out\gravity_switch_1b.mp4 --samples 3 --qa-json out\gravity_switch_1b_qa.json
apex render examples\gravity_switch_1c.json -o out\gravity_switch_1c.mp4 --samples 3 --qa-json out\gravity_switch_1c_qa.json --review-dir out\review_1c
apex render examples\gravity_switch_1d.json -o out\gravity_switch_1d.mp4 --samples 3 --qa-json out\gravity_switch_1d_qa.json --review-dir out\review_1d
apex render examples\foundry_flip.json      -o out\foundry_flip.mp4      --samples 3 --qa-json out\foundry_flip_qa.json --review-dir out\review_ff
apex render examples\the_rescue.json        -o out\the_rescue.mp4        --samples 3 --qa-json out\the_rescue_qa.json --review-dir out\review_rescue
python scripts\interaction_diagnostics.py examples\the_rescue.json out\rescue_diag
# human review packet (objective metrics + rubric; scores are filled in by people)
apex review examples\gravity_switch_1d.json out\review_1d --video out\gravity_switch_1d.mp4 --qa-json out\gravity_switch_1d_qa.json
# fast half-resolution preview:
apex render examples\gravity_switch_1b.json -o out\preview.mp4 --scale 0.5

# 5. Plan a scene from a story (offline template planner; no API key needed)
apex plan --offline "Nova sprints into the lab, presses the red switch and gravity swings to the left wall." -o out\nova.json
apex render out\nova.json -o out\nova.mp4 --scale 0.5

# 6. Optional: AI planning through a provider (keys stay in the backend environment)
copy .env.example .env      # then edit .env, or set the variables in the shell:
$env:APEX_AI_PROVIDER="openrouter"; $env:OPENROUTER_API_KEY="<your key>"; $env:APEX_AI_MODEL="anthropic/claude-sonnet-5.5"
apex plan "your story here" -o out\story.json

# 7. Backend API
apex serve --port 8077      # then open http://127.0.0.1:8077/docs
```

If `activate` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### Linux / macOS

Same steps, using `python3 -m venv .venv && source .venv/bin/activate`. On headless Linux, Skia needs the EGL shared library even for CPU rendering:

```bash
sudo apt-get install -y ffmpeg libegl1
```

## Third-party software and licences

| Dependency | Purpose | Licence |
|---|---|---|
| numpy | numerics | BSD-3 |
| pydantic 2 | schema validation | MIT |
| pymunk (Chipmunk2D) | rigid-body physics behind `physics/world.py` | MIT |
| skia-python (Skia) | CPU rasterizer behind `render/skia_renderer.py` | BSD-3 |
| FastAPI, uvicorn, httpx | backend and HTTP | MIT / BSD-3 / BSD-3 |
| pytest (dev) | tests | MIT |
| FFmpeg (external binary, not bundled) | H.264/AAC encoding and probing | LGPL-2.1+; builds with libx264 are GPL. It is invoked as a separate process and is not linked or redistributed. Check your build's licence before distributing binaries |

**Sound effects.** The engine layers its synthesised sounds with a curated set of 32 recorded samples in `src/apex/audio/sfx/`. They come from OpenGameArt packs by Kenney, rubberduck, thimras, artisticdude and qubodup.

- All of them are CC0 (public domain) and safe for commercial videos.
- The wet-towel pack also carries an MIT/zlib/BSD notice, which is kept in `sfx/licenses/`.

Sources, authors and licences are in `src/apex/audio/sfx/CREDITS.md`, and the mapping from event to sound is in `manifest.json`. Without ffmpeg, or with `SoundDirector(samples=False)`, the engine falls back to synthesised sound only. The music is synthesised by the engine.

## Repository layout

```
src/apex/
  core/      math, easing, timelines (pure functions of time)
  rig/       skeleton, FK, IK, stickman rig, pose blending
  motion/    ground frames, gait generator, character controller (simulation), animator (pose evaluation), motion library + clips/, secondary motion (scarf, dust)
  physics/   gravity field, PhysicsWorld interface (pymunk backend)
  scene/     schema (pydantic), runtime (simulate + evaluate(t))
  camera/    camera director
  render/    renderer adapter (base.py), Skia renderer, video encoding, end-to-end pipeline
  audio/     sound director + synthesizer
  qa/        animation quality inspector, decode check, contact sheets, diagnostics charts, human review packet
  ai/        provider abstraction + story director
  api/       FastAPI app + storage
examples/    project JSON files (milestone scenes); build_gravity_switch_1d.py / build_foundry_flip.py / build_rescue.py regenerate them
scripts/     motion_test.py (original-vs-improved motion comparison), interaction_diagnostics.py
tests/       pytest suite (128 tests)
docs/        architecture, schema, reference analysis, milestone status, roadmap, evidence
```
