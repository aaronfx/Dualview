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
