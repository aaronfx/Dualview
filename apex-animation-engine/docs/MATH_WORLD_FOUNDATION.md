# APEX Math World — Foundation M0

## Goal
Make mathematical symbols **physical objects with mathematical meaning**, without replacing the existing APEX engine or confusing story choreography with mathematical proof.

## Current APEX foundation
- `scene/glyphs.py` provides collidable, standable, wieldable, fragmentable and morphable glyphs.
- `render/diagrams.py` draws values from the physics simulation and QA verifies them.
- `physics/world.py` uses Pymunk/Chipmunk2D.
- The standalone M0 module `scene/math_semantics.py` adds bounded symbolic reasoning with SymPy; it **does not yet integrate into the scene runtime, renderer, or AI Director**.

## M0 scope
- Bounded typed AST for integer constants, variables, +, −, ×, constant-denominator division, small nonnegative powers and equality.
- No arbitrary Python code execution, `eval`, `sympify` of user strings, or `parse_expr`.
- Real-number expression identities and one-variable equation solution-set checks.
- Physical beats (grab, throw, ride, push, strike, break, climb, dodge) deliberately do **not** claim mathematical equivalence.
- Six targeted tests cover valid and invalid rewrites, equations, bounds, and story-vs-proof separation.
- Direct dependency when integrating: `sympy>=1.13,<2` in `pyproject.toml`.

## Next implementation gates
1. **M1 Semantic token–glyph bridge.** Give each math token a persistent ID; map AST nodes to the existing glyph renderer. Distinguish the variable `x` from multiplication `×`. Preserve identity across cuts and camera moves.
2. **M2 Event-driven math actions.** Add `combine`, `split`, `simplify`, `balance`, and `solve`. Math proof authorizes a rewrite; a collision/interaction event triggers it. No unmotivated time-based morphing.
3. **M3 Math visualization.** Add vector contours for variables, fractions, parentheses, limits, graphs, radicals, ∑ and ∫. Consider Manim as an offline optional asset/technique source; keep Skia/Pymunk as APEX's core.
4. **M4 AI Director bridge.** The Director plans *mathematical goals and physical beats* in a strict schema. APEX solves staging/timing, checks real math, simulates physical consequences, renders, and runs technical and cinematic QA.
5. **M5 Original proof film.** Build a 15–25-second interaction benchmark: a figure climbs a `+` platform, merges `2+2` into `4`, balances `x+2=5` into `x=3`, then exits through an `=` gate. Only scale to a longer film after motion, equation truth, screen readability and narrative payoffs pass human review.

## Test and integration protocol
- Run `pytest -q tests/test_math_semantics.py` with the engine in editable mode.
- After wiring schema/scene runtime, run full `pytest`, 9-film regression, and 14-transition matrix.
- Add CPU/time budgets in an isolated worker for untrusted AI-generated expressions; AST bounds alone are not a general complexity/time guarantee.
- Keep all development local on Windows first; do not deploy Railway yet.
- No existing APEX files are replaced by this foundation.

## Explicit limits
Only basic polynomial semantics are supported. General calculus, symbolic geometry, multi-variable equation solving, token-based staging and renderer integration are future milestones. A mathematically valid transformation and a physically pleasing film are separate acceptance criteria. Aim for an original interactive-mathematics story, not shot-for-shot imitation of any reference film.
