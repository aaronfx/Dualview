# Milestone 1D: plan and what was actually built

**Status:** implemented and rendered (`examples/gravity_switch_1d.json`, 30.0 s), awaiting owner review. The review results are in `docs/MILESTONE_STATUS.md`.

## The 30 s story as built

Times come from the simulation (events), not from authoring.

| Time | Beat | Gravity | Engine capability |
|---|---|---|---|
| 0–1.6 | Wide push-in. The room shows the floor switch, the conduit beam, the grab rail, the second switch and a sealed door on the ceiling. AXEL enters | G0 (down) | — |
| 1.6–7.25 | Double take at the switch; cautious approach; hesitant press, with contact at 6.69 | G0 | 1C acting (startle now eased) |
| 7.25–8.95 | Gravity turns +90°. He loses support, falls to the right wall, braces and lands (1341 u/s) | G0 → G1 | 1B physics |
| 8.95–10.85 | Camera rolls with gravity. **Relief beat:** exhale, hands on knees, straighten up (new). Then a double take | G1 | `RECOVER` clip |
| 10.85–13.25 | POV of the sealed door, now high on the far end wall. He points at it. POV of the second switch on the end wall | G1 | POV inserts |
| 13.25–15.9 | Sprints along the wall and **slides under the conduit beam** (16.6 units clearance) | G1 | `duck_slide` |
| 15.9–18.3 | Looks up, crouches, **jumps and slaps the switch mid-air** (17.15), lands | G1 | `jump_to` with an airborne press |
| 18.3–19.75 | Gravity turns **−180°** (clockwise, back through the original "down"). He falls "up" the screen, tumbles feet-first and **catches the rail overhead** (19.65) | G1 → G2 | `grab_swing`: catch |
| 19.75–22.45 | Pumps the swing; the camera turns with gravity; he **lets go at the top of the swing** (21.22), drops and lands by the door (1524 u/s) | G2 | `grab_swing`: swing, release |
| 22.45–25.4 | Relief beat. He looks back up at the rail. The seal has retracted (unlocked at 19.25) and the **door slides open** (22.65) | G2 | door state machine |
| 25.4–30 | Turns, walks into the doorway and fades into the light (`exit_reached` 26.65). The room is left empty, the doorway glowing | G2 | `reach_exit` |

## Deviations from the original plan, and why

| Plan | Built | Reason |
|---|---|---|
| G2 = ceiling, a 180° rotation counted from the original | G2 = **left wall**: −180° relative to G1 (a true reversal of the preceding state), −90° relative to the original | It makes the second change a reversal of the first, as the story asks. The jump spot is near the ceiling, so a "toward the ceiling" gravity would have meant a tiny fall. The relative/original distinction is now explicit in the data (`rel_prev_deg`, `rel_original_deg`). |
| Exit on the right wall | Exit **on the ceiling, next to the left wall** | In G0 and G1 the door is unreachable: a "sealed door far above" that motivates the second switch. In G2 it stands at the base of a side wall, so it is a door you can walk through. |
| Crate in the path, slide under it | Slide under a **fixed conduit beam** spanning the room depth | A crate rests *on* the floor in any gravity, so there is nothing to slide under. The beam is a solid static collider, present and visible from the establishing shot. |
| Grab the handle rail next to the door | Grab a **rail (bar) mid-room** on the fall path | The rail turns a dangerous 1100-unit fall into a catch and swing. It is placed on the hands' actual (simulated) path. |
| Release on the swing angle while still moving | Release **at the top of the swing** | Letting go mid-swing threw him into the ceiling (a graze, detected). Letting go at the apex is the clean dismount. |

## Engineering delivered

- **Schema**:
  - `GravityEffect.rotate_deg` / `turn`;
  - `SwitchSpec.surface`;
  - `ObstacleSpec` (beam, bar);
  - `ExitSpec.unlock_on` / `open_radius`;
  - the actions `duck_slide`, `jump_to`, `grab_swing`, `reach_exit`;
  - the `bar:<id>` target;
  - `CameraSpec.roll_rate`.
- **Physics**:
  - signed sweeps;
  - `angle_unwrapped`;
  - `report()`;
  - static boxes;
  - pivot pins for the grip;
  - COM impulses for pumping.
- **Controller**:
  - slide;
  - standing or running `jump_to`, with a closest-approach mid-air press;
  - the armed grab, a feet-first tumble with clearance gating, a hands-overhead catch with absorption, pumping and the apex dismount;
  - the forced relief beat after hard landings;
  - "graze" contacts that are not landings.
- **Animator**:
  - clips for slide, crouch and swing, plus mid-air slap and bar reach;
  - the grip as a hard constraint after blending;
  - the ground clamp after blending;
  - hands that brace on surfaces instead of passing through them;
  - the eased startle;
  - the relief clip.
- **Runtime**: the door state machine, door events and exit portals (the scarf and QA allow the open doorway).
- **Renderer**:
  - switches on any surface;
  - beams and rails;
  - door states (bars retract and turn green, the leaf slides back, light falls off into the corridor);
  - fade into the light;
  - interior clip;
  - contact shadows on every surface;
  - rings and flashes on any surface.
- **Audio**: slide, clank, unlock, door and resolve; a two-act adaptive score that resolves to D major on `exit_reached`.
- **QA (new)**:
  - `gravity_angle_report`;
  - `camera_roll_follows_gravity_direction`;
  - `landings_on_supporting_surfaces`;
  - `hand_on_switch_at_contact`;
  - `grip_attachment`;
  - `swing_energy_conserved` (net of pumping work);
  - `obstacle_clearance`;
  - `door_state_machine`.
- **Tests**: `tests/test_escape_1d.py` (22 tests).
