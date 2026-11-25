# Capability consolidation — first regression boundary

Baseline: apex-unified 57eacf7. Prior Windows evidence: 37 focused tests passed;
the obstacle-course planner and native rescue renderer ran locally. These do not
prove general autonomous film production or universal collision avoidance.

## Source audit
Local Studio calls local_production.create_from_brief -> smart_director.plan_story
-> StoryDirector.plan. The raw provider response previously went directly into
ProjectSpec validation; compile_scene requires an already valid project. That
made the two recorded errors (object camera target, missing lift target) impossible
to repair locally on this path. The existing director already supports JSON
patches against its prior response: short repair responses alone are not evidence
of a patch-handling defect.

The new compile_project boundary retains native validation and invokes existing
deterministic repair functions only for the two observed failures. Ambiguous
lift targets are refused; known camera objects are kept in frame. Valid projects
are unchanged. Compiler repairs are recorded alongside each attempt. Other
invalid instructions still follow the existing bounded provider repair loop.
No movement, physics, or QA thresholds are modified.

## Permanent acceptance matrix (not yet all verified)
| Fixture | Acceptance obligation |
| --- | --- |
| CORE RUN Director's Cut | Preserve parkour, combat, cooperative recovery, concurrent acting; compare original authored scenes and new Director output separately. |
| The Last Retry | Preserve multi-scene continuity, transitions and character state. |
| Autonomous obstacle course | Preserve dimensions, chosen/rejected tactics, event-derived ending; reject grazing, check visible support and whole-body contact. |
| The Rescue | Preserve physical causality, failed lift, lever, release and recovery; inspect apparent crate/body intersections, intentional contact and ending. |
| Math transposition | Preserve signed intermediate expression, sign inversion and final evaluation. |
| Raw AI boundary | Fake provider: repair the two reported failures before a second call, reject ambiguous targets, keep all other native validation. |

Do not conflate authored choreography with runtime autonomous behaviour.
The earlier videos are benchmark evidence, not proof all action pathways already
share a universal collision/avoidance controller. D10 monitoring/cancellation,
full mission-tool integration, proactive multi-actor avoidance, native visual
regression and live paid E2E remain outside this patch.

No paid AI calls or deployment are required for these regression tests.


## Historical CORE RUN audit and second boundary patch

Source checked against the unified tree at de88d32 and the builder history:
- 9669f014: strikes at props, failed and assisted get-up, City and Tower.
- d4912dd2: assisted recovery grip/height and blocked strike recoil fixes.
- fda0ff1d: vault clearance and hand/foot staging; authored lanes and approaches.
- f5d7d5f2: carried props during aerial motion, faster pacing, depth-aware throws.
- dff43e8f: carried props through exits and coordinated canyon/drone action.

These capabilities remain visible in examples/build_core_run.py, core_run.json,
motion/combat.py, motion/interaction.py, motion/rescue.py, motion/controller.py,
motion/acrobatics.py and SceneRuntime. CORE RUN has five authored action queues
with explicit movement coordinates, clip choices, strike combinations and
event waits. The action catalogue already enumerates the native ActionType
schema. The missing capability is general high-level orchestration: the
objective planner exposes seven kinds, and CharacterBrain chooses from six
intents using a snapshot supplied by the caller. This is not yet continuous
runtime perception or independent combat decision-making.

Existing qa/benchmark.py and test_regression_films.py already cover Last Retry
and The Rescue. CORE RUN was not in that film registry. The new
test_core_run_preservation.py freezes independent event obligations for its
five scenes and ensures the action/clip catalogue covers all three historical
films. It reuses native simulation, not another choreography engine.

The presentation overlap detector previously waived collisions globally
within 1.6 seconds of any intentional contact. It now scopes that same window
to identified actor pairs and counts each bad frame once. Tests reproduce
unrelated third-party overlap, isolated prop events and intended pair contact.
This is a detection correction, not new physics or a proof of full silhouette
clearance. The Local Studio presentation audit is not yet a mandatory gate;
the physical root causes and rendered reference comparisons still need work.


## Third patch: align historical fixtures, broaden typed objective access

The previous CI run exposed an omitted Skia Linux dependency (libEGL.so.1)
and two new assertions that expected the wrong exit actor. The original
CORE RUN builder's ENDS table closes Canyon on PELL's exit and Arena on
IKO's exit; Tower closes on PELL. The tests now assert the original
terminal events, not a new exit order. Whether every actor exits before
the cut is a separate continuity issue, not certified here.

The existing ActorObjective schema now exposes vault, block, evade, recover,
pull_up, celebrate and lift. These compile into existing native action queues
and run through the same bounded ensemble rehearsal. Successful defense
requires actual block_hit/evaded events from the named opponent; lift requires
lift_ok, and recovery requires stood_up. Existing attack, climb and hand-grab
proofs now identify their targets. The mission tool schema is generated from
ActorObjective, so these types become visible to that planner without another
executor. Full-story Local Studio still uses StoryDirector; this does not claim
automatic high-level objective selection for every free-form story.

The added tests exercise all seven new compiler mappings, reject unsupported
target combinations and simulate a real native block with a retained opponent
action. No existing motion controller, authored film, or QA threshold is changed.


## Fourth patch: shared controller multi-prop awareness

The existing native Acro mixin already checks structure paths, guards against
body/prop intersections, and selects alternate depth lanes around props.
The planner selected a lane against all obstacles but the hold/release logic
tracked only one. Both preplanned and reactive sidesteps now retain every
blocker; forward motion waits for depth clearance of all and the home lane
is restored only when all active blockers are safely past. The reactive path
also explicitly includes the actual contact prop. Avoidance events already
emitted by the engine are now recognized by the native event contract.

Added a real two-container native simulation and event-contract regression.
This is physical 2.5D avoidance, not a claim that all screen-space overlaps
are eliminated. Existing authored lane choices and structure traversal
semantics remain unchanged. No new controller or physics engine.
