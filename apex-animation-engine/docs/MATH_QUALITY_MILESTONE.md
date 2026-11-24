# Mathematical animation — quality milestone

The professional-quality foundation for APEX Studio / EDU: an autonomous, generalisable linear-equation solver and film
generator that teaches by **transposition**, not a hand-tuned animation for one equation. Branch `apex-math-quality` (on
top of the V2 integration).

## The method: transposition (crossing the `=`)
An equation is solved the way it is taught on a board: a term **crosses the equals sign and its operation inverts**.
`x + 2 = 5` → the `+2` glides across the `=` and becomes `−2` → `x = 5 − 2` → compute → `x = 3`. Nothing is thrown away
or discarded; every symbol on screen is a real algebra step the viewer can follow.

- `+ b` crosses as `− b`  (and `− b` crosses as `+ b`)
- a coefficient `a·` crosses as `÷ a`  — `2x = 8` → `x = 8 ÷ 2` → `x = 4`

## What was built (reusable engine, not hardcoded)
- **Engine `transpose` move** (`schema.TransposeSpec` + `runtime.transpose_tick`) — a new, reusable primitive: a
  kinematic glyph glides along a lifted arc from its position to a target over a duration, triggered by time (`at`) or a
  named event (`on`), and lands exactly on target. The operator's sign flip reuses the existing morph system, so the
  inversion happens *as the term crosses*. This is a general engine capability, usable by any future scene, not
  equation-specific code.
- **`scene/equation_solver.py`** — `solve_plan(a, b, c)` for any `a·x + b = c`. Returns the ordered steps that isolate
  x. Every step is checked twice: exact rational arithmetic keeps the solution, and `math_semantics.verify_rewrite`
  (SymPy) proves before/after equivalence. A false or non-integer step is refused before anything is staged.
- **`examples/build_equation_film.py`** — generates a complete film from `solve_plan`: lays the equation out as glyphs,
  identifies the coefficient / constant / right-hand-side tokens from the layout, and stages each step as the character
  directing the term to cross the `=` (the engine `transpose` move) while its operator inverts (a paired morph) and the
  right side then computes. No per-equation code.

## Equality, demonstrated
Each step keeps the equation true (checked in `equation_solver`), and the film shows *why*: the term does not vanish, it
moves to the other side with its operation inverted — the visible, causal reason the value changes. For `2x+3=11` the
right side passes through the correct intermediate `2x = 8` before `x = 4`.

## Deficiencies addressed (vs the earlier balance scene)
| # | Was | Now |
|---|-----|-----|
| 1 Mechanical/slow motion | long walks and carries | the figure directs; terms glide on smoothstep arcs; ~6.6 s single-step |
| 2 Excess idle | ~5 s standing tail | trimmed to a short beat after the last action |
| 3 Weak acting | flat | study → effort/reach on each cross → shock at the compute → triumph payoff |
| 4 Unconvincing interaction | littered throws | each term is deliberately moved across the `=`; sign inverts on arrival |
| 5 Unclear transforms | one-sided, discarded | transposition reads as real algebra; intermediate shown for two-step |
| 6 Excess glow/trails | energy bloom + smears | no energy core, smears off, screen-fx off |
| 7 Camera crops the equation | tight framing cropped the result | one wide shot sized to the whole equation's extent incl. the crossed terms |
| 8 Weak payoff | lingering debris | lands on the solved `x = N`, triumph beat |

## Generalisation (one generator, no per-equation code)
`x+2=5 → 3`, `x+4=9 → 5`, `2x=8 → 4` (coefficient → `÷`), `2x+3=11 → 4` (two-step, shows `2x=8`), `x−3=4 → 7`
(`−` crosses as `+`). An off-brief `2x+1=7 → 3` also generates and solves.

## Verification
- `tests/test_equation_solver.py` (12): all five equations solve, every step SymPy-verified and balance-preserving.
- `tests/test_equation_film.py` (9): each equation solves by transposition, every compute is caused by a real `transpose`
  crossing (never a timer), the `+`→`−` and coefficient→`÷` inversions happen, the two-step intermediate is shown, and an
  off-brief equation works.
- `tests/test_milestone5.py` (transpose): the engine move glides across and lands exactly on target, lifts on its arc
  (not teleport), inverts the sign on crossing, and can fire from a named event.
- Native regression: full suite re-run with the additive `transpose` feature; the new field/tick are inert unless a prop
  declares `transposes`, so nothing else changes.
- Each render has a QA report (technical/cinematic gates) and a contact sheet.
- Original vs upgraded comparison: `scripts/compare_equation_films.py` (motion analysis from the simulation + a
  synchronised side-by-side contact sheet).

## Honest limitations (not production-certified)
- Glow is reduced but the glyph renderer still blooms; crisper symbol rendering is an engine follow-up.
- A right-hand side that stays multi-digit across more than one step (e.g. `14 → 12 → 4`) is a known follow-up; the five
  benchmark equations do not need it.
- The multiply operator is drawn with the times glyph `x`, visually close to the variable `x`; a distinct `·` for
  implicit multiplication is a rendering follow-up.
- **Automated tests passing is not artistic acceptance.** These MP4s are submitted for human visual review against the
  reference films (particularly *Animation vs. Math*) before the milestone is called complete.
