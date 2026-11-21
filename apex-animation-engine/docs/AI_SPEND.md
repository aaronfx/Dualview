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
| — | — | — | Paid testing is paused until the owner re-enables it | — | — | — |
