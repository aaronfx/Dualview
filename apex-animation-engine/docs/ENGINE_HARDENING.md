# Engine hardening before Milestone 4

This answers the owner's review of Milestones 1–3, which named five priorities:

1. Character–object collisions (critical).
2. Physical-to-animated transitions.
3. Scene-independent QA.
4. Two quality gates.
5. A regression benchmark.

Every number below comes from a real run:
- `tests/test_body_physics.py`
- `tests/test_transitions.py`
- `tests/test_regression_films.py`
- `docs/evidence/regression_baseline.json`

No quality level is claimed. The films still need human review.

## 1. Characters and dynamic objects (critical)

**The problem.** There were two wrong behaviours, one on each branch:
- On this branch, standing characters did not collide with props at all, so props ghosted through bodies.
- On the PR #7 branch, characters collided as infinite-mass kinematic bodies. A scripted walk drove a 110 kg container about 294 units backwards (the reversal reported on PR #7).

**The fix: a bounded-force body.** Every standing character now has a physical body in the physics world:
- It is a capsule from knee height to the shoulders.
- It is tied to the scripted character by a joint whose force is capped at the character's **strength**.
- It collides with props in its depth lane, so props can no longer pass through it.
- It can push with at most that strength. It cannot push with infinite force.

What happens follows from the forces involved; nothing is tuned per scene:

| Situation | Outcome |
|---|---|
| A prop is held by more static friction than the character's strength | It does not move. The character stops at its face (`prop_block`) |
| A prop is light enough | It is pushed along, with no more than the character's strength |
| A moving prop hits the character | The character is displaced by the momentum it takes (`shoved`), and staggers above 160 u/s |
| A walk is planned through a prop | The character steps to a free depth lane first, passes, and returns (`sidestep`); it never touches the prop |
| Props the character is handling (push, lift, lever, carry, pick up), thrown props in flight, and props already overlapping at the start | Excluded from body contact; their own rules apply |

The body has a small contact mass (8), so a walk-in does not kick a prop with a 70 kg body's momentum. When the character is airborne or lying, its body exerts no force. When the character crouches, the body's lower end stays at knee height (it never reaches below a standing body's knees).

**Stick-slip.** A prop only breaks loose past 30 u/s (hysteresis). Without this, the PR #7 reproduction still showed a 467-unit reversal: the prop kept slipping and re-sticking at the friction threshold.

**Evidence** (`tests/test_body_physics.py`):

| Test | Result |
|---|---|
| The PR #7 case: a character walks into a heavy container resting against it | Container moved **0.1 units** (it was ~294 on PR #7). The character stops at its face |
| A container launched at a standing body at 420 u/s | Never passes through it. The body is displaced by less than 160 units |
| A 12 kg crate | Pushed 363 units. The sustained force stays within the character's strength |
| A walk planned through a container | Sidesteps in depth, never touches it, and arrives back in its own lane |

**In the films.** *The Rescue* had characters walking through the support post. Under the new rule, this collision is real. The post is restaged as a column (20 deep) in front of both characters' lanes. This is a staging change to the scene, not an engine workaround: the engine applies the same rule to every scene. JUNO's stop at the bench moved from x≈380 to x=440, because the container now really slides into the lever workspace and stops there. **PR #7's reversal is fixed on this branch.** The PR #7 branch itself was not changed.

## 2. Transitions between moves (`apex/qa/transitions.py`)

Fourteen chains the films never tried. They cross the boundaries between scripted motion and dynamic physics:
- flips into guard and strikes;
- landing rolls;
- a sweep → ragdoll knockdown → get-up → counter-strike;
- a knockdown → get-up → back flip;
- a flying kick → roll;
- duck → uppercut;
- pick up → swing → throw;
- throw → flip;
- climb → flip off → roll → strike;
- vault → strike;
- dodge → flying kick;
- a walk into a heavy crate → sidestep → strike.

All chains share one arena, and nothing is tuned per chain. Each chain is judged by the film inspector's technical checks:
- joint teleports;
- surface penetration;
- 3D body clearance;
- bodies and held props versus structures;
- props versus bodies;
- flip landings;
- feet on tops;
- strike contact;
- knockdowns settling.

The matrix found six engine defects. All are fixed in the engine:

| Chain | Defect | Engine fix |
|---|---|---|
| strike rebound into a crate | A blocked attacker's recoil (and other directly placed moves) went into a prop | Placed moves (lunges, rebounds, dodges, rolls, reactions) stop at a prop's face, as they already did at structures |
| knockdown → get-up | The blend out of a ragdoll sprawl put a knee through the floor | Knees are kept above the floor in that blend |
| pick up → swing | The pick-up target and the swung weapon registered as "props through bodies" | Props being handled are part of the action (engine and QA agree) |
| crouch next to a prop | The crouched body's lower end sank with the pelvis | The lower end stays at knee height |
| dodge → flying kick | The simulation scored a hit the animated leg could not reach (hip to target 115 units, leg 86) | The kick's forward travel ends as the foot arrives, so the simulated and drawn geometry agree |
| flying kick → roll | The roll curled into the opponent's knee: the head leads the pelvis by ~0.7 body heights | A rolling body keeps a body-length further off. A roll stopped short has its plan shortened, so it does not pop forward at its end |

Result: **14/14 chains pass** (`PYTHONPATH=src python -m apex.qa.transitions`; `tests/test_transitions.py`).

## 3. Scene-independent QA

New checks run on every film and every chain, with no exemptions:
- **`body_clearance`**: 3D capsule intersection of torso, head and legs, including crouched and curled bodies.
- **`props_not_through_bodies`**: a prop through a body, in 3D, for every prop and body.
- **`silhouettes_readable`** and **`screen_separation`**: overlap of the characters' silhouettes in camera space, from a raster of what the camera actually shows.
- **`throw_momentum`**: the impulse exchanged in a throw agrees with the tracked motion.
- **`held_props_outside_structures`**.

## 4. Two gates

The QA report now gives two separate verdicts (`QAReport.gates()`):
- **Technical**: physics consistency, valid geometry, no unintended clipping, deterministic replay, and correct event outcomes. Any failure here fails the film.
- **Cinematic (automated part)**: subject in frame, silhouettes readable, screen separation, composition, screen direction across cuts, shot length, and camera roll. A person still has to judge movement, direction, pacing and story, so this gate can say WARN ("look at this"), but it can never certify quality.

A film must pass both gates.

## 5. Regression benchmark (`apex/qa/benchmark.py`)

Seven committed films are re-simulated from their scene files after every change:
- First Exchange
- The Rescue
- Runaway Crate
- Symbol Run
- Glyph Duel
- Foundry Flip
- Gravity Switch 1D

Each film is checked on four things:
- its goals happen, in order;
- every scripted action runs;
- both gates hold;
- goal-time drift (reported, because event-timed cuts depend on it).

A film fails if it meets fewer goals, a check that passed in the baseline now fails, or a gate gets worse. The baseline is `docs/evidence/regression_baseline.json`. The benchmark runs as `tests/test_regression_films.py`.

**It caught a regression on its first run.** The crouch-aware body end (row 4 of the table in §2) reached far below the floor after a climb, because the pelvis is high above the top during a climb. This snagged a glyph in *Glyph Duel* at 13.3 s: a joint teleport, a sliding foot, and a foot off the end of a top. The fix was in the engine: the body end never goes below a standing body's knees. No scene was changed.

| Film | Goals | Technical | Cinematic |
|---|---|---|---|
| First Exchange | 10/10 | PASS | PASS |
| The Rescue | 10/10 | PASS | PASS |
| Runaway Crate | 8/8 | PASS | PASS |
| Symbol Run | 13/13 | PASS | PASS |
| Glyph Duel | 22/22 | PASS | PASS |
| Foundry Flip | (no event goals; all actions run) | PASS | PASS |
| Gravity Switch 1D | (no event goals; all actions run) | PASS | PASS |

## Still open

- **Choreography.** It is still hand-authored. The transition matrix is evidence that unseen combinations hold up, but it is not an AI Director inventing sequences.
- **Body model.** The body is one capsule per character. Arms do not push props, and props do not push individual limbs.
- **Contact mass.** The body's contact mass (8) is a modelling choice: it is a light shell around a strength-limited joint, not the character's mass.
