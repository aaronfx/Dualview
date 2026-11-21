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

## Test film: *First Exchange* (original, hand-authored)

| | |
|---|---|
| Video | 1080p, 24 fps, 16.67 s, H.264 + AAC (`docs/evidence/ffprobe_first_exchange.txt`). Delivered separately; MP4s are not committed |
| Source | `examples/first_exchange.json` (built by `examples/build_first_exchange.py`) |
| Who wrote it | **Hand-authored choreography.** The engine decides the outcomes and the timing. No AI planning was used |
| QA | **45 PASS / 2 SKIP / 1 WARN** (`docs/evidence/first_exchange_qa.json`) |
| Strike contact at impact | worst 11.8 units, limit 24 (`strike_contact`) |
| Fighters' closest approach | 58.7 units, limit 28 (`fighters_do_not_overlap`) |
| Audio | 32 cues, each placed at its engine event time; audio and video durations match within 0.7 ms; every frame decodes |
| Tests | **158 passed**, including 7 in `tests/test_combat.py` |

**What happens in it, as decided by the simulation:**
1. KAI's jab is **blocked** (sparks, and the guard recoils).
2. The cross is **ducked** (whiff).
3. RHO's counter-hook **hits** (a flinch).
4. The front kick is **dodged** with a back-step (whiff).
5. RHO's roundhouse is **ducked** (whiff).
6. The uppercut **hits** (a stagger).
7. The sweep **knocks RHO down.** He falls as a ragdoll and settles **face up**.
8. RHO gets up from his back. They fist-bump.

The 6 shot cuts are placed at the simulated events (`cut_on`).

**Evidence:**
- `docs/media/first_exchange_contact_sheet.jpg`
- `docs/media/first_exchange_key_moments.jpg`
- `docs/media/first_exchange_interaction_diagnostics.jpg` (a state timeline per character, and contact error at impact)

## Known defects (honest list)

| # | Defect | Severity |
|---|---|---|
| C1 | **Close exchanges crowd the frame.** Pelvises stay 59 or more apart, but arms and guards overlap in many frames (around 5.0–6.0 s, 7.5 s and 10 s). Both fighters are drawn on one depth plane. This is the same root cause as R2 and R7 in *The Rescue* | Medium |
| C2 | **The fist-bump ending is too tight.** The two figures nearly overlap at 14–16 s | Medium |
| C3 | **The QA flags screen-direction flips** at 5 cuts (WARN). Following KAI, then RHO, who face opposite ways, flips which side each character is on. The camera grammar should keep one side of the action line | Low–medium |
| C4 | **A body lies straight while it waits to settle.** A ragdoll on a flat floor straightens out before the face-up pose blends in. The sprawl springs are too weak to bend the limbs against floor friction | Low |
| C5 | **No hit-stop or slow motion.** Impacts have effects and shake, but no freeze frames or speed ramps (planned for Milestone 3) | Medium |
| C6 | **The opening is long and dark.** The walk-in establishing shot runs 4.2 s, and in the very dark void theme the figures read small | Low |
| C7 | **Choreography is written by hand.** The author picks each move and its `next:` waits. A bad wait leaves a character stuck, though the dry run reports it. There is no automatic choreographer yet | — |
| C8 | **The *Rescue*'s push-and-fall still uses its scripted fall,** kept deliberately because its pinning depends on it | Low |

**No quality level is claimed.** These are technical results, and the score in the roadmap is an estimate until a human reviews it.

