# APEX M3 — bounded autonomous choreography, first verified proof

## Problem

Previous films such as *The Threshold* were physically valid, but their action sequence was still manually specified. The AI Director could write an action list without proving it physically possible. An expressive character is not yet an autonomous character.

## Implemented

`src/apex/scene/autochoreo.py` introduces **bounded, deterministic tactical search** for a downward-gravity scene with one figure, one structural barrier, one physical prop reward and optionally another movable prop. This is intentionally *not* a general-purpose robotic planner or an LLM deciding untrusted runtime commands.

- Reads the actual Pydantic `ProjectSpec` and geometry of the wall, actor and reward.
- Generates six candidate action sequences: `direct_run`, `low_jump`, `powered_jump`, `vault`, `climb_then_drop`, and (if appropriate) `shift_crate_then_climb`.
- Rejects impossible jumps early with `route_planner.check_jump`, using the same gravity, collision envelopes and launch speed budgets.
- Executes each remaining tactic in a fresh deterministic native APEX `SceneRuntime(..., strict=False).simulate(physics_only=True)`, 240 Hz. Each trial has a bounded duration and does not inherit previous outcomes.
- **Requires a real `pick_up` event for the named prop**, the correct tactic event, no controller violation, no falling/push-loss failures, and enough time to show a payoff.
- For the crate tactic, requires a `push_end` event and independently measures the crate's physical x-displacement from its simulated track. A plausible-sounding push is not credited.
- Scores *passing* routes on event time and complexity. An optional tool-use preference only rewards the crate tactic **after** physical proof.
- Returns an explicit JSON proof/rejection trace with the chosen tactic, reasons and timestamps.
- The original film is then rebuilt **from the chosen actions and simulated again** for staging, event-timed camera shots and native render/QA. Simulated trial frames are never copied into the final film.

The benchmark is `examples/build_impossible_crossing.py`. Its original premise is a figure deciding how to overcome an impassable barrier and physically claim a glowing mathematical symbol. Failed routes remain visible in the planner report, **not acted out as fake on-screen collision footage**. A later benchmark must actually show a failed attempt and mid-scene replanning if the creative goal requires that.

### Build and test on Windows

```powershell
cd apex-animation-engine
python -m pip install -e ".[dev]"
python -m pytest -q tests/test_autochoreo.py tests/test_route_planner.py
python examples/build_impossible_crossing.py out/impossible_crossing.json
apex validate out/impossible_crossing.json
apex render out/impossible_crossing.json -o out/impossible_crossing.mp4 --scale 0.75 --samples 1 --qa-json out/impossible_crossing_qa.json --review-dir out/m3_review
apex review out/impossible_crossing.json out/m3_review --video out/impossible_crossing.mp4 --qa-json out/impossible_crossing_qa.json
```

The builder writes two files: `out/impossible_crossing.json` (replayable validated APEX film) and `out/impossible_crossing.plan.json` (decision and rejection evidence). The GitHub Action `apex-m3-autochoreo.yml` executes both the physical candidate tests and an actual APEX MP4 render, and keeps the decision trace, video, QA report and review sheet together.

## Acceptance gates

1. At least two tactics are rejected on concrete evidence, not assumed.
2. The chosen tactic performs the objective in native physics in both the trial and the replay.
3. No failed or rejected tactic is silently treated as success.
4. Final project has ordered causal beats, readable event-timed camera shots and an independently passing APEX film QA gate.
5. Reviewers inspect actual video frame by frame and score acting, clarity, weight and timing under `docs/REVIEW_RUBRIC.md`. Technical QA cannot award a professional artistic score.

## Boundaries of current implementation

- One actor, one left-to-right structural barrier, one collectible. Does not yet solve arbitrary level graphs, changing gravity, multi-character combat or multi-room continuity.
- **Not** online mid-scene replanning: rejected tactics are simulated offline before the video starts. The winning plan is still executed by existing APEX actions.
- The planner does not learn from previous films, does not change physics or edit scene obstacles to fake feasibility.
- Runtime `climb`/`vault` are existing APEX character controllers; further visual polish and contacts remain an artistic task.
- The optional crate shift is *only one tested proposal*; do not claim the selected scene visibly uses a crate unless the recorded chosen tactic is `shift_crate_then_climb`.
- This is a reusable tactical component that an OpenRouter Director can request via a **bounded tool contract**, but no autonomous natural-language-to-entire-film integration is claimed here.
- No Railway deployment. All code lives on the APEX development branch and the PR remains draft pending regressions, rendered verification and owner review.

## Next technical upgrades

Graph search through multiple obstacles using recorded world-state constraints; temporal preconditions so plan steps depend on real events; runtime replanning from measured state after failed or intercepted actions; multi-agent joint planning; tool/object affordance learning with no future-state leakage; multiple original 20–30-second acceptance films and consistent human review against the supplied references.
