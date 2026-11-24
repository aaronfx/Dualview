# Milestone 1 (combat): capability audit and design

**Goal.** Two characters can fight: strikes, blocks, dodges, hit reactions, and a fall driven by physics instead of a scripted curve, with hit effects that read clearly. This is the base for the symbolic-world benchmark film. Milestone 2 makes symbols into wieldable props.

## What already exists (reused)

| Need | Existing piece |
|---|---|
| Two characters reacting to each other's events | `wait_for` with `until: event:<type>@<who>`; `char:` targets; `others` on every controller |
| Approaching a target | `_go` (walks, or runs above 250 u/s) and `_face` in `motion/interaction.py` |
| Key poses with timing curves | `Track.of` with `smooth`, `snap`, `back` and `slow_in` interpolation; `motion/library.py` key-pose clips |
| Limb IK (a hand or foot on a target) | `StickmanRig.arm_ik` and `leg_ik` |
| Lying down and getting up | `prone` posture, `_eval_getup` (from face-down only), the `get_up` action |
| Physics world, floor and props | `PhysicsWorld` (pymunk), collision categories |
| Event-driven effects, shake and sound | `pipeline._fx` (flash, burst), camera `shake_events`, `SoundDirector` bindings and the CC0 samples |
| Motion trails | `SkiaRenderer._trail` (ghost limbs for fast limbs) |

## What is missing (built in this milestone)

1. **Combat actions** (`motion/combat.py`, `motion/combat_anim.py`):
   - `strike`, with `move`: jab | cross | hook | uppercut | front_kick | side_kick | roundhouse | sweep;
   - `guard`;
   - `dodge`, with `style`: back | duck;
   - a fighting stance.

   Each strike has phases (anticipation, snap, contact, recovery) with move-specific timing and reach. The attacker closes to range first.
2. **Hit resolution at the moment of contact**, in the simulation and not by script:
   - **whiff:** the target is out of reach, or ducked under a high strike;
   - **blocked:** the target is guarding and facing the attacker;
   - **hit:** with the body part, power and direction.
3. **Hit reactions that interrupt the target:**
   - **flinch** (light);
   - **stagger** (knocked back several steps);
   - **knockdown.**

   Power, the guard, and an optional `reaction` override choose which one. The target's queued actions resume afterwards. A pending `wait_for` is kept.
4. **Physics-driven fall.** A knockdown spawns an 11-part pymunk ragdoll from the target's stance. It has joint limits from the rig, light muscle tone, the hit impulse and the body's own velocity. It falls, tumbles and settles on the real floor and props. Poses are read back from the bodies.
5. **Lying face up** (`supine`) and **getting up from the back** (sit up → squat → stand). The existing get-up only works face down. A ragdoll settles face up or face down depending on the hit.
6. **Hit effects:**
   - an impact star with speed lines at the contact point;
   - a white flash, sized by the hit;
   - camera shake on hits;
   - sparks when a strike is blocked;
   - motion trails on the striking limb;
   - sounds: a swing whoosh, a hit impact, a clang for blocks, a body thud.
7. **QA:**
   - the striking hand or foot reaches its target at contact;
   - fighters don't overlap;
   - ragdoll joints stay inside their limits;
   - nothing sinks through the floor (existing check).

**Not in this milestone.** Weapons and symbol props come in Milestone 2; acrobatics (flips, wall-runs) in Milestone 2; slow motion and impact frames in Milestone 3. The push-and-fall in *The Rescue* keeps its scripted fall, because its pinning test depends on it. It can move to the ragdoll later.

## Design rule (same as *The Rescue*)

The controller decides outcomes in the simulation, using simple body geometry: reach, height, guard and facing. The animator makes the contact look exact at render time: it uses IK to put the fist or foot on the target's body at the contact frame.
