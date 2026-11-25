# APEX skill inventory and integration audit

Audited source: apex-unified @ ce71c8c02927ac40cef9f48d0b277492ee3a348f.
Scope: current tracked native modules, extension helpers, historical M1/M2
patch documentation, existing test files and production call paths. This is a
source inventory, not fresh proof of every capability. File presence does
not establish runtime activation, artistic quality, or autonomous selection.
No production defaults or physical rules are changed in this audit.

## Evidence and status convention

- N: native implementation present; action or engine feature can be authored.
- B: bounded planner exists, with specific scope and constraints.
- H: helper/interface present; integration not established.
- A: archived separate patch; original source not in unified tree.
- Test names below identify existing evidence locations, not a claim that
  every listed test was rerun on this commit.
- Exposure: schema means available as a primitive to StoryDirector; typed
  mission means explicit dispatch; direct means author or caller selects.
  None of these alone proves autonomous selection across unfamiliar stories.

## Inventory: native engine (paths relative to src/apex)

| Skill family | Source | Existing evidence | Exposure / gap |
|---|---|---|---|
| Rig and IK | rig/stickman.py, rig/ik.py, rig/skeleton.py | test_rig | N, runtime; illustrated retarget unverified |
| Locomotion, turns, contact gait | motion/controller.py, motion/gait.py | test_motion, test_runtime | N, schema; no general route replanning |
| Jump, flip, vault, roll, wall kick, climb | motion/acrobatics.py, motion/acro_anim.py | test_acrobatics, CORE RUN | N, schema; bounded vault/climb objectives |
| Ledge catch, hang, pull up | motion/rescue.py | test_milestone6, Last Retry | N, schema; pull_up objective |
| Strikes, guard, dodge, reactions | motion/combat.py, motion/combat_anim.py | test_combat, CORE RUN | N, schema; attack/block/evade objectives |
| Falling, ragdoll and recovery | motion/ragdoll.py, motion/combat.py | test_combat, test_rescue | N, schema; recover objective |
| Push, lift, lever, pin, crawl, help | motion/interaction.py, motion/interaction_anim.py | test_rescue, The Rescue | N, schema; help_up/lift objectives; generic rescue strategy incomplete |
| Pick up, carry, throw, place | motion/acrobatics.py | test_acrobatics, CORE RUN | N, schema; collect objective; carry-aware routes incomplete |
| Prop and body collisions, depth lanes | motion/acrobatics.py, physics/world.py | test_body_physics, test_acrobatics | N, shared runtime; proactive actor avoidance incomplete |
| Gravity and support changes | physics/gravity.py, motion/frames.py | test_physics, test_escape_1d | N, schema; general gravity route search incomplete |
| Obstacle route preflight | scene/route_planner.py | test_route_planner | B, downward gravity; not full physical proof |
| Automatic obstacle tactic search | scene/autochoreo.py, ai/obstacle_course.py | test_autochoreo, test_obstacle_assessment | B, native rehearsal; not arbitrary world navigation |
| Arcade, orbs, portals, beat sync | motion/arcade.py, scene/level.py, scene/beats.py | test_milestone4 | N, schema; direct staging |
| Breakables, morphs, creatures | scene/runtime.py, motion/creatures.py | test_milestone5 | N, schema; direct staging |
| Acting clips, expression, scarf | motion/library.py, motion/animator.py, motion/secondary.py | test_motion, test_milestone6 | N, schema; contextual acting selection limited |
| Pacing and continuous performance | scene/pacing.py, motion/performance_profile.py, scene/performance_upgrade.py | test_m4_actor_pacing, test_p1_p5_native | N/B, profile and optional rehearsal |
| Character intents and outcome memory | ai/character_brain.py, ai/production_memory.py | test_character_brain, test_director_ensemble_memory | B, caller-supplied perception; not live awareness |
| Multi-character dependency choreography | ai/ensemble_planner.py, scene/ensemble_direction.py | test_director_ensemble_memory, test_p1_p5_native | B, typed mission/optional direct call |
| 14 high-level actor objectives | ai/objective_planner.py | test_objective_planner | B, typed mission; not free-form Studio default |
| Creative plan, story and beat validation | scene/creative.py, qa/creative.py, ai/story_check.py | test_creative_director, test_story_check | B, story archetype coverage limited |
| Event cuts, camera, shot composition | camera/director.py, ai/cinematic_staging.py, scene/film_staging.py | test_cinematic_1c, test_smart_visual_profiles | N/B, Studio staging; native camera consumes project |
| Ink styling, industrial depth, particles | render/ink_character.py, render/industrial_art.py, render/worlds.py, render/particles.py | test_p1_p5_native, test_smart_visual_profiles | N, profiles/backdrops; legacy default outside new brief pathway |
| Sound, music, slow-motion and hit stop | audio/sound_director.py, audio/score.py, render/timewarp.py | test_render_audio_video, test_time_fx | N, schema; authored/event-timed cues |
| Multi-scene continuity and retry | render/film.py, qa/film.py, render/hud.py | test_milestone6, test_film_windows | N, film pipeline; not universal story planner |
| Physical math and signed-term transfer | scene/math_stage.py, scene/math_transfer_runtime.py, scene/math_transposition.py, scene/math_semantics.py | test_math_transposition, test_math_semantics | N, specialized math builder; keep optional domain |
| Geometry, physical contacts, QA | qa/inspector.py, qa/transitions.py | test_qa, test_transitions | N, render/strict rehearsal |
| Presentation and video criticism | qa/presentation_audit.py, qa/director_critic.py, qa/video_critic.py, qa/local_vision_critic.py | test_presentation_audit, test_local_production | B/H, not all presentation checks mandatory in every production |
| Compiler/repair and setup solver | ai/plan_compiler.py, ai/plan_revision.py, scene/solver.py | test_plan_compiler, test_plan_revision, test_setup_solver | B, raw StoryDirector boundary repair limited |
| Local studio, preview and approval | api/local_studio.py, ai/local_production.py | test_local_production, test_integration_together | N/B, local service; monitoring/cancellation gaps |
| Historical film regression | qa/benchmark.py, tests/test_core_run_preservation.py | core_run.json, last_retry.json, the_rescue.json | N, event tests; full rendered visual baseline remains pending |

## Extension kit (src/apex_extension)

registry.py explicitly marks six entries verified with historical native
evidence and seven entries unverified. The separate action catalogue is
not the same registry. Do not convert old evidence into a blanket current
native verification claim.

| Family | Files | Integration state |
|---|---|---|
| World, character and math bridges | world.py, character.py, math_world.py | native bridge tests in test_apex_extension_native; static world perception and bounded memory only |
| Symbolic search and acting helpers | planning.py, acting.py | H, isolated/helper tests; general native scheduling not established |
| Ensemble and world rules | ensemble.py, world_rules.py | H, not evidence of runtime autonomy |
| Story, cinema, timeline | story.py, cinema.py, production.py | H, interfaces; actual native film path separate |
| Rig, assets, rendering | rig.py, assets.py, rendering.py | H/native render bridge; illustrated rig unverified |
| Dialogue, education, charts | dialogue.py, education.py, visualization.py | H, registry marks associated capabilities unverified |
| Quality, assessment and product contract | quality.py, assessment.py, product_sdk.py, registry.py | H/native bridge; reconcile evidence, do not create a third executor |

## Recovered historical packages (outside unified tree)

- apex_causal_choreography_m1.patch: docs/CAUSAL_CHOREOGRAPHY_M1.md
  describes deterministic uniform-cost symbolic search, ordered story
  milestones and unique event witnesses, one active actor. Its original
  src/apex/scene/causal_planner.py and tests are absent from unified tree.
  Original evidence is isolated planner tests, not native video.
- apex_intelligent_choreography_m2_only.patch: docs/TEMPORAL_STAGER_M2.md
  describes pickup/throw goal compilation, event-synchronized defender,
  finite parameter search, stationary-hit versus dodged-miss control.
  Original temporal stager and tests absent. Original report: 24 isolated
  M1+M2 tests; real native physics/render/QA not run. Recover the causal
  control contract; compare against extension planning and native ensemble
  before integrating any source.
- M3-M6 are represented in native autochoreo, pacing, arcade, environment,
  acting and film systems. Historical P1-P5 are additive opt-in upgrades
  documented in REFERENCE_GRADE_INTEGRATION.md.

## Actual production pathways

1. Authored film: ProjectSpec -> SceneRuntime -> render/film or pipeline ->
   Inspector and film QA. CORE RUN is authored event-based choreography.
2. Local Studio brief: api/local_studio.worker -> local_production.create_from_brief
   -> smart_director.plan_story -> StoryDirector.plan -> compile_project ->
   prepare/setup solver. create_from_brief explicitly sets apex_ink,
   continuous and has_scarf=False, then stage_cinematics. It does NOT dispatch
   the typed objective/ensemble mission by default. stage_project preserves
   the supplied project instead.
3. Typed mission: ai/mission.run_mission -> TOOL_SCHEMA -> dispatch ->
   cross_and_collect, objectives, ensemble or rehearse. Native simulation
   and Inspector decide candidate acceptance. It is not the Studio brief path.
4. Bounded autonomous film: ai/autonomous_film.film_from_brief -> parse_brief ->
   constructed world/objectives -> plan_objectives -> plan_ensemble ->
   native rehearsal. It uses ink/continuous, event cameras and payoff; it
   is not a general multiscene natural-language director.
5. Extension backend: registry.ApexBackend.render -> rendering.render_native.
   Product contract and verified list are separate from mission catalogue.

## Audit patch and integration order

The native action catalogue previously omitted the already implemented
objectives and ensemble tools. It now discloses both and their generated
request schemas (lazy imports, no second source of truth for fields).
Mission already dispatches these; this change improves discovery only.
A regression test checks the catalogue against the actual tool schema.

Next: consolidate skill routing through one existing planning boundary,
preserve authored film styles (including scarf choice) rather than blindly
apply a global visual profile, compare M1/M2 contracts with existing
planners, wire C5 environmental awareness to all applicable routes, then
finish C6/C7 and D10. Require held-out scenes, native event traces,
collision/presentation QA, and rendered CORE RUN/Last Retry/Rescue
comparisons before claiming production quality. Do not install historical
patches blindly or replace the native executor.

## Current verification

At audited source ce71c8c, Director boundary workflow 45590566680 logged
25 + 42 = 67 passing targeted tests. Smart Director foundation and
reference-triad creative QA completed successfully. Native math workflow
was still running at inspection. This is not a rerun of the full native
suite or proof of Windows rendering. The inventory/catalogue change itself
requires its own CI verification.


## Full-story routing increment

StoryDirector now accepts optional top-level native_plans in the provider
response. This is planning metadata, not a persisted ProjectSpec field.
The existing objective and ensemble schema/compilers/rehearsal choose action
queues for explicitly delegated actors. Unassigned actors and authored
outcome goals are retained; a delegated actor with a preexisting authored
queue is rejected. The winning actions are merged into the original scene,
then the existing setup solver and dry-run run. Task proofs and dependencies
are checked again after preparation. Native rejection flows back into the
existing bounded repair loop; no new model call or executor is introduced.
Only up to four scenes, 60s each, with explicit goals are delegated in a
single response. Ordinary projects and offline template mode retain their
existing route. This is optional planning delegation, not automatic routing
for every story or continuous runtime awareness. Style preservation and
C5/C6/C7 remain separate work. New fake-provider test uses real native
rehearsal; other tests check scope/queue preservation/rejection.


## Causal choreography consolidation increment (M1/M2)

The existing ensemble planner previously checked each task proof and each
dependency edge independently. Overlapping proof filters could allow one
native event to count as multiple tasks, or inconsistent witness assignments.
A bounded backtracking matcher now establishes one distinct native event per
task, respecting the entire dependency graph. It is shared with the
post-setup full-story verification. Same-tick distinct witnesses remain
allowed as the native event stream is sorted by type within a tick.

M1's pickup-before-throw logical sequence is recovered as throw_at, using
the existing apex_extension.planning uniform-cost search and native actions.
The projectile is explicit, not guessed. Native proof identifies the actual
prop and intended recipient on release; it does NOT certify a collision.
The symbolic initial state is a planning assumption, not a live world
snapshot. Physical preflight and rehearsal still decide feasibility.

M2's original stationary-hit/dodged-miss counterfactual has not been
integrated in this increment. No claim of universal projectile avoidance
or general symbolic world planning. Added causal witness tests and actual
native pickup/release simulation; CI verification required.
