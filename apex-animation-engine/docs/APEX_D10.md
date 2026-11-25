# APEX D10 — Intelligent compiler, self-repair and independent story verification

Branch `apex-d10-compiler` (off `feature/apex-smart-director-local`). The primary bottleneck addressed is the
translation of AI-generated plans into valid, physically executable native instructions, plus the acceptance of the
*requested* story. No paid OpenRouter calls were made; the AI model was not upgraded; no QA threshold was weakened;
no existing capability was removed.

## Reported failures → fixes (reproduced with offline fixtures, no API calls)
| # | Failure | Fix | Test |
|---|---------|-----|------|
| 1 | `camera.target = "prop:girder"` (needs a placed character) | `plan_compiler.repair_camera`: the object is moved to `camera.include`; the shot is retargeted to the sole character, or switched to static framing when the subject is ambiguous | `test_plan_compiler.py` |
| 2 | `lift` generated without a `target` | `plan_compiler.repair_action` + `_infer_missing`: a mandatory parameter is filled only from a single unambiguous scene candidate, otherwise **rejected** ("refusing to guess") | `test_plan_compiler.py` |
| 3 | tiny repair response treated as a full replacement project | `plan_revision.PlanRevision`: targeted patches (replace/update/insert/delete) are applied to the preserved validated plan; invalid patches are rejected and the previous revision kept | `test_plan_revision.py` |
| 4 | dashboard stuck at 0% | **Not yet implemented** (D10.6) — see Scope below | — |
| 5 | wrong story accepted (single character + switch for a requested two-character rescue) | `story_check`: the required story is derived from the brief independently of the plan and verified against actual native events; wired into `local_production` so a technically valid wrong-story film is rejected, and an unsupported offline brief yields a clear limitation | `test_story_check.py` |

## Implemented and tested (native, offline)
- **D10.1 instruction compiler** — `ai/plan_compiler.py`, schema-driven on the native `ActionSpec`/`ProjectSpec` +
  capability catalogue (`REQUIRED` params, namespaces). Validates every reference; records every correction.
- **D10.2 reference resolver** — scene-aware resolution of characters/props/obstacles/exits/tools/cameras; corrects an
  unambiguous namespace/format error, **rejects** an ambiguous or unknown one.
- **D10.3 deterministic self-repair** — invalid formats, missing mandatory parameters, wrong namespaces. No physical
  outcome is changed; validation is not weakened.
- **D10.4 structured partial-response handling** — `ai/plan_revision.py`; revision history; invalid patches rejected.
- **D10.5 independent story verification** — `ai/story_check.py`; required story derived from the brief, verified
  against native simulation events in order; wired into `local_production.create_from_brief`/`run_production` so the
  requested story gates acceptance; unsupported offline → clear limitation, never a silent substitution.

Tests: `tests/test_plan_compiler.py` (8), `tests/test_story_check.py` (4), `tests/test_plan_revision.py` (4) — all
offline, no API calls. The existing production/director/mission/visual-profile tests continue to pass unchanged.

## Mandatory rescue acceptance film (independently verified)
`examples/the_rescue.json`, rendered native 1080p in both the approved **ink** and **legacy** character styles. Every
required physical story beat is verified independently against the native simulation (`out/d10/rescue_*.story.json`):
two characters → `pinned` → `notice` → `lift_fail` → `lever_engage` → `freed` → `stood_up` → `fist_bump`, **in order,
8/8, 0 controller violations**. MP4 decode and audio/video duration sync verified.

## Scope — honest status (implemented vs tested vs artistically accepted)
**Implemented + unit-tested (offline):** D10.1, D10.2, D10.3, D10.4, D10.5, and the story-gate integration into the
production acceptance path (part of D10.8).

**Not yet implemented in this pass (documented, not claimed):**
- **D10.6 live production monitoring** — the Local Studio dashboard still shows coarse progress; the staged
  AI/validation/repair/rehearsal/render telemetry, API cost/count surface and persisted failed-plan diagnostics are a
  follow-up.
- **D10.7 cancellation & timeouts** — safe job cancellation, bounded processing, interrupted-job recovery and spend
  caps beyond the existing budget controls are a follow-up.
- **D10.8 full compiler↔planner integration** — the compiler/resolver/repair are standalone + the story gate is wired;
  routing every AI plan through the compiler inside `director_local`/`mission` is a follow-up.
- **D10.9 end-to-end acceptance with a live (paid) planner** — not run (no paid calls during debugging, per the brief).
  The offline path and independent verification are tested; a paid E2E needs explicit owner approval.
- **Artistic improvements (section 5)** — thin/over-glowing outlines, grounding, climbing mechanics, grip/brace,
  aerial variety, emotional reactions and environmental detail are **not** addressed here; the approved ink character
  is used as the foundation. A numerical QA pass is **not** artistic acceptance; the rescue MP4s are submitted for
  human review.

## Windows operating instructions (unchanged core, new tools)
From `apex-animation-engine`, Python 3.12 with FFmpeg/ffprobe on PATH:
```
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_plan_compiler.py tests/test_story_check.py tests/test_plan_revision.py
python -m apex.cli render out\d10\rescue_ink.json -o out\d10\rescue_ink.mp4 --scale 1 --samples 1 --qa-json out\d10\rescue_ink.qa.json
```
The deterministic compiler and story verification run with no network and no API key. The paid planner path
(`director_local mission`, `local_studio`) is unchanged and still gated by the existing spend controls.
