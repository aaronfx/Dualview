# Paid AI experiments: policy and record

## Policy (enforced in code: `src/apex/ai/budget.py`)

| Rule | How it is enforced | Default |
|---|---|---|
| Paid calls are off unless switched on | `APEX_AI_PAID_ENABLED=1` is required, otherwise nothing is sent | **off** |
| Low-cost models only | A model must be in `LOW_COST_MODELS`, or the owner names it in `APEX_AI_APPROVED_MODELS` | Haiku 5.5, DeepSeek V4.1 Flash, Qwen 3.8 Flash, GPT-5 nano |
| No automatic escalation | An experiment is bound to one model; a model change mid-experiment is refused; APEX has no fallback model | — |
| Limited paid retries | `APEX_AI_MAX_CALLS` per experiment, which also caps the director's repair loop | 3 calls |
| Output cap per call | `APEX_AI_MAX_OUTPUT_TOKENS` (the value actually sent) | 6000 |
| Experiment budget | A call is refused if its **worst case** (full prompt plus the full output cap) would cross the cap | $0.10 |
| Total budget | Same check against everything recorded in the ledger | $1.00 |
| A reason for every experiment | An empty reason is refused | — |
| Report every experiment | One ledger line per experiment (`APEX_AI_LEDGER`): model, reason, worst-case estimate, actual cost and its source, calls, outcome | `apex_data/ai_ledger.jsonl` |
| Unknown price is refused | Prices come from `src/apex/ai/model_prices.json`, a snapshot of OpenRouter's free public model list | — |

- `apex ai-budget` prints the policy and the ledger (no network).
- `apex plan --reason "..."` prints the worst-case estimate before the first call and the actual cost at the end. It also stores the record in `result.json`.
- These rules are verified offline by `tests/test_ai_budget.py`, which uses a mock HTTP transport, so the tests send nothing and use no credits.

## Past experiments (before the policy existed)

Per-experiment costs were **not recorded** at the time. The only measured figure is the account's total usage, which read **$3.36** after the v5 run. That figure covers every call made with the key, not only these runs.

The estimates below use only the visible prompt and response text at today's listed prices. They don't include hidden reasoning tokens, which are billed as output. That is the most likely reason they add up to much less than the measured total.

| Run | Model | Calls | Reason at the time | Estimated cost (visible text only) | Actual cost |
|---|---|---|---|---|---|
| `rescue_baseline` | claude-sonnet-5.5 | 3 | Test whether the unchanged engine could represent the story | ~$0.07 | not recorded |
| `rescue_upgraded_v1` | claude-sonnet-5.5 | 3 | Re-test after adding the interaction actions | ~$0.06 | not recorded |
| `rescue_upgraded_v2` | claude-sonnet-5.5 | 5 | Re-test with the dry-run "stuck" check | ~$0.12 | not recorded |
| `rescue_upgraded_v3` | claude-sonnet-5.5 | 4 | Re-test with physics numbers in the feedback | ~$0.05 | not recorded |
| `rescue_upgraded_v4` | claude-sonnet-5.5 | 8 | Re-test with robust parsing and 8 attempts | ~$0.20 | not recorded |
| `rescue_upgraded_v5_opus` | **claude-opus-5.5** | 8 | Check whether a stronger model would get further. **Not approved by the owner. It should not have been run.** | ~$0.50 | not recorded |
| **Total** | | 31 | | **~$1.00** | account total **$3.36** (all usage) |

**Lesson recorded.** The failures were in the physical setup: the plans needed exact friction, slack and geometry values. A stronger model doesn't fix that. The fix is for APEX's own physics and validation to choose those values. The v5 run escalated cost without addressing the cause.

## New experiments

From now on, every paid experiment is listed here from its ledger record, with its model, estimated cost, actual cost and reason.

| Date | Experiment | Model | Reason | Estimated (upper bound) | Actual | Outcome |
|---|---|---|---|---|---|---|
| 2026-11-21 | `20261121T075057Z-198e22` (`docs/ai_runs/rescue_solver_v6_haiku/`) | anthropic/claude-haiku-5.5 | Owner-approved test of the new workflow on *The Rescue*: story goals, setup solver, patch repairs | $0.0123 before the run (upper bound), $0.0100 summed per call | **$0.0069** (provider usage report) | **Failed** after 3 calls. See the findings below |

| 2026-11-21 | `20261121T075646Z-e9f466` (`docs/ai_runs/rescue_solver_v7_haiku/`) | anthropic/claude-haiku-5.5 | Owner-approved re-test after the v6 fixes | $0.0134 before the run (upper bound), $0.0107 summed per call | **$0.0040** (provider usage report) | **Failed** after 3 calls. See the findings below |

| 2026-11-21 | `20261121T080813Z-49d8c5` (`docs/ai_runs/rescue_solver_v8_haiku/`) | anthropic/claude-haiku-5.5 | Owner-approved: second worked example (*Runaway Crate*) in the prompt, lenient patches, up to 5 calls | $0.0223 before the run (upper bound), $0.0179 summed per call | **$0.0053** (provider usage report) | **Failed** after 5 calls. See the findings below |

**Running total of new experiments:** $0.0162. **Ledger total:** $0.0162 of the $1.00 cap.

**Findings from `rescue_solver_v8_haiku`:**

- **The first plan was much better structured.** Unlike v7, the lever targets the support, the helper waits for `body_fall`, and the goals are real events. Hidden reasoning was again 0 tokens.
- **Haiku copied an exit hatch from the Foundry Flip example**, wired to a switch that didn't exist. It spent all four repairs on that hatch.
  - **Fix:** the gravity/switch example is now included only when the story is about gravity or switches. The prompt says to include only what the story needs.
- **The field hints were wrong.** One suggested `position` for `position`.
  - **Fix:** hints now list the fields allowed at that exact location and never suggest the same name.
- **Offline diagnosis.** I replayed the paid response, removing the stray hatch by hand for diagnosis only, so the plan is not counted as AI-generated.
  - The solver reached push, break loose and strap snap.
  - Ordered goals were too strict: a fall 0.4 s before the strap snapped failed `rope_snap` → `body_fall`.
    - **Fix:** beats may be out of order by up to 0.75 s.
  - It then reaches the fall, and stops at `pinned`. Haiku's support is a 520-long post tilted almost flat and strapped at its foot. The solver's placement rule assumes an upright post, which is a known limitation.

**Findings from `rescue_solver_v7_haiku`:**

- **The v6 fixes held.** Hidden reasoning was 0 tokens. Attempt 1 was a complete 9,168-character plan, with 4,264 output tokens.
- **The patch rules were too strict.** Attempt 2's repair was rejected because it used "replace" to set a field that didn't exist yet. Strict RFC 6902 forbids that, but planners use it routinely. Attempt 3 then patched the stale plan.
  - **Fix:** "replace" of a missing key now acts as "add".
  - **Checked offline** by replaying the same paid responses: attempt 2 now passes the schema and reaches the setup solver.
- **The solver rejected the plan's structure, correctly:**
  - The lever targets the **container**, not the fallen support.
  - The push lasts only 2 s against a 900-mass container.
  - The helper "notices" at 0.5 s, before anything has happened.
  - The goals include `run_to@bo`, which is an action, not an event.
  - In 88 simulations, no physical setting could make the push get away. These are story-structure errors for the planner to fix, and the engine did not hide them.
- **Goals named non-existent events.**
  - **Fix:** goals and `cut_on` must now name a real engine event, with "did you mean" hints.

**Findings from `rescue_solver_v6_haiku`** (all three fixed afterwards, offline):

1. **Hidden reasoning used up the output budget.** Attempt 1 was billed 6,000 output tokens but returned 136 visible characters, a stub with only one character. This also explains why past visible-text estimates (~$1.00) undercounted the account total ($3.36).
   - **Fix:** APEX now asks OpenRouter to turn reasoning off (`APEX_AI_REASONING_TOKENS`, default 0).
   - The ledger records `reasoning_tokens` and the number of visible characters.
   - The director flags any call billed for much more output than it returned.
2. **Proportion keys were not validated.** Attempt 3's `proportions: {"height": 175}` passed the schema and crashed the runtime.
   - **Fix:** proportions are now checked against the rig's segment names and ranges, so the model gets a clear schema error it can repair.
3. **Input tokens were underestimated.** Estimated 4,518, actual 6,039. The worst-case cap still held because the output cap dominates.
   - **Fix:** the estimator now uses 2.4 characters per token.

The patch repairs worked as designed. Attempts 2 and 3 were patches of 3.4k and 0.5k characters, much shorter than full rewrites. The setup solver was never reached, because no attempt passed schema validation.
