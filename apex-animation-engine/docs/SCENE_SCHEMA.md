# APEX scene schema v0.1

The full machine-readable JSON Schema comes from `apex schema` (or `GET /schema`). It is generated from the pydantic models in `src/apex/scene/schema.py`. Unknown fields are rejected everywhere (`extra="forbid"`).

## ProjectSpec

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `"0.1"` | Must match the engine |
| `id`, `title` | str | |
| `fps` | 24 \| 30 | |
| `width`, `height` | int | Output resolution |
| `seed` | int | Deterministic procedural and audio seed |
| `characters[]` | CharacterSpec | `id`, `name`, `rig: "stickman"`, `proportions{}` (bone-length overrides), `style` (colours, limb width, movement signature: `cadence_scale`, `stride_scale`, `lean_scale`, `arm_swing_scale`) |
| `environments[]` | EnvironmentSpec | `room{width,height,depth_*}`, `gravity [gx,gy]`, `switches[]`, `props[]`, `exits[]`, `obstacles[]`, `dust` (particle count, 0 = off) |
| `scenes[]` | SceneSpec | See below |

Validation covers duplicate ids, unknown references (environment, character, switch, camera target, action `target`) and schema version.

## SwitchSpec, ExitSpec and ObstacleSpec

- **SwitchSpec** `{id, surface: floor|wall_left|wall_right|ceiling, x, height, effect}`. `x` is the position *along* its surface: world x for floor and ceiling, world y for the walls. `height` is the button's distance from that surface.
- **ExitSpec** `{id, surface, s, width, sealed, unlock_on?, open_radius}`. `s` uses the same along-surface convention.
  - `unlock_on: "switch:<id>"` releases the seal once that switch's gravity change has settled.
  - State machine: `sealed → unlocking (0.7 s, bars retract) → unlocked → opening (0.6 s, when a grounded character is within open_radius) → open → exited → closing (0.75 s after the exit, 0.5 s long) → closed`.
- **ObstacleSpec** `{id, kind: beam|bar, center, size}` describes structures spanning the room depth.
  - A `beam` is a solid static collider.
  - A `bar` is a grab rail: a grip anchor for `grab_swing`, not a collider.

## Gravity angles (GravityEffect)

Each switch changes gravity in exactly one of two ways:
- `{to: [dx,dy], turn: shortest|ccw|cw}` gives an absolute direction plus the way the vector rotates to reach it.
- `{rotate_deg: ±deg}` gives a signed rotation relative to the gravity at activation.

Either way the engine stores a **signed sweep** relative to the preceding state. A 180° reversal therefore has an explicit direction.

| Convention | Meaning |
|---|---|
| World angle | Counter-clockwise from +x, with y up. The original "down" is −90°. |
| `rel_prev_deg` | Signed rotation from the preceding gravity state (+ = counter-clockwise). |
| `rel_original_deg` | Accumulated rotation from the original state G0. |
| Camera roll | `align_gravity` shots roll to `90 + unwrapped gravity angle`, so the camera always turns the same way as the physics. A counter-clockwise sweep rolls the camera clockwise on screen (positive roll), and vice versa. Large turns are rate-limited by `roll_rate`. |

The 30 s story uses:

| State | World direction | vs previous | vs original |
|---|---|---|---|
| G0 | −90° (down) | — | 0° |
| G1 | 0° (toward the right wall) | +90° (CCW) | +90° |
| G2 | 180° (toward the left wall) | **−180° (CW, back through the original "down")** | −90° |

`gravity_shift` events carry `rel_prev_deg` and `rel_original_deg`, and `GravityField.report()` lists every state. QA records this as `gravity_angle_report`, and `camera_roll_follows_gravity_direction` checks that aligned shots roll the same way as the sweep.

Gravity can only change through a switch effect. That makes every gravity transition attributable, and QA verifies the cause.

## SceneSpec

| Field | Notes |
|---|---|
| `environment` | Environment id |
| `duration` | Seconds (keep it a whole number of frames) |
| `placements[]` | `{character, x, facing: ±1}` (x on the floor) |
| `actions[]` | Executed in order per character. `idle(duration)`, `walk_to(target_x, speed?)`, `run_to(target_x, speed?)`, `turn(face)`, `press(switch, hesitate?)`, `jump(height)`, `look_around(duration)`, `wait_grounded` (waits until no gravity transition is pending and the character is standing), `notice(target, duration?)` (a double take), `look_at(target, duration)`, `point(target, duration)`. `duck_slide(target_x, speed?)`: a feet-first slide that drops the hips to 30 units, decelerates by friction and rises straight into the next run. `jump_to(target_x, height, switch?)`: a ballistic jump to a landing point with an apex height; with `switch`, the hand slaps the button mid-air at the closest approach. `grab_swing(target "bar:<id>", release_deg, swings, face)` is armed while standing: when support is lost, the body tumbles feet-first and the hands lock onto the bar overhead (a pivot joint). The arms absorb 45 % of the catch, pumping kicks build the swing (booked as muscular work), and the release comes at the top of the swing on side `face` (+1 = counter-clockwise of hanging) once the angle exceeds `release_deg`. Its optional `duration` is a dangle: AXEL hangs, looks down and then at the exit before pumping, which leaves time for a camera turn. `reach_exit(target "exit:<id>", speed?, duration?)` walks to the doorway, waits at the threshold until the door is open, then walks through. With `duration`, AXEL stops in the doorway and looks back at the room for that long before stepping out. `target` is `switch:<id>`, `exit:<id>`, `bar:<id>` or `point:x,y`. Locomotion takes `style: normal|cautious` and an optional gaze `target` |
| `shots[]` | Contiguous, starting at 0 and ending at `duration` |

Required fields per action are validated: for example, `walk_to` needs `target_x` and `press` needs `switch`.

## ShotSpec (one per shot, for every shot)

| Field | Purpose |
|---|---|
| `id`, `start`, `end` | Identifier and timing |
| `description` | Human-readable intent |
| `camera` | `mode: static|follow|track_x|dolly`, `target`, `center`, `center_end`, `view_height`, `view_height_end`, `offset`, `lead`, `stiffness`, `roll`, `roll_end`, `roll_mode: fixed|align_gravity`, `roll_rate` (deg/s cap for aligned rolls), `roll_ease: in_out|sine|linear` (easing for `roll → roll_end`; `sine` peaks at 1.57× the average rate, cubic `in_out` at 3×), `focus: body|upper|head` (the framing region, used by the guard), `shake` (strength of the event shake), `keep_in_frame` |
| `kind` | `establishing|wide|medium|close|insert|tracking`. QA checks inserts frame the switch, and close-ups frame their focus region |
| `character_states` | Expected state at shot start (documentation / QA hint) |
| `action_objectives` | What the shot must show |
| `object_interactions` | e.g. "hand contacts gswitch button" |
| `environment_state` | e.g. `{"gravity": "G0 -> G1"}` |
| `physics_requirements` | e.g. "ballistic fall", "feet-first contact with wall_right" |
| `sound_cues[]` | `{on_event, sound, gain}`. Bound to engine events, never to raw times |
| `fade_out` | Seconds of fade to black at the end of the shot |
| `exit_conditions[]` | `event:<type>`, `state:<idle|loco|press|...>`, `grounded_on:<surface>`. **Checked by QA** |

Character positions per shot are not hand-specified. They are the *output* of simulation: `SceneRuntime.evaluate(t)` returns every character's pose at any time.

## Events (engine output)

`footstep`, `turn`, `press_contact`, `switch_activated`, `gravity_shift`, `gravity_settled`, `lost_support`, `brace`, `impact`, `recovered`, `takeoff`, `prop_impact`, `notice`, `point`, `slide_start`, `slide_end`, `grab`, `grab_missed`, `release`, `graze` (glancing contact with a surface that cannot support the body under the current gravity: not a landing), `door_unlocking`, `door_unlocked`, `door_open`, `look_back`, `exit_reached`, `door_close`. Each has a time, a character and data (surface, speeds, points).

## Example

See `examples/gravity_switch_1d.json` (the 30 s story: every action above, two signed gravity rotations, the door state machine), `examples/gravity_switch_1c.json` (acting, shot vocabulary, gravity-aligned roll), `examples/gravity_switch_1b.json` and `examples/motion_test.json`.
