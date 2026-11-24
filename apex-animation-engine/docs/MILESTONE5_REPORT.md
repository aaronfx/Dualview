# Milestone 5: breakables, morphs, diagram layer, composite creatures

The scope is option 1 of the owner's choice: the planned mechanics, with the three requirements carried over from the Milestone 4 review built into the test film and checked by QA:
1. Environmental art direction.
2. Spatial continuity between connected places.
3. Satisfying endings.

Every number below comes from a real run. No quality level is claimed; the film needs human review.

| Film | QA | Gates |
|---|---|---|
| *The Specimen* (`examples/specimen.json`, built by `examples/build_specimen.py`): 720p draft, 17 s | 52 checks: 51 PASS, 1 SKIP (no shot exit conditions declared) | technical PASS, cinematic PASS |
| *Orb Runner* revised (see §6): 720p, 14.5 s | 59 checks: 58 PASS, 1 SKIP | technical PASS, cinematic PASS |

Evidence:
- `docs/evidence/specimen_qa.json`
- `docs/evidence/orb_runner_qa.json`
- `docs/evidence/ffprobe_specimen.txt`
- `docs/media/specimen_key_moments.jpg`

*The Specimen*: a glyph creature roams a lab at night. It walks into a glass vial, which topples and shatters. ODA picks up a "−", which becomes an "×" in her hand. She throws it, the creature is torn apart into its symbols, and after a beat its body reforms as a "?". ODA walks over and points at it.

## Design rule (as in Milestone 4)

Each mechanic acts on the simulation, and QA checks it against the simulation:
- **Breakables:** a contact impulse breaks a prop.
- **Morphs:** a shape change keeps the motion.
- **Creatures:** joints and bounded forces hold a creature together and move it.
- **Diagrams:** only show measured values.

## 1. Breakables (`BreakSpec`; `scene/runtime.py`, `physics/world.py`)

How a prop breaks:
- **Trigger.** The prop breaks when the contact impulse it takes in one physics step reaches its threshold. The impulse is summed over all of its shapes, because a glyph takes a blow through several strokes at once.
- **Pieces.** A glyph breaks into its strokes, with long strokes cut into runs of at most 4 segments (`glyphs.pieces`; a piece is named `"8#3"`). A box breaks into a `grid` × `grid` of blocks. Each piece's mass is proportional to its stroke length at the prop's real size, or to its area.
- **Before the break.** The pieces are ordinary props from the start, out of play: they don't collide and they ride inside the prop.
- **At the break.** Each piece leaves with the prop's velocity and spin at its own centre of mass, plus a radial scatter. The scatter is proportional to the piece's offset from the prop's centre of mass, and those mass-weighted offsets sum to zero, so it adds no momentum.

New robustness fix: solid slabs now sit behind the floor, walls and ceiling. A body pushed into a thin surface segment (a piece born overlapping the floor, a fast fragment) is pushed back out instead of tunnelling through. The surfaces themselves don't move.

QA:

| Check | What it verifies |
|---|---|
| `breaks_at_threshold` | Every break came from an impulse at or above the prop's threshold |
| `breaks_conserve_momentum` | The pieces' total momentum equals the prop's. Measured: 0 |
| `breaks_continuous` | Each piece starts exactly where it was inside the prop. Measured: 0 units |

## 2. Morphs (`MorphSpec`)

A glyph prop changes into another glyph, either at a time or on an event, with an optional delay. While it changes, the drawing blends stroke by stroke. At the end, the physical shape swaps:
- The mass is kept.
- The centre of mass stays put, its velocity is kept, and the spin is rescaled so the angular momentum is conserved.
- If a structure is in the way (a "+" growing out of a "−" lying on the floor), the new shape pushes itself clear by the smallest nudge that frees it: up first, then sideways. The nudge is recorded.
- If a character is in the way, the swap waits.
- The blend ends exactly where the new shape will sit, and the prop track is cut at the swap, so the drawing never pops.

QA:

| Check | Measured (*The Specimen*) |
|---|---|
| `morphs_conserve_motion` | 6e-17 |
| `morphs_hold_centre` (no shift beyond the recorded nudge) | 4e-16 |
| `morphs_no_pop` | 0.68 units (limit 6) |

## 3. Diagram layer (`DiagramSpec`, `render/diagrams.py`)

Diagrams are annotations drawn over the picture, and none carries a hand-written number:

| Kind | Shows |
|---|---|
| `velocity` | An arrow of the body's velocity, with the speed |
| `trajectory` | A dashed path, drawn as the body travels it |
| `label` | Text that follows a body, filled with live `{speed}`, `{height}`, `{mass}` and `{name}` |
| `measure` | A dimension line with the distance |
| `impulse` | An orb's Δv, a break's impulse, or the blow that tore a creature |

QA:
- **`diagrams_truthful`** re-derives every shown value independently, from the *rendered* body positions. It allows 8% plus 15 u/s for authored acting such as a settle. *The Specimen*: 51 values, worst disagreement 0.
- **`diagrams_in_frame`** (cinematic) checks the annotations stay on screen. *The Specimen*: 94%.

**This check found a real animation defect.** Blending into or out of a flight dragged the body toward the previous pose's frozen end position, so the drawn body lagged and then caught up (1,040 u/s against a physical 613). The fix:
- Coming out of an orb's mid-air jump, only the limbs blend; the body stays where the physics has it.
- Into or out of a flight, the offset at the boundary is blended away instead of a frozen position.

The first version of that fix applied to every blend. The transition matrix and the benchmark caught that it broke rolls, vaults and climbs, which place the body themselves, so it now applies only to flights. All 9 films and 14/14 chains pass.

## 4. Composite creatures (`CreatureSpec`, `motion/creatures.py`)

A creature is a glyph body with glyph limbs (legs, arms, a tail, a head, eyes). Every part is an ordinary glyph prop: it collides with structures, props and the characters' bounded-force bodies, and it is drawn and checked like any prop. The creature adds:
- **Joints:** pivot joints from the body to each part, with rotary springs. A gait drives the legs and arms in turn, paced by the distance travelled; they settle when it stops. Tails are held loosely.
- **A bounded drive:** a horizontal force that follows the path, a lift that carries the whole creature's weight at its standing height, and an upright torque.
- **Tearing:** a contact impulse on any part at or above `breaks` removes every joint and the drive, and the parts fall free.

QA:

| Check | Measured (*The Specimen*) |
|---|---|
| `creature_joints_hold` (largest gap between a joint's two ends) | 0.12 units |
| `creature_breaks_at_threshold` | Torn by 2,815 against 1,800 |
| `creature_follows_path` (largest lag behind the path) | 5.9 units |

## 5. The three carried-forward requirements

| Requirement | What changed | How it is checked |
|---|---|---|
| **Environmental art direction** | Set dressing (`DecorSpec`): windows with a night skyline, wall panels with status lights, screens with live traces, pipes, ceiling lamps with light cones, shelves of glassware, lab benches. A quieter grid (`room.grid_alpha`). Stronger particles: bigger orb, portal and collect bursts, a brighter glow, debris for breaks. Diagram text enlarged for 720p | Human review (the lab in *The Specimen*) |
| **Spatial continuity** | New cinematic check **`causes_on_screen`**: every key cause and effect (break, creature tearing, shape change, throw, both ends of a portal crossing, orb, blow, snap) happens where the camera is looking at that moment. A portal crossing's entry is checked in the frame before the crossing and its exit in the frame after. Cuts on portal crossings, for props as well as characters, are now locked against beat snapping | **It reproduced the owner's *Orb Runner* finding**: the plus's exit from the ceiling portal and IKO's entry were off screen. *Orb Runner* is restaged with a cut on the crossing, and now both films pass |
| **Satisfying endings** | *The Specimen* ends on a payoff: the creature torn apart, its body reforming as "?", and ODA walking over to point at it, with a fade | Human review |

Also new:
- A shot with no character subject (a shot of a vial and a creature) is judged on the objects it lists in `include`.
- A `point` gesture can aim at a moving prop or character.
- `CameraSpec.bound_to_room` was added in Milestone 4.

## 6. Other engine fixes made in this milestone

| Defect | Fix |
|---|---|
| A contact the body rule deliberately ignores (a thrown prop leaving its thrower) was still reported as an impact, so a clang played at every throw | Ignored contacts produce no event |
| The morph overlap test didn't count characters (their physical bodies were skipped) | A character's body counts, except for a prop it is holding or handling |
| Goals could not name a creature, a creature part (`spec.body`) or a fragment (`vial~1`) | Fixed |

## 7. Results

| Suite | Result |
|---|---|
| `tests/test_milestone5.py` | 9 tests pass |
| Regression benchmark | 9 films (now including *The Specimen*): all goals met, both gates hold |
| Transition matrix | 14/14 |

## Limits

- **The "?" punchline** reforms on the body lying where physics left it, so it reads on its side. The engine does not right it, because that wouldn't be physical.
- **Creatures** walk on a flat path: there is no climbing and no stepping off edges, since the lift holds a standing height. They react to blows physically but have no behaviours (fleeing, noticing).
- **Morphs** need glyph props, and a morphing prop cannot also be breakable.
- **Set dressing** is procedural and 2.5D. It is a first step toward the richer worlds (cities, labs, oceans) the owner described; there is no asset pipeline yet.
- **`diagrams_truthful`** passed at 0.079 against 0.08 on one test scene, where a launch-pad takeoff blends into a flight. *The Specimen* has 0. That margin is narrow and worth watching.
- Choreography is still hand-authored.
