# Milestone 1D: preparation plan (30 s Gravity Switch story)

**Status: prepared, not started.** The sequencing rule for this assignment says 1D starts only after the 14 s 1C sequence (`examples/gravity_switch_1c.json`) passes review. This file records what 1D needs, so work can begin right after that sign-off. Nothing here is claimed as done.

## Story (30 s, continuous room, two gravity reversals)

| Time | Beat | Gravity | New engine capability |
|---|---|---|---|
| 0–14 | 1C sequence: notice → hesitant press → fall to the right wall → recover → notice exit → point | G0 → G1 (right wall) | none (reuse) |
| 14–17 | Run along the new floor (the right wall) toward the door; a crate slides into the path | G1 | prop-aware path, `duck_slide` |
| 17–19.5 | Slide under the crate, pop up | G1 | `duck_slide` (low capsule, hands on surface) |
| 19.5–22 | Door is sealed; a second switch sits on the ceiling-side panel; jump and slap it | G1 → G2 (ceiling) | `jump_to` with mid-air `press` (hand IK to switch in flight) |
| 22–25 | Gravity reverses to the ceiling; grabs the door handle rail while falling "up" | G2 | `grab_swing`: hand IK lock plus pendulum about the grip |
| 25–28 | Swings, releases at the apex, lands beside the door on the ceiling | G2 | release impulse, then existing brace and landing |
| 28–30 | Seal bars retract; steps through; door light on the closing frame | G2 | door state machine (sealed → open), `reach_exit` exit condition |

## Engineering tasks

1. **Schema.** Add the actions `duck_slide`, `jump_to`, `grab_swing{anchor, release_angle}` and `reach_exit`. Add an `ExitSpec.unlock_on` event and the exit condition `event:exit_reached`.
2. **Controller.**
   - `duck_slide` is a kinematic grounded state: a lowered capsule, friction-decayed speed, a clearance check against prop AABBs.
   - `grab_swing` is a dynamic pendulum. It constrains the pymunk body to the grip with a pin joint. Release happens on the authored angle, or when the swing reaches it.
   - An airborne `press`: hand IK to the switch while the body follows its ballistic path. Contact time is solved from the trajectory instead of authored.
3. **Animator.** Clips for slide (lead leg extended, trailing hand dragging), hang/swing (arms locked, legs trailing by follow-through and swing phase), release tuck and door push.
4. **Physics.**
   - Prop paths must be tested against the slide clearance; the inspector gets a `clearance_violation` check.
   - G2 is a 180° transition. `gravity_roll` is now wrapped and the roll spring takes the shortest path, fixed in 1C because the old code would have spun 270°.
5. **Camera.**
   - Hand-off from the 1C `s6` gravity-aligned roll into tracking shots.
   - A second roll of 180° during G2. Choose the turn direction for continuity: keep the door on screen right.
   - An insert of the hand grabbing the rail.
6. **Audio.** Slide scrape, metal grab clank, door unlock chord. The music resolves to the tonic only on `exit_reached`.
7. **QA additions.**
   - Grip drift: hand to anchor distance while swinging (< 1.5 u).
   - Slide clearance.
   - Roll direction consistency across both reversals.
   - Door visibility in at least one frame of every shot after `notice exit`.

## Acceptance (not to be claimed without the rendered video)

- A playable 30 s 1080p MP4 with full-decode verification and a contact sheet every 0.5 s.
- Every inspector check passes, including the new ones.
- A separate subjective review of acting, action clarity, staging, continuity and emotional readability, written after viewing the actual render, plus a defect list.
