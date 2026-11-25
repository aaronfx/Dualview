# APEX — Universal obstacle assessment and movement selection

The autonomous pipeline must **adapt its movement to unfamiliar obstacle geometry**, not have the geometry reshaped
to suit one tactic. This document records the root-cause fixes, how the assessment works, what is tested, and the
current capability boundaries (stated honestly, not concealed).

## The regression fixture is fixed, not the obstacles

`examples/autonomous_obstacle_course.py` holds a rooftop course of **80-unit-wide pillars** of different heights,
gaps and positions. The dimensions are deliberately fixed. The engine must assess each obstacle and choose a tactic
that clears it; the course is never widened or lowered to make a tactic pass. `tests/test_obstacle_assessment.py`
keeps these 80-wide pillars (and harder variants) as the autonomous-adaptation fixture.

## How a movement is selected (native autochoreo + full-plan validation)

Per obstacle, the native `autochoreo` tactic search proposes `direct_run`, `low_jump`, `powered_jump`, `vault`,
`climb_then_drop` and a crate-assisted climb, **simulates each at 240 Hz**, and rejects the infeasible ones. A tactic
is rejected when it:

- is geometrically impossible (body would cross the solid obstacle; obstacle too tall to vault);
- produces a controller violation (would walk into a structure);
- **grazes the obstacle** — an *uncontrolled body-vs-structure collision* mid-move. A graze means the body did not
  clear the obstacle, so the tactic is not a valid clearance and is rejected (new).

`plan_course` then does **full-plan validation with dynamic re-selection**: a tactic that is clean when a segment is
rehearsed in isolation (actor at rest) can still graze once *chained*, because the actor arrives with real forward
momentum. The whole scene is simulated; any grazing tactic is excluded for that obstacle (`Objective.exclude_tactics`)
and the segment is re-planned with the next feasible native tactic. This repeats until the traversal is graze-free,
or raises if an obstacle has no clean tactic left.

The assessment therefore considers, through real simulation rather than a hand-coded rule: obstacle **height**
(hurdle vs climb), **width / landing space** (a top too narrow to stand on is climbed-and-dropped, not stood upon,
so a planted foot never hangs past the edge), **approach velocity** (the chained-momentum graze check), the actor's
**reach and jump apex** (`max_jump_apex`), and (see boundaries) carried objects and nearby characters.

## The five reported root causes

1. **Airborne collision impulse read as a gravity_direction failure.** *Legitimate contact or defect?* — **Defect.**
   The impulse was a real `graze`: the hurdle trajectory clipped the pillar. It is no longer accepted as a
   clearance; the engine climbs the pillar instead, and the spurious gravity_direction spike disappears.
2. **Foot placement beyond narrow platform edges (`feet_on_tops`).** Fixed by adaptation: a tall 80-wide pillar is
   climbed-and-dropped, not stood on, so no planted foot overhangs a too-narrow top.
3. **Surface penetration during climbing.** The climb itself is clean (0.0 penetration in isolation and on the
   fixture). Penetration is never concealed — it drives re-selection / honest failure.
4. **Incorrect movement-strategy selection for geometry.** Fixed: the graze rejection makes the search select the
   tactic that actually clears each obstacle (climb the tall/narrow, hurdle the low).
5. **Failure to dynamically select alternative navigation strategies.** Fixed: full-plan validation excludes a
   grazing tactic and re-plans with the next native tactic; when none clears, it **stops** (raises) rather than
   walking through — the Director must reroute or stop.

## Test matrix (`tests/test_obstacle_assessment.py`)

| Configuration | Expected behaviour | Status |
| --- | --- | --- |
| 80-wide pillars, varied height (3 fixtures) | adapt (climb tall/narrow, hurdle low), full QA gate passes | tested |
| Low narrow barrier | hurdled (jump) | tested |
| Tall narrow pillar | climbed | tested |
| Tall pillar a hurdle would graze | re-selected to climb (no uncontrolled contact) | tested |
| Consecutive obstacles, different rooftop gaps | chained clean traversal | tested (fixtures) |
| Physically impossible crossing (500-tall wall) | honest STOP (raises), never a walk-through | tested |
| Other character blocking the path (stationary) | runner stops at the body gap, no pass-through | tested |
| Two moving characters converging | never interpenetrate (native body collision) | tested |

## Collision prevention vs. intelligent avoidance (multi-character)

The engine has **collision prevention** (reactive): a character in another's lane is never passed through — the
mover stops at the body gap (`body_block`). It does **not** yet have **intelligent avoidance** (proactive): a
blocked actor does not re-plan a path *around* the obstruction, it stops. `tests/test_obstacle_assessment.py`
(`test_multichar_course_collision_prevention_is_not_intelligent_avoidance`) asserts both halves of that boundary so
it is documented in code, not implied.

## Unresolved limitations (stated honestly, QA unweakened)

These are real and are **not** hidden by relaxing a threshold, a camera angle, a depth offset or an effect. The QA
thresholds are unchanged; where a limitation would show, the check still fails rather than being silenced.

1. **Marginal surface penetration on some synthetic chained geometries.** A clean single climb penetrates the
   structure by 0.0 units, and the shipped 80-wide fixtures and the example film pass `surface_penetration`
   cleanly. On certain *synthetic* back-to-back layouts a planted toe can dip ~0.8 units past the 4.0-unit
   threshold during a fast plant on the approach to a climb (e.g. a 120-tall pillar immediately after a long run).
   This is a foot-plant easing issue in the approach, not a walk-through, and the QA check correctly reports it.
   The principled fix (easing the approach-plant, or a stricter per-tactic landing-space check) is a defined next
   step; it is **not** patched by loosening `surface_penetration`.
2. **Carried-object clearance.** The actor picks up and carries a prop correctly, and when it meets an obstacle
   while carrying it **stops safely (bumps, no pass-through, `held_props_outside_structures` holds)** rather than
   hurdling with its hands full. Autonomous *carry-aware* tactic selection (set the prop down, or reroute, then
   continue) is not yet wired into the assessment.
3. **Self-propelled / drifting moving obstacles.** A prop cannot be given an initial drift velocity through the
   scene schema (props move only under physics — gravity or being pushed), so a self-propelled moving *obstacle* is
   not yet expressible. Dynamic prop-vs-body non-penetration **is** covered natively (`props_not_through_bodies`),
   and moving *characters* in the path are handled by body collision (tested).

Nothing above weakens a QA threshold, conceals penetration behind camera angles / depth offsets / effects, or
discards a difficult fixture.
