# APEX — independent Windows + Codex workspace

## What this clone is

This branch was created directly from Claude's APEX commit
\`5dc968732b9b41d2aeb5bc9cfdbd7157216f92c3\` (22 Nov 2026).
It is NOT derived from the GPT Director's Cut PR #8. No engine behavior or film
story files were changed when the local workspace was prepared.

- Reference branch (Claude): \`ccr-8f5558fb-f9agl2\` — do not push to it from this workspace.
- Independent development branch: \`apex-independent-local-20261122\`.
- The independent branch is in the **same GitHub repository**, but it is a
  separate line of commits. If full repository-level isolation is desired,
  create a new private GitHub repository for APEX later and change the
  independent clone's remote.
- A cloned workspace is physically separate from Claude's local files and
  does not automatically track further Claude updates.

## 1. Install prerequisites (one time)

In Windows PowerShell, run these only if not already installed:

\`\`\`powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
winget install -e --id Gyan.FFmpeg
\`\`\`

Close and reopen PowerShell, then verify:

\`\`\`powershell
git --version
py -3.12 --version
ffmpeg -version
ffprobe -version
\`\`\`

No CUDA GPU is required. The Skia rasterizer and Pymunk physics run on CPU.
Rendering a multi-minute 720p/1080p film can still take considerable time.

## 2. Clone in its own folder

\`\`\`powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\Documents\Codex" | Out-Null
Set-Location "$env:USERPROFILE\Documents\Codex"
git clone --single-branch --branch apex-independent-local-20261122 https://github.com/aaronfx/Dualview.git APEX-Independent
Set-Location .\APEX-Independent\apex-animation-engine
git branch --show-current
git log -1 --oneline
\`\`\`

The branch must show \`apex-independent-local-20261122\`. **Do not
\`git checkout ccr-8f5558fb-f9agl2\` or \`git push origin ccr-8f5558fb-f9agl2\`.**

## 3. Set up Python and verify local execution

\`\`\`powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_windows.ps1 -QuickTests -RenderSmoke
\`\`\`

The script creates \`apex-animation-engine/.venv\`, installs APEX with the
project's declared dependencies, validates \`examples/core_run.json\`,
runs focused runtime tests, and optionally renders
\`out/local_smoke.mp4\` with its QA JSON.

For a quick initial setup without tests or rendering:

\`\`\`powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_windows.ps1
\`\`\`

For the entire test suite later:

\`\`\`powershell
.\.venv\Scripts\python.exe -m pytest -q
\`\`\`

Tests may take many minutes.

## 4. Preview the actual Claude CORE RUN locally

\`\`\`powershell
.\.venv\Scripts\apex.exe validate examples\core_run.json
.\.venv\Scripts\apex.exe film examples\core_run.json -o out\CORE_RUN_local_draft.mp4 --preset draft --report out\CORE_RUN_local_report.json
\`\`\`

This uses the independent copy of **Claude's** latest CORE RUN project, not
the previous GPT movie. The project can be re-rendered after changing shots,
choreography or environments locally. Look at the QA report and video;
a successful encode alone is not movie acceptance.

When approved and technical QA is clean, use \`--preset final\` for 1080p.
Do not produce expensive full-resolution renders for every iteration.

## 5. Run the local API (optional)

\`\`\`powershell
.\.venv\Scripts\apex.exe serve --port 8077
\`\`\`

Open \`http://127.0.0.1:8077/docs\` for the FastAPI/OpenAPI test interface.
This is an API interface, **not** a finished timeline editor or Creator
Studio-style GUI.

## 6. Open in Codex desktop

Open the folder:

\`C:\Users\<your Windows user>\Documents\Codex\APEX-Independent\apex-animation-engine\`

Request Codex to **audit** before changing physics or film logic. Begin by
reading \`README.md\`, \`docs/ARCHITECTURE.md\`, \`docs/SCENE_SCHEMA.md\`,
\`docs/ACTION_FILM_PLAN.md\`, and \`examples/build_core_run.py\`.
Capture baseline tests and rendering first. Work on a new feature branch for
risky experiments and keep the APEX-independent baseline recoverable.

### Main architecture (source modules)

| Area | Source | Role |
|---|---|---|
| Validated project plans | \`src/apex/scene/schema.py\` | Strict Pydantic specifications |
| Scene simulation | \`src/apex/scene/runtime.py\` | Fixed-step event log and physical state |
| Physical dynamics | \`src/apex/physics/\` | Pymunk world, gravity, collisions |
| Character movement and performances | \`src/apex/motion/\` | Controllers, acrobatics, combat, ragdoll, acting, animator |
| Visual skeletons | \`src/apex/rig/\` | Skeletons, IK, poses |
| Cameras | \`src/apex/camera/\` | Shot direction and subject framing |
| Rendering and film joining | \`src/apex/render/\` | Skia frames, FX, FFmpeg output |
| Audio | \`src/apex/audio/\` | Event-bound effects and synthesized music |
| QA | \`src/apex/qa/\` | Technical and cinematic checks |
| Story AI | \`src/apex/ai/\` | Optional provider, offline planner, budget |
| HTTP backend | \`src/apex/api/\` | FastAPI, storage, render jobs |
| CLI | \`src/apex/cli.py\` | validate, render, film, plan, qa, review, serve |
| Film builders | \`examples/build_*.py\` | Authored choreography and project JSON |
| Tests | \`tests/\` | Regression and behavior acceptance |

## 7. Optional OpenRouter access

The engine runs, renders and tests without an AI key. Paid AI experiments
are off by default. Copy \`.env.example\` to \`.env\` only if you plan to use
the AI Director, keep API keys out of Git, and review \`docs/AI_SPEND.md\`.
Never store keys in project JSON or Codex prompts.

## 8. Troubleshooting and guardrails

- **Python, Git or FFmpeg not found**: install via \`winget\`, restart PowerShell.
- **Skia import error**: use the \`.venv\` installed by the script; inspect the
  Windows DLL wheel and Python version.
- **Some referenced audio samples are missing**: the checked-in sound manifest
  can reference audio not present in a fresh clone. The source's current
  \`SampleBank\` checks for FFmpeg but does not prevalidate every manifest file;
  capture the exact failure rather than assuming the film is broken.
- **Long rendering times**: first use \`--preset draft\`; \`final\` is 1080p with
  additional motion-blur samples. Render one scene for rapid iteration:
  \`apex render examples\core_run.json --scene city -o out\city_preview.mp4\`.
- **Branch separation**: the local workspace uses its own Git branch and
  output directory. It will not receive Claude's later commits automatically.
- **Not yet a desktop GUI**: use Codex + terminal + API docs + MP4 previews.
  A GUI can be a later, separate engineering milestone.

## 9. Safety checkpoint

Before modifying the engine, record \`git rev-parse HEAD\`, store
\`pytest\` results and render an unchanged short example. Do not merge old PR #8
unless individual changes are reviewed independently against this baseline.
