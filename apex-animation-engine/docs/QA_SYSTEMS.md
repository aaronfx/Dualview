# QA systems

The automated quality harness for APEX. It proves the animation is **technically correct** and **explainable**. It
never proves the film is **good** — that is a human judgement (`docs/REVIEW_RUBRIC.md`, the review gate below). Passing
technical QA is not grounds for any claim about artistic quality.

Every check belongs to one of two gates (`qa/inspector.py`):
- **technical** — physics consistency, valid geometry, no unintended clipping, stable replay, correct event outcomes. A
  single FAIL fails the gate.
- **cinematic** — automated readability (silhouettes, framing, camera, pacing, occlusion, narrative). These **warn**
  rather than fail; a person decides what reads well.

## New checks (CORE RUN)

Each check ships with positive **and** negative tests (`tests/test_core_run_regressions.py`) so we know it catches a
genuine failure without rejecting valid animation.

| Check | Gate | What it proves | Tuned so that… |
|-------|------|----------------|----------------|
| `carried_object_continuity` | technical | a carried prop stays in the carrier's hands through the ground, jumps, flips and falls | a swing may extend the arms (≈38–54 u); a prop *left behind* is >100 u away → threshold 60 u |
| `props_not_floating` | technical | no posed (kinematic) prop that nobody carries hangs above any surface | only props that are *ever carried* are judged, so an authored flyer (a drone on a path) is exempt |
| `characters_not_overlapping` | cinematic | important characters/props do not bury one another on screen | a prop held by its own carrier is excluded (that overlap is "holding", not occlusion) |
| `narrative_order` | cinematic | the scripted story beats happen in the listed order | near-simultaneous beats (<0.75 s) may still swap |
| `narrative_causality` | cinematic | every decisive effect (knockdown, hit, throw, disarm, freed, pulled_up…) has its cause on record before it | carrying a prop (incl. carried in from the previous scene) counts as the cause of a throw/disarm/carried_out |
| `decisive_events_visible` | cinematic | the scripted goal beats play where the camera is looking | a beat with no world point is not judged |

### Structured diagnostics

`Check` carries an optional `diag` list. When a check fails or warns, each record says **when** (`t`), **who**
(entities), **where** (positions), the **state** that matters, and a **likely cause** — so a failure explains itself
instead of being a bare number. `QAReport.to_dict()` serialises the diagnostics with the checks.

## Regression benchmark (`qa/benchmark.py`)

Every committed film is re-simulated and judged on story outcome, the technical gate, the cinematic gate and goal-time
drift. A film **regresses** if it meets fewer goals, a check that passed now fails, or a gate gets worse. Defects that a
reviewed baseline already had are reported as **`known`**, not regressions (so a frozen reference such as
`core_run_r4.json` keeps its recorded shortfalls on the record without masking new breakage).

```
PYTHONPATH=src python -m apex.qa.benchmark            # compare against the baseline
PYTHONPATH=src python -m apex.qa.benchmark --update   # store a new baseline (after a reviewed, intended change)
```

## Action test matrix (`qa/transitions.py`)

Two matrices run chains/contexts through the full engine with no per-scenario tuning:
- **Hand-over chains** — two-to-four move sequences across the scripted↔physics boundary (flips, rolls, combat,
  ragdoll, carrying, climbing).
- **Pairwise context matrix** — one move under varied context. The factors (`move`, `carrying`, `surface`, `lane`,
  `nearby` structure, `pace`) are exactly the ones whose *combinations* produced the CORE RUN bugs. Testing every
  combination is 128 scenes; a **pairwise covering array** hits every pair of factor levels in ~12 scenes, and a short
  **high-risk** list adds the specific dangerous combinations (carry+jump over a wall between lanes, carry+slide past a
  wall, …).

```
PYTHONPATH=src python -m apex.qa.transitions              # hand-over chains
PYTHONPATH=src python -m apex.qa.transitions --pairwise   # pairwise context matrix + high-risk combos
```

## Visual review (contact sheets + mandatory gate)

- **Contact sheets** (`qa/media.py`, wired into `render --review-dir`) sample a **one-second grid** over the whole film
  **plus high-frequency frames** (every ~2 frames) in a ±0.4 s window around each key event (impacts, hand-overs,
  decisive beats), each frame labelled with shot and state and marked when it belongs to an event.
- **Mandatory review gate** (`qa/review.py`, `apex review-gate <dir>`). A movie **revision is not deliverable** until a
  human reviewer has completed the rubric for it (`reviewers/<name>.json`, every criterion scored). Technical QA passing
  does not substitute for visual review, and the scores are advisory — they are never an automatic quality claim.

```
apex review <project> <dir> --video <mp4> --qa-json <json>   # write the rubric packet + a blank score sheet
apex review-gate <dir>                                        # exit 0 only if a human has reviewed this revision
```

## Next priority: a deterministic choreography stager

The CORE RUN work showed the choreography is fragile: lanes, throw origins and timing cascade through the physics, and
much of the effort went into hand-placing props and tuning beats so the simulation produced the intended staging. The
agreed next major step is a **deterministic choreography stager between the AI Director and the simulation engine**: the
Director states intent (who does what, where, in what order); the stager resolves it into concrete, physically-valid
placements, lanes, timings and camera framing deterministically; the engine then simulates it. The QA systems here are
the verification layer that stager will be built against — continuity, floating, occlusion, narrative order/causality
and decisive-beat visibility are exactly the invariants an autonomous stager must preserve, with the diagnostics telling
it *why* a staging failed.
