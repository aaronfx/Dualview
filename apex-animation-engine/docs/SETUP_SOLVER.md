# Setup solver: APEX chooses the physical numbers

## Why

None of the earlier AI Director runs produced a plan that played the whole *Rescue* story (`docs/RESCUE_REPORT.md` §5). The models wrote reasonable stories. They failed on numbers that can only be found by simulating:

- the static friction that lets a push break a container loose;
- the strap slack and break force that topple a post;
- where the post has to stand to land on the character who fell;
- where a fulcrum has to be for a bar to lift the post's end;
- when each event happens, which decides where the cuts go.

A stronger model was not the fix. An unapproved Opus run (v5) got further than Sonnet, but it still had to guess the same numbers (see `docs/AI_SPEND.md`). The fix is to stop asking the model for these numbers.

## What changed

The planner now states **intent**. APEX's own physics works out the **numbers**.

| Planner writes | APEX does (`src/apex/scene/solver.py`) |
|---|---|
| `scene.goals`: the ordered story beats, e.g. `["push_lost@a", "pinned@a[by=post]", "lift_fail@b", "lever_engage@b", "freed@a", "stood_up@a"]` | Simulates and checks the beats happen in order. Tunes the setup until they do |
| Plausible masses, frictions, positions | **Physics-derived fixes, in closed form.** Static friction just below the push force, so the prop breaks loose. Sliding friction low enough that it gets away. Slack for a rope that starts taut. A break force for a rope that must snap. An obstruction that must pin someone is made solid to characters |
| A prop tied to the pushed one | **Placement from the simulation.** The `body_fall` position from a first run decides where the toppling prop stands, so its fall covers the body |
| A bar and a fulcrum for `use_lever` | **Placement from the simulation.** The fulcrum goes about 0.3 bar-lengths beyond the end of the load nearest the body, *where the load came to rest*. The bar goes a short run away. A relocated fulcrum becomes non-solid set dressing, so it cannot block the earlier accident |
| Nothing else | **Bounded search.** Seeded local search with restarts over the physical knobs the action list depends on: frictions, load mass, rope slack and break force, positions of the toppling prop, tool, fulcrum and helper, and the toppling prop's balance. Uses fast physics-only simulations (about 0.3 s each, against about 4.4 s for a full one). Score: goals met in order, then a measure of closeness to the next missing goal (prop displacement, rope tension over break force, gap between the falling prop and the body), then fit to the planned length |
| `shot.cut_on: "event:<type>@<who>"` | `resolve_cuts` puts each cut at its simulated event time |
| Repairs as `{"patch": [...]}` | RFC 6902 operations against the previous plan, instead of a full rewrite. Unknown fields get "did you mean" hints, and common rope spellings are accepted |

**What APEX never changes:** the actions, their order, the characters, or the props in the scene. If the beats cannot be reached by tuning the setup, the report names the first missing beat and says the story structure has to change. That message goes back to the planner.

**Honesty.**

- The director keeps the model's plan exactly as written (`ai_plan_as_written.json`) separate from the engine's adjustments (`engine_adjustments.json`, each with its reason).
- A film made this way should be described as an **AI-written story with an engine-tuned physical setup**. It should not be called fully AI-generated or hand-made.

**Engine race guards** found from the AI runs:

- `struggle` with `until` now waits for the event; before, it timed out after 1.5 s.
- `crawl_out` waits while a load is still coming down.
- A helped `get_up` stops waiting when the helper has no `offer_hand` left, or after 4 s, and emits `help_missed`.

## Results (offline replay of recorded responses; no new paid calls)

**Status: interim.** The full replay of all 31 recorded responses is still to run.

The plans are scored against the brief's six beats, mapped to whichever character pushes (P) and whichever uses the lever (H): `push_lost@P`, `pinned@P`, `lift_fail@H`, `lever_engage@H`, `freed@P`, `stood_up@P`.

| Recorded response | Current engine alone | Plus setup solver |
|---|---|---|
| `rescue_upgraded_v2` attempt 5 (Sonnet 5.5) | 0 / 6 (struggles while still standing) | **6 / 6 with 3 of 4 seeds**, 90 simulations each (~45 s). The fourth seed reached 3 / 6 |
| `rescue_upgraded_v5_opus` attempt 5 | 3 / 6 | All goals derived from its own `until` events reached in 10 simulations |
| `rescue_upgraded_v5_opus` attempt 8 | 0 / 4 derived goals | All reached in 16 simulations |

**Known limitations**

- **Length.** Solved plans run 23–30 s against the brief's 15–20 s. The pacing comes from the plan's own actions: long walks, waits and approach speeds. The solver deliberately doesn't change actions, so it can only move props and the helper's starting position.
- **Not every seed succeeds.** The search is a bounded random search, so it can miss a solution within its budget.
- **Structure can't be invented.** Plans with no strap, or with no push and lever actions, are reported as structural gaps. They are not fixed.
- **Lever geometry is heuristic.** The fulcrum and bar placement is a rule (0.3 bar-lengths beyond the load's end), not an optimisation.
