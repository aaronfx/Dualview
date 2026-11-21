# Milestone 4: level builder, orbs, portals, beat sync, particles

This milestone builds on the engine hardening (`docs/ENGINE_HARDENING.md`). Everything below was measured on real runs. The test film is *Orb Runner*: a 720p draft, 14.5 s, at 120 bpm. No quality level is claimed; the film needs human review.

| Film | QA | Gates |
|---|---|---|
| *Orb Runner* (`examples/orb_runner.json`, built by `examples/build_orb_runner.py`) | 58 checks: 57 PASS, 1 SKIP (no shot exit conditions declared) | technical PASS, cinematic PASS |

Evidence:
- `docs/evidence/orb_runner_qa.json`
- `docs/evidence/ffprobe_orb_runner.txt`
- `docs/media/orb_runner_key_moments.jpg`

## Design rule

Every new feature acts on the **simulation**, never on an animation clip:
- An orb changes a body's velocity.
- A portal moves a body (a character or a prop) together with its velocity.
- The level builder emits the same platforms the engine already uses.
- The beat grid changes *when* things happen, not *how*.

Everything that follows an orb or a portal (the flight, the landing, a walk carrying on, a prop bouncing) is ordinary physics and controller behaviour. So these features combine with flips, rolls, combat and carrying without special cases.

## 1. Level builder (`scene/level.py`, `EnvironmentSpec.level`)

A level is drawn as a character grid:

| Symbol | Becomes |
|---|---|
| `#` | Solid blocks. Horizontal runs merge, and identical runs stacked vertically merge into one platform |
| `=` | Thin ledges |
| `o` | Jump orb |
| `b` | Boost orb |
| `^` | Launch pad |
| `*` | Collectible |
| `A` … `a` | A linked portal pair. Each portal opens toward its free side |
| Digits | Markers. `placements[].at` places a character on one |

`legend` overrides any symbol's fields (power, flip, angle, height, centre). Expansion happens once at validation; re-validating the scene does not repeat it. A grid that does not fit the room, a portal without a partner, or an unknown symbol is rejected with a message.

## 2. Orbs (`motion/arcade.py`)

| Kind | Effect on the body | Checked by |
|---|---|---|
| `jump` (in the air) | The "up" velocity becomes that of a jump of apex `power`. It can start a flip (angular momentum, as in Milestone 2) | `orb_impulses`: the velocity change is measured from the simulation records and compared with the spec |
| `boost` (in the air) | Adds `power` u/s along the direction of travel | same |
| `pad` (on a surface) | Launches to apex `power`, keeping the run speed. The walk resumes after landing | same |
| `collect` | An event; the orb is taken once for every character | `collectibles_once` |

A walk planned across a block is accepted when a pad lies before the block. It is checked again from where the body lands.

## 3. Portals (`motion/arcade.py`, `scene/runtime.py`)

A body whose centre crosses a portal's plane from its open side, within the portal's height, comes out of the linked portal. Its position and velocity are mapped by a rigid isometry, so **the speed is preserved exactly**.

There are two such isometries. One is a rotation; the other is a mirror about the travel direction followed by a rotation. The engine uses the one that keeps "up" up. Two portals facing the same way therefore mirror the body, like a doorway, instead of turning it upside down. A body falling into an upward-facing portal still comes out of the other one feet first, as the physics says.

Characters:
- A walk into a portal **ends there**. The body carries its momentum out of the other end. If the exit stands on a surface, the character runs straight on and brakes to a stop, unless the next action is another walk. This matters because resuming the old walk could lead straight back into the portal.
- In the air, the same flight carries on: the same tuck timing, and the same pose blended across.

Props:
- Free props go through with their spin, mirrored when the map is a reflection.
- Roped and carried props are excluded. A carried prop jumps with its carrier.

A portal crossing is a **cut**, and nothing is ever interpolated across it:
- the animator does not mix the records on either side;
- the gait planner does not use them;
- prop tracks and the follow camera do not interpolate across it either; the camera jumps with its subject.

The QA teleport check does not excuse the jump. It carries the earlier frame through that portal's own map, and the joints must still agree to within one frame of ordinary motion. `portal_transfers` checks that every crossing keeps the speed, rotates the velocity correctly, and puts the body at the mapped exit point.

## 4. Beat sync (`scene/beats.py`, `SceneSpec.music`)

The beat grid is in **film time**, because that is what the audience hears:
- **`wait_beat`** holds until the n-th next beat. The next action starts on it, to one 240 Hz physics step. With hit-stops or slow motion, film and story time differ, and the warp depends on the simulated events. In that case the scene is re-simulated with the previous pass's warp until the beat waits stop moving (at most 4 passes).
- **Cut snapping.** A shot boundary within half a beat of a beat moves onto it. The exception is a boundary on a portal crossing: the picture already cuts there, and moving it would put two cuts a few frames apart.
- **Music.** A beat-locked groove with a kick on every beat, hats on the off-beats, and a bass note per bar.

QA (all in film time):

| Check | What it measures |
|---|---|
| `beat_cuts` | Snapped cuts on their beat, to half a frame |
| `beat_waits` | Beat waits on their beat, to 1.5 physics steps |
| `music_on_beat` | **Measured from the rendered WAV**: a matched filter finds the kick at each beat |

*Orb Runner*: 3 of 4 cuts snapped (1 kept on a portal crossing), offset 0. Kick found at 26/28 beats, worst offset 0.27 ms.

## 5. Particles (`render/particles.py`)

Bursts are born from engine events:
- orb hits and pick-ups (sparkles);
- portal crossings (a swirl along the portal);
- hard landings (dust);
- blows (sparks).

Each particle is evaluated in closed form at any time: drag-damped velocity plus gravity, fading over its life. Nothing is integrated frame by frame, so any frame renders identically whatever came before it. This is what motion-blur sub-samples, hit-stops and partial re-renders need. Each burst has its own seed (project seed, burst index), so adding one burst never changes another.

QA:
- `particles_deterministic`: two independent builds agree at every sampled frame, evaluated in opposite orders.
- `particle_budget`: at most 900 particles alive at once.

## 6. Engine defects M4 found (fixed in the engine; every film re-checked)

Each of these defects was found by QA or by the regression benchmark, and each fix applies to every scene.

| Defect | Fix |
|---|---|
| **Gait: a braking runner put a lifted foot back down.** The stance fraction was read at the current speed. A walk's stance is longer than a run's, so slowing mid-swing re-entered stance on the plant the foot had left. Found by `foot_sliding` on a pad landing | A step's stance fraction now follows the highest speed since its foot landed: it shrinks when speeding up, but never grows back. The first version used the speed at footfall; the benchmark caught that it broke *Runaway Crate* (accelerating), so it was revised. Test: `test_a_braking_runner_never_puts_a_lifted_foot_back_down` |
| A foot planted past the end of a top the body was running off | Gait plants are bounded by the top's ends |
| Bracing for the ceiling on a rising jump | The airborne brace only turns toward a surface that can hold the body |
| The hand swing at takeoff, stacked on the crouch-to-flight blend, moved a hand 140 units in one frame | The tuck-in now lasts 0.28 s (was 0.2 s). All films still pass |
| `gravity_direction` counted orb and portal impulses as gravity errors | Only the steps that straddle an impulse are left out. That impulse is verified by its own check |

## 7. Results

| Suite | Result |
|---|---|
| `tests/test_milestone4.py` | 15 tests pass |
| Regression benchmark | 8 films (now including *Orb Runner*): all goals met, both gates hold |
| Transition matrix | 14/14 |

## Limits

- **Portals** are flat and non-physical: they are openings, not colliders. A body crossing a portal's back face passes through it. Ropes are not carried through portals.
- **Orbs** are touched by the body capsule (pelvis to neck) or, for pads, by the feet. Limbs alone do not trigger them.
- **Beat sync** times when actions *start*. A move's key frame (for example a jump's takeoff after its crouch) is not yet placed on the beat.
- **`jump_to`** still plans its flight from the target, not from the run-up speed. Running into a `jump_to` loses the run's momentum. This predates M4 and is noted for the next milestone.
- **Camera:** `bound_to_room` keeps a view inside the walls when the camera has no roll. The renderer's perspective can still show a sliver beyond the walls at the near plane.
- **The film** is a short technical showcase: hand-authored choreography on a hand-drawn level. Its artistic quality is not claimed.
