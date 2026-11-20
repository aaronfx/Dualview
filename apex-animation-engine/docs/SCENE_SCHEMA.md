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
| `environments[]` | EnvironmentSpec | `room{width,height,depth_*}`, `gravity [gx,gy]`, `switches[]`, `props[]`, `exits[]` (`{id, surface: floor|wall_left|wall_right|ceiling, s, width, sealed}`), `dust` (particle count, 0 = off) |
| `scenes[]` | SceneSpec | See below |

Validation covers duplicate ids, unknown references (environment, character, switch, camera target, action `target`) and schema version.

## SwitchSpec and GravityEffect

`{id, x, height, effect: {to: [dx,dy], magnitude?, delay, duration}}`. Gravity can only change through a switch effect. That makes every gravity transition attributable, and QA verifies the cause.

## SceneSpec

| Field | Notes |
|---|---|
| `environment` | Environment id |
| `duration` | Seconds (keep it a whole number of frames) |
| `placements[]` | `{character, x, facing: ±1}` (x on the floor) |
| `actions[]` | Executed in order per character. `idle(duration)`, `walk_to(target_x, speed?)`, `run_to(target_x, speed?)`, `turn(face)`, `press(switch, hesitate?)`, `jump(height)`, `look_around(duration)`, `wait_grounded` (waits until no gravity transition is pending and the character is standing), `notice(target, duration?)` (a double take), `look_at(target, duration)`, `point(target, duration)`. `target` is `switch:<id>`, `exit:<id>` or `point:x,y`. Locomotion takes `style: normal|cautious` and an optional gaze `target` |
| `shots[]` | Contiguous, starting at 0 and ending at `duration` |

Required fields per action are validated: for example, `walk_to` needs `target_x` and `press` needs `switch`.

## ShotSpec (one per shot, for every shot)

| Field | Purpose |
|---|---|
| `id`, `start`, `end` | Identifier and timing |
| `description` | Human-readable intent |
| `camera` | `mode: static|follow|track_x|dolly`, `target`, `center`, `center_end`, `view_height`, `view_height_end`, `offset`, `lead`, `stiffness`, `roll`, `roll_end`, `roll_mode: fixed|align_gravity`, `focus: body|upper|head` (the framing region, used by the guard), `shake` (strength of the event shake), `keep_in_frame` |
| `kind` | `establishing|wide|medium|close|insert|tracking`. QA checks inserts frame the switch, and close-ups frame their focus region |
| `character_states` | Expected state at shot start (documentation / QA hint) |
| `action_objectives` | What the shot must show |
| `object_interactions` | e.g. "hand contacts gswitch button" |
| `environment_state` | e.g. `{"gravity": "G0 -> G1"}` |
| `physics_requirements` | e.g. "ballistic fall", "feet-first contact with wall_right" |
| `sound_cues[]` | `{on_event, sound, gain}`. Bound to engine events, never to raw times |
| `exit_conditions[]` | `event:<type>`, `state:<idle|loco|press|...>`, `grounded_on:<surface>`. **Checked by QA** |

Character positions per shot are not hand-specified. They are the *output* of simulation: `SceneRuntime.evaluate(t)` returns every character's pose at any time.

## Events (engine output)

`footstep`, `turn`, `press_contact`, `switch_activated`, `gravity_shift`, `gravity_settled`, `lost_support`, `brace`, `impact`, `recovered`, `takeoff`, `prop_impact`, `notice`, `point`. Each has a time, a character and data (surface, speeds, points).

## Example

See `examples/gravity_switch_1c.json` (acting, shot vocabulary, gravity-aligned roll), `examples/gravity_switch_1b.json` and `examples/motion_test.json`.
