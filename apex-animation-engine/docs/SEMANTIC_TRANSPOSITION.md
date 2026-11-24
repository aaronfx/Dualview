# Semantic transposition (development candidate)

Base: Studio/EDU V2 f5b28cc; no merge of PR #12.

Root cause: math_stage.plan_balance aligns individual glyph prefixes and
refuses to add glyphs to the destination side. build_balance_equation throws
away '+' independently, then throws '2', triggering morph 5 -> 3.
Its regression explicitly expects both throws. SymPy's endpoint proof
does not prove the intervening visual action.

New foundation:
- math_transposition: AST-derived inverse operation, intermediate equation,
  separate exact evaluation, two SymPy proofs, stable term identity.
- glyphs: numeric groups share native stroke/collision geometry; inversion
  retains digit geometry throughout morph.
- transposition_stage: native PropSpecs with one signed-term prop and
  reserved destination to the right of the RHS.
- Regression contracts cover different magnitudes, negative answers,
  subtraction, zero, unsupported syntax, and grouping.

NOT CERTIFIED: Runtime placement, authenticated evaluation, intermediate
dwell, actual native simulation, MP4 rendering and frame inspection remain
required. Do not advertise as a verified V2 capability. Legacy planner and
regression contracts remain unchanged.

## Native integration candidate
Opt-in MathTransferSpec compiles a single signed prop and a hidden expression
body. The native runtime checks pickup, actual crossing, inverse morph,
seated placement and a minimum dwell, then an actor's point event authorizes
merging the two operands into the identical RHS geometry. The existing
native morph engine evaluates that expression. A frame-state regression
requires the intermediate and final equations to exist visibly in the
simulation. This is still a candidate until native tests and rendered frames
have been reviewed; no verified registry entry is added.

Build: python examples/build_semantic_transposition.py out/transpose.json
Render: apex render out/transpose.json -o out/transpose.mp4 --scale 0.75 --samples 1 --qa-json out/transpose_qa.json --review-dir out/transpose_review
