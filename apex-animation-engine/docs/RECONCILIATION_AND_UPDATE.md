# APEX — Branch reconciliation and safe Windows update

## Branch topology (as reconciled)

The work lived on three draft-PR branches that all diverged from the same base commit `f5b28cc`:

| Branch | PR | Contents |
| --- | --- | --- |
| `feature/apex-smart-director-local` | #15 | Smart Director: native tool catalogue, typed objectives, ensemble planning, telemetry critic, Local Studio, persistent production jobs, OpenRouter integration, decoded-video critique |
| `apex-reference-grade` | #16 | P1–P5 package, native signed-term math correction, native Smart Director core integration, autonomous film from a natural-language brief, presentation QA, and the **universal obstacle assessment + movement-selection** fix |
| `apex-d10-compiler` | (stacked on #15) | **Contains all of #15** plus D10: deterministic instruction compiler, reference resolver, self-repair, independent story verification, partial-response handling, and the sign-inversion morph fix |

Because `apex-d10-compiler` already contains every commit of `feature/apex-smart-director-local`, the single
unified branch is produced by merging `apex-reference-grade` (#16) into `apex-d10-compiler` (= #15 + D10):

```
apex-unified = apex-d10-compiler  (#15 Smart Director + D10)
             + apex-reference-grade (#16 P1–P5, math, obstacle assessment, autonomous film)
```

All subsequent corrections and upgrades are made on **`apex-unified`**. D10, Local Studio, OpenRouter integration,
native animation, math corrections, autonomous choreography, production management and API spending controls are all
preserved on it. Nothing is merged into `main` and nothing is deployed to Railway.

## What is preserved automatically on update

These paths are git-ignored, so **fetch / checkout / merge never touch them**:

- `out/` — all generated videos and render review sheets
- `.venv/` — the Python virtual environment
- `.env` — API keys / OpenRouter configuration (only `.env.example` is tracked)
- `__pycache__/`, `.pytest_cache/` — caches
- any local production history / job store kept under `out/` or another ignored path

> Before updating, confirm your local production history and settings live under an ignored path (e.g. `out/` or a
> dotfile). If you keep them somewhere tracked, copy them aside first (the commands below also make a safety tag so
> nothing is lost).

## Exact Windows PowerShell update commands

Run from the existing installation. These update it to `apex-unified` **without deleting generated videos, local
production history, settings, the virtual environment, or API configuration**. They never force-push and never touch
`main`.

```powershell
cd C:\Users\User\APEX-Smart\apex-animation-engine

# 0) Safety: tag whatever you have now so it can always be recovered, and back up ignored data just in case.
git tag backup/pre-unified-$(Get-Date -Format "yyyyMMdd-HHmmss")
if (Test-Path .\.env) { Copy-Item .\.env .\.env.backup -Force }
# (out\ videos, .venv\ and .env are git-ignored and will NOT be altered by the steps below.)

# 1) Save any uncommitted local edits on your current branch so the switch is clean.
git add -A
git commit -m "WIP: local changes before updating to apex-unified" 2>$null
#   If there was nothing to commit, that message is harmless.

# 2) Fetch the reconciled branch.
git fetch origin apex-unified

# 3) Switch to it (your ignored out\, .venv\ and .env are untouched).
git checkout apex-unified
git pull --ff-only origin apex-unified

# 4) Refresh dependencies inside your EXISTING venv (kept, not recreated).
.\.venv\Scripts\Activate.ps1
pip install -e . --upgrade

# 5) Verify the installation.
$env:PYTHONPATH = "src"
python -m pytest -q tests/
```

If step 3 reports a conflict because you had local commits on the old branch, do **not** force anything — merge
instead and keep your work:

```powershell
git merge --no-edit origin/apex-unified
# resolve any conflicts, then:
git add -A
git commit --no-edit
```

Your generated videos remain in `out\`, your OpenRouter key remains in `.env`, and your virtual environment in
`.venv\` is reused.
