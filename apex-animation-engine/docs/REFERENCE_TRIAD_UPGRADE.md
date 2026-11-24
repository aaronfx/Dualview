# APEX — Three-reference capability upgrade / executable acceptance contract

## Mission
Upgrade **one standalone APEX engine** so it can create original productions that approach the artistic and technical caliber of the three studied films:
1. *Animation vs. Math* — rules become physically interactive, and mathematics is real.
2. *Animation vs. Geometry Dash* — precise travel, gravity, portals, challenges, rapid reactions and musical rhythm.
3. *The Dark Age — Animator vs. Animation 14* — character-driven conflict across multiple environments, clear emotional intent and a feature-length causal arc.

**Never copy the reference films' frames, characters, choreography, copyrighted sound, or assets.** Re-create the *capabilities*, not the films.

This document distinguishes **implemented**, **under test**, and **not done**. Technical QA is necessary, but it cannot certify artistic equivalence.

## Reusable architecture (one authority for every system)

```text
Story / world rules / character goals
    ↓
AI STORY DIRECTOR (explicit, bounded and repairable plans)
    ↓
CausalBeat graph  ──>  creative-qa (logic, continuity, timing, math)
    ↓
ACTION / STAGING DIRECTOR (next)
    ↓
Scene schema → 240-Hz physics and character rigs (Pymunk, APEX)
    ↓
Skia renderer + cameras + sound + 24/30-fps film timeline
    ↓
Technical QA + cinematic QA + human artistic review
    ↓
Revision plan, selective shot/scene rerender, repeat
```

The scene physics, not the LLM, must remain the authority for collisions, trajectory, falling, mathematical physical-world effects and event outcomes. Simulating and rendering a plan is mandatory before calling it a film.

## Implemented on feature/apex-three-reference-grade (draft PR #10)

- **`scene/creative.py`** — strict multi-scene story beats: causality, prerequisites/effects on persistent narrative state, actors, per-shot timestamps, proof events, movie-clock beat cues, math claims.
- **`qa/creative.py`** — checks that creative plans have valid causal order, scene/actor coverage, state continuity, mathematically proven rewrites, musical event precision and real simulation evidence.
- **`scene/schema.py`** — optional `ProjectSpec.creative_plan`, so existing projects remain valid.
- **`qa/film.py`** — creative QA joins the native film report, with real SceneRuntime events for declared proof events.
- **`cli.py`** — `apex creative-qa film.json [--simulate] [--report report.json]`.
- **`scene/glyphs.py`** — added original physical contours for grouping, algebraic variables, calculus and infinity; these use existing collision, physics and rendering paths.
- **`scene/math_stage.py`** — a bounded AST becomes real APEX ObstacleSpec/PropSpec glyphs, not superficial equation text. Compile can reject incorrect transformations before assets are allocated. The multi-token transformation itself is not yet simulated.
- **`tests/test_creative_storyboard.py`**, **`tests/test_math_stage.py`**, and the prior **`tests/test_math_semantics.py`**.
- **CI**: lightweight story/math tests plus native engine installation and physics integration tests.

**Important:** These are foundations, not three completed reference-quality movies. The math-stage and story authoring still need scene choreography, runtime transforms, shot polish and human acceptance.

## Third-party dependencies, evaluated for fit and licensing

| Project | Use | Integration choice |
|---|---|---|
| SymPy (BSD) | Symbolic expressions, equation solutions and rewrite proof | Required for typed math claims |
| Pymunk / Chipmunk2D (MIT) | Existing physics contacts, constraints and world-state authority | **Keep** as core |
| Manim Community (MIT) | Formula layout, mathematically matched transformations | Study and optionally call as *external asset tool*; do not replace Skia/Pymunk |
| Godot demo projects (MIT for appropriate examples) | Reference patterns for 2D skeleton performance and state animation | Techniques only, not a second runtime |
| Blender (GPL application) | Future camera, Grease Pencil and 3D output pipeline | Optional *separate process*; not required for current local CPU tests |

Do not vendor GPL code or fork an entire animation engine into APEX without an explicit architecture and licensing review.

## Three benchmark acceptance films (to build and render)

### MATH: *The Equation Vault* — 30–45 s original
- Five physical math objects can be stood on, carried or thrown.
- A concrete expression `x + 2 = 5` physically participates in the plot.
- A real action unlocks a transformation to `x = 3`; SymPy verifies the equation *before* the effect.
- The mathematical cause, the actual trigger, the animated transformation and the consequence all occur on screen.
- A character must react with original anticipation and surprise. Symbol identity remains visually traceable.
- **Not yet built:** multi-token physical transform runtime, equation-based environmental state, final benchmark film.

### ARCADE: *Pulse Runner* — 30–45 s original
- At least two genuinely different obstacle patterns and one portal/gravity shift.
- One failed attempt and retry whose starting state is proven equal.
- Each declared music-critical action is within two 24-fps movie frames of a beat, including under slow motion.
- No invisible collision, camera-teleport, impossible gap or off-screen consequence.
- **Existing foundation:** portals, gravity, grid levels, beat clock, retry and film-time effects; needs route/action planning and a polished benchmark.

### EPIC: *CORE RUN — The Return* — 90–150 s original
- At least three spatially distinct environments, two recognizable characters and a rival.
- Across scenes, carryable objects and character motivations do not teleport or spontaneously change.
- The plot has setup, a reversal, a rescue/help action and a visible payoff.
- Contacts, handoffs, falls, camera staging, continuity and layered sound all pass QA.
- **Existing foundation:** CORE RUN and Director's Cut attempts with important known technical defects; must fix them, strengthen acting and complete human review before an acceptance claim.

## Release stages and non-negotiable gates

1. **Engine integrity:** install and run native APEX tests. Lock the existing film regression suite and the transition matrix; repair known baseline failures, not hide them.
2. **Math World runtime:** implement event-driven combine/split/balance/proven morphs using actual colliders, with no expression teleporting.
3. **Action/staging planner:** given a character's intent, obstacle geometry, physical feasibility, target and camera, choose action sequences; reroute on failed simulations. AI never scripts impossible collisions.
4. **Performance polish:** strong key poses, contacts and impulses, weight, reaction lag, distinct personalities, hand-tuned pose clips, physically truthful hits, effects at the correct film time.
5. **Film art:** richer backgrounds and character silhouettes, shot-to-shot spatial continuity, original sound library, strong visual hierarchy and purposeful camera direction.
6. **AI Director integration:** strict tool/action vocabulary; bounded planning + corrective simulation feedback; style bible and persistent character/world state, cost guardrails and versioned drafts.
7. **Real acceptance:** all three films render and decode at 1080p, technical + cinematic automated gates pass, no unresolved major defects, and 2+ human reviewers reach high artistic scores with timestamped notes.

Reference-level quality is **not** a machine-generated score. The existing APEX human-review rubric's 7 categories remain the final artistic gate (character acting, choreography, camera, art, sound, story, emotion). Any sub-8 human rating creates a concrete revision ticket; a valid MP4 alone does not pass.

## How to run new checks (on this branch)

```powershell
cd apex-animation-engine
pip install -e ".[dev]"
pytest -q tests/test_math_semantics.py tests/test_math_stage.py tests/test_creative_storyboard.py
apex creative-qa examples/your_film_with_creative_plan.json --report out/creative.json
apex creative-qa examples/your_film_with_creative_plan.json --simulate --report out/creative_simulated.json
apex film examples/your_film_with_creative_plan.json -o out/film.mp4 --report out/film_qa.json
```

Without a `creative_plan`, creative-qa skips rather than pretending there is a causal proof. Without actual simulation, evidence checks are marked SKIP. A feature only becomes **verified** after executable tests and a human-viewable film.

## Git and deployment discipline
- Current master branch does **not** contain the APEX engine. APEX resides in its long-lived development PR #2.
- PR #9 adds the math semantics M0 base. PR #10 builds on PR #9; merge dependencies in order only once CI and review pass.
- Keep APEX standalone. Develop/test on Windows and GitHub CI first; do not deploy to Railway automatically.
- Preserve all existing movie samples and regression tests. Never force-push or rewrite the owner's branches.
