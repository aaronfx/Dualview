# Milestone 1: combat, physics-driven falls and hit effects

Toward the benchmark film (a character fighting a symbolic world) and the 80/100 target. Design and audit: `docs/COMBAT_AUDIT.md`.

## What was built

| Capability | How it works | Where |
|---|---|---|
| Strikes | Eight moves: jab, cross, hook, uppercut, front kick, side kick, roundhouse, sweep. Each has anticipation (wind-up and a dip), a snap with a fast-out curve, a hold on contact, and a return to guard. The attacker closes to the move's range first. Kick range is worked out from leg length and target height | `motion/combat.py` (`MOVES`), `motion/combat_anim.py` |
| Exact contact | The fist or foot is solved with IK onto the target's actual body point at the contact frame. A whiff extends through empty space to full reach | `combat_anim._eval_strike` |
| Outcomes decided in simulation | At contact: **whiff** (out of reach, ducked under a head strike, already down), **blocked** (guarding and facing; sweeps go under), or **hit** with part, power and direction | `combat._resolve_strike` |
| Reactions | Chosen by `power × move weight × attacker strength`, or forced with `reaction`. **flinch** snaps the head back, **stagger** knocks the target back with stepping feet, and a **block** recoils inside the guard. Reactions interrupt the target, whose queue resumes afterwards. A `wait_for` survives unless the hit was its event | `combat._receive` |
| Physics-driven fall | A knockdown builds an 11-part ragdoll from the stance: pivots at the rig joints, rotation limits taken from the rig's bone limits, and damped springs pulling toward a loose sprawl. The whole body is launched, the struck part faster. Gravity, the floor and the walls decide the tumble and where it lands, and whether it ends face up or face down. The fall is sampled and replayed as rig poses | `motion/ragdoll.py` |
| Getting back up | From the front (existing push-up get-up) or **from the back** (new: sit up with the hands behind, squat over the planted feet, stand). A knocked-down character gets up automatically before its next standing action | `combat._getup_back_tick`, `combat_anim._eval_getup_back` |
| Guard and dodges | `guard` is a fighting stance with a bob, and blocks recoil inside it. `dodge` is `back` (out of reach) or `duck` (under head height). Idles between combat moves are drawn in the fighting stance | `combat.py`, `combat_anim.py` |
| Choreography | `next:<event>@<who>` waits only count events after the wait starts, such as "the next strike". Event-timed cuts (`cut_on`) from the setup-solver milestone | `interaction._event_seen`, `scene/solver.resolve_cuts` |
| Hit effects | An impact star (spikes, a ring and a hot core) and a flash sized by power. Sparks on a block. A swoosh arc along the striking fist or foot, sampled from the poses. A floor ring and dust where a body lands. Camera shake scaled to the hit | `render/pipeline.py`, `render/skia_renderer.py` |
| Sound | A whoosh on the swing, an impact scaled by power, a clang on a block, a body thud, a soft whoosh on a dodge (CC0 samples and the synth) | `audio/sound_director.py` |
| QA | `strike_contact` (fist or foot on the struck point at contact), `fighters_do_not_overlap`, `knockdowns_settle` | `qa/inspector.check_combat` |
| AI Director | The prompt documents `strike`, `guard`, `dodge`, `next:` and the combat events; goals and cuts can name them | `ai/director.py`, `scene/goals.py` |

RESULTS_PLACEHOLDER
