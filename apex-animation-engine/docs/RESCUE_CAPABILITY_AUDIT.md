# *The Rescue*: capability audit (before implementation)

**Brief.** Two original stickman characters enter an industrial workshop.

- One tries to move a heavy metal container, loses control and is trapped beneath a falling support.
- The other notices, runs to help, struggles to lift the obstruction, and uses a nearby lever to free the first.
- The film ends on relief and friendship, with no dialogue.

**Method.** The current engine was tested in two ways *before any new code was written*.

1. **A real AI Director run through OpenRouter.** The story was planned with `anthropic/claude-sonnet-5.5` using the existing `StoryDirector`. Every raw model response was preserved in `docs/ai_runs/rescue_baseline/`. The accepted plan was then rendered and run through QA.
2. **A code-level audit.** Each requirement was checked against the existing motion, physics, camera, render and sound systems.

## 1. Result of the real AI Director run (unchanged engine)

| | |
|---|---|
| Model / provider | `anthropic/claude-sonnet-5.5` via OpenRouter, 3 calls (59 s, 30 s, 23 s), cost below $0.01 |
| Attempt 1 | Rejected by schema validation. It used prop kinds `container` and `support_beam`, which don't exist, and an extra shot field |
| Attempt 2 | Rejected: a `turn` action without `face` |
| Attempt 3 | **Accepted** (validates, and the dry-run simulation passes) |
| Rendered preview (with only the sound names patched, see `PATCHES.md`) | QA **FAILED**: 5 failures, including the missing story events `impact`, `press_contact` and `recovered`; a foot below the floor at t = 0; a joint-speed spike |
| Contact sheet | `docs/media/rescue_baseline_ai_plan_contact_sheet.jpg` |

**What the AI plan actually contains:**

- **Push, trap and lift are only text notes.** They are written as `idle` actions with a note ("strains to push the heavy container…", "trapped beneath the support"). No character touches anything.
- **The lever is a gravity switch** whose effect sets gravity to the same direction it already has.
- **The container and the support are plain crates.** The "support" lies flat on the floor from the start, and nothing falls.
- **The two characters overlap** at the start and the end. Both use the default yellow style.
- **Sound names don't exist.** It referenced `metal_crash`, `lever_clunk` and `soft_chime`, which the sound bank lacks. Validation didn't catch this, so the "accepted" plan couldn't render.

**Conclusion.** "Accepted by validation" is not the same as "represents the story". The model did the best the schema allowed, and the schema cannot express the story.

## 2. Requirement-by-requirement audit

| # | Requirement | Status | Evidence / gap |
|---|---|---|---|
| 1 | Two independent articulated characters | **Partial** | The runtime builds one controller and animator per placement, so several characters can simulate and render. This had never been tested with two. There is no collision or awareness between characters: grounded bodies are kinematic capsules that pass through each other, which is why the baseline overlaps. There is also no way to target a character with `look_at` or camera `include` |
| 2 | Character-specific movement and acting | **Exists** | Per-character proportions and `CharacterStyle` (cadence, stride, lean, arm swing), plus `Performance(emotion=…)` in the motion library |
| 3 | Real interaction with physical objects | **Missing** | Props are dynamic boxes that only gravity and collisions move. Hands can't make contact with props. A grounded character is kinematic, so it can't apply a *finite* force: if it walked into a box it would shove it with infinite strength. There are no container, support or lever prop kinds, and no joints between props (a lever needs a pivot) |
| 4 | Clear cause and effect | **Partial** | The event system and shot exit conditions exist. But each character's action queue is fixed in advance: there is no way to say "B reacts when A becomes trapped". A trap can't be *caused* by physics, because there is no knock-down from a falling object |
| 5 | Coordinated character movements | **Missing** | No synchronisation between characters (wait for another character's event). No contacts between characters, such as a hand on a hand or shoulder for helping up or a hug |
| 6 | Pushing, pulling, lifting, recovery | **Missing** (recovery partly exists) | No push, pull, lift or lever action. No knocked-down, pinned, struggle, crawl-out or get-up-from-the-floor states or clips. **Reusable:** `lose_balance` (losing control), `land_hard`'s absorb and push-off phases, and the `recover_relief` clips (relief acting) |
| 7 | Cinematic, readable camera | **Exists** (small gap) | Shot types, follow, static and dolly moves, `include` objects, and the composition QA rules (subject size, required objects, no roll during fast action). **Gap:** no two-character framing, because `include` can't name a character or a prop |
| 8 | Original, synchronised sound | **Partial** | Event-bound cues, the 32 CC0 samples, panning and reverb exist. **Missing:** a container scrape tied to sliding speed, lever ratchet or creak, strain breaths, and a falling-support crash. **Missing in the AI Director:** validation of sound names |
| 9 | Reuse the APEX renderer | **Exists** (small gap) | The Skia renderer and themes are reused. New prop kinds (container, post, lever) need draw code. Lying and crawling poses are ordinary rig poses |
| — | AI Director natural-language workflow | **Works but outdated** | Live OpenRouter calls work (proven above). **Gaps:** the system prompt lists only 8 old action types; it uses the 1B example; it doesn't validate sound names; it doesn't store the raw responses or the repair log (the test used a wrapper to do that) |

## 3. Proposed implementation (general features, not scene-specific hacks)

1. **Physical interaction layer.**
   - New prop kinds: `container` (heavy, high friction), `post` (a tall support that can topple) and `lever` (a bar pinned at a fulcrum).
   - A bounded **effort force** applied at the character's hand contact. Its strength comes from a per-character parameter, so physics decides whether a push or lift succeeds.
2. **Knock-down from physics.** A heavy prop striking a character above an impulse threshold knocks them down. If the prop then rests on them, they are **pinned**. The trap is *caused* by the simulation, not scripted.
3. **New actions:**
   - `push` and `pull` a prop;
   - `lift` a prop (strain, partial rise; it fails when the prop is too heavy);
   - `operate_lever`;
   - `crawl_out`, `get_up`;
   - `wait_for` (another character's event);
   - `help_up`, a two-character contact;
   - `look_at` targets `char:<id>` and `prop:<id>`.
4. **Motion-library clips:** push strain, lift strain and fail, lever pull, knocked down, pinned struggle, crawl out, get up from prone, reach to help, pulled up, relief and friendship gesture. Contacts may target **another character's** joints.
5. **Camera:** `include` accepts `char:` and `prop:` targets, which gives two-shots.
6. **Renderer:** draw the container, post and lever.
7. **Sound:** a scrape tied to the prop's sliding speed, a lever ratchet, a crash for the falling support, and strain breaths. These come from the CC0 library or the synthesiser.
8. **QA:**
   - hand-to-prop contact distance during pushes, lifts and lever pulls;
   - a prop moves only while it is touched or falling (cause and effect);
   - the pinned character is under the support without penetrating it;
   - the lever angle correlates with the support rising;
   - no interpenetration between the two characters.
9. **AI Director:**
   - generate the action list in the system prompt from the schema;
   - validate sound names and target references;
   - `apex plan --log-dir` stores every raw response, error and accepted plan;
   - a two-character example.

**Then:**

1. Rerun the AI Director on the same story with the upgraded schema, and preserve and render its plan.
2. Produce the final 15–20 s film.
3. If the AI plan needs manual edits, record every edit as a diff. The film is labelled AI-generated only if no edits were made.

## Outcome

The interaction layer was built as proposed, and the film was rendered. Results are in `docs/RESCUE_REPORT.md`.
