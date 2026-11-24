# Mathematical animation — quality milestone

The professional-quality foundation for APEX Studio / EDU: an autonomous, generalisable linear-equation solver and film
generator, not a hand-tuned animation for one equation. Branch `apex-math-quality` (on top of the V2 integration).

## What was built (reusable engine, not hardcoded)
- **`scene/equation_solver.py`** — `solve_plan(a, b, c)` for any `a*x + b = c`. Returns the ordered steps that isolate x
  (subtract the constant from both sides, then divide both sides by the coefficient). Every step is checked twice: exact
  rational arithmetic keeps the solution, and `math_semantics.verify_rewrite` (SymPy) proves before/after equivalence. A
  false or non-integer step is refused before anything is staged.
- **`examples/build_equation_film.py`** — generates a complete film from `solve_plan`: lays the equation out as physical
  glyphs, identifies the coefficient / constant / right-hand-side tokens from the layout, and stages each step as the
  character removing a term from the left while the right side changes by the same amount **on the same throw event**.
  Both sides change together → equality is preserved and visible; every transformation is caused by a real, verified
  action, never a timer. A measure-then-rebuild pass trims idle time.

## Equality, demonstrated
Each step keeps `left value == right value` (checked in `equation_solver`). The film shows the constant leaving the left
and the right side dropping by the same amount in one motion — that is *why* subtracting the same amount from both sides
keeps the equation true. For `2x+3=11` the right side passes through the correct intermediate `2x = 8` before `x = 4`.

## Deficiencies addressed (vs the earlier balance scene)
| # | Was | Now |
|---|-----|-----|
| 1 Mechanical/slow motion | run 260, long carries | run 360, tighter walks |
| 2 Excess idle | ~5 s standing tail | duration trimmed to ~2.4 s after the last action |
| 6 Excess glow/trails | energy bloom + smears | no energy core, smears off, screen-fx off |
| 7 Camera crops the equation | tight framing cropped the result | one wide shot sized to the whole equation's extent |
| 5 Unclear transforms | one-sided, littered | both sides change together on a verified event; terms thrown clear |
| 8 Weak payoff | lingering debris | lands on the solved `x = N`, triumph beat |

Acting (3, study/effort/triumph) uses existing clips; richer emotional performance and a literal tilting balance beam
are the next pass.

## Generalisation (actual 1080p MP4s)
Rendered from the single generator, no per-equation code:
`x+2=5 → 3`, `x+4=9 → 5`, `2x=8 → 4`, `2x+3=11 → 4`, `x−3=4 → 7`, and off-brief `2x+1=7 → 3`.

## Verification
- `tests/test_equation_solver.py` (12) and `tests/test_equation_film.py` (7): all five equations solve, every step is
  SymPy-verified and balance-preserving, every morph is caused by a character throw, the two-step intermediate is shown,
  and an off-brief equation also works.
- Native regression: **335 passed** with the V2 integration + engine fix; the additive math modules change nothing else.
- Each render has a QA report (technical/cinematic gates) and a contact sheet.
- Original vs upgraded comparison: `scripts/compare_equation_films.py` (motion analysis from the simulation + a
  synchronised side-by-side contact sheet).

## Honest limitations (not production-certified)
- Glow is reduced but the glyph renderer still blooms; crisper symbol rendering is an engine follow-up.
- A right-hand side that stays multi-digit across more than one step (e.g. `14 → 12 → 4`) is a known follow-up; the five
  benchmark equations do not need it.
- The balance is shown by synchronised both-sides change; a literal tilting beam that visibly tips on a one-sided move
  (the strongest "why") is the next enhancement.
- **Automated tests passing is not artistic acceptance.** These MP4s are submitted for human visual review against the
  reference films (particularly *Animation vs. Math*) before the milestone is called complete.
