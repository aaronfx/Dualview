# APEX Animation Engine

A standalone, AI-directed procedural animation engine. It turns structured scene plans, which an LLM can generate from a story, into physically grounded stick-figure animation. It renders 1080p MP4s with synchronized sound and automatically checks every render for animation defects.

> **Status:** Milestones 1A and 1B are complete and verified. 1C (character acting, secondary motion, cinematic direction) is implemented and technically verified, and its 14 s review sequence is rendered; the artistic sign-off is pending the owner's review (see `docs/MILESTONE_STATUS.md`). 1D, the full 30-second story, is planned (`docs/MILESTONE_1D_PLAN.md`) but not started.

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
| Automated QA, 24–31 checks per scene | `qa/inspector.py` | `docs/evidence/*_qa.json` |
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

# 3. Run the automated tests (about 1 minute)
pytest -v

# 4. Render the milestone demos (1080p, 3-sample motion blur, QA report)
apex render examples\motion_test.json       -o out\motion_test.mp4       --samples 3 --qa-json out\motion_test_qa.json
apex render examples\gravity_switch_1b.json -o out\gravity_switch_1b.mp4 --samples 3 --qa-json out\gravity_switch_1b_qa.json
apex render examples\gravity_switch_1c.json -o out\gravity_switch_1c.mp4 --samples 3 --qa-json out\gravity_switch_1c_qa.json --review-dir out\review_1c
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

All sounds are synthesized by the engine; no third-party audio assets are used.

## Repository layout

```
src/apex/
  core/      math, easing, timelines (pure functions of time)
  rig/       skeleton, FK, IK, stickman rig, pose blending
  motion/    ground frames, gait generator, character controller (simulation), animator (pose evaluation), secondary motion (scarf, dust)
  physics/   gravity field, PhysicsWorld interface (pymunk backend)
  scene/     schema (pydantic), runtime (simulate + evaluate(t))
  camera/    camera director
  render/    Skia renderer, video encoding, end-to-end pipeline
  audio/     sound director + synthesizer
  qa/        animation quality inspector, decode check, contact sheets, diagnostics charts
  ai/        provider abstraction + story director
  api/       FastAPI app + storage
examples/    project JSON files (milestone scenes)
tests/       pytest suite (66 tests)
docs/        architecture, schema, reference analysis, milestone status, roadmap, evidence
```
