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
| `environments[]` | EnvironmentSpec | `room{width,height,depth_*}`, `gravity [gx,gy]`, `switches[]`, `props[]`, `exits[]`, `obstacles[]`, `dust` (particle count, 0 = off), `theme` (ThemeSpec: `accent`, `alert`, `back`, `floor`, `side`, `ceiling`, `background`, `dust` hex colours; the defaults reproduce the original lab look) |
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

## Props, ropes and characters' strength (physical interaction)

**PropSpec** `{id, kind, position, size, mass, angle, friction, static_friction, collide_characters, solid, com, z, depth}`. Every prop is a dynamic rigid body.

- **`kind`** is `crate`, `canister`, `container`, `post`, `bar` (pry bar / lever) or `toolbox`.
- **`friction` / `static_friction`**: the sliding coefficient, and an optional higher coefficient used while the prop is at rest. This gives stick-slip: a heavy container "breaks loose" once the push exceeds static friction.
- **`com`**: centre-of-mass offset in the prop's local frame (a top-heavy post).
- **`solid: false`**: fixed set dressing (a tool on a wall rack, a fulcrum block) until a character picks it up.
- **`z` / `depth`**: the prop's depth in the room. A negative `z` is nearer the camera than the characters.

Standing characters pass in front of props (2.5D). A character lying down is solid, so a load can come to rest on it.

**RopeSpec** `{id, a, a_local, b, b_local, length | slack, break_force, color}`: a strap between two props, or between a prop and `world:x,y`.

- Give `slack` (the extra length beyond the initial distance between its ends) or `length`. With `slack`, the engine computes the length from the geometry. `a_point`, `a_anchor`, `local_a`, `a_offset` and the matching `b_` spellings are accepted for `a_local` and `b_local`.
- It is slack below `length` and taut at it. `rope_taut` fires when it snaps taut.
- With `break_force`, it breaks when its tension exceeds that force (`rope_snap`).

**CharacterSpec.strength**: the maximum sustained hand force for pushing, lifting and levers. Efforts are regulated toward a goal and clamped to this value, so physics decides what a character can move.

## Interaction actions

| Action | Fields | What happens (outcomes come from the simulation) |
|---|---|---|
| `push` | `target: prop:`, `effort`, `duration` | Walks up, braces and strains with a bounded force. If the prop breaks loose and outruns the character: `push_lost`, then a stumble and a fall to prone (`body_fall`) |
| `lift` | `target: prop:`, `effort`, `duration` | Grips the prop's nearest end and lifts. The force is clamped to strength. Emits `lift_ok` or `lift_fail` (with the measured rise) |
| `use_lever` | `tool`, `fulcrum`, `target` (all `prop:`), `until` | Runs to the bar and picks it up (`pick_up`), carries it, places it over the fulcrum with its tip under the load (`lever_place`), then bears down on the handle (`lever_engage`). Holds until the `until` event, then releases (`lever_release`) |
| `struggle` | `duration` / `until` | Lying only. Struggles under the load |
| `crawl_out` | `distance` | Lying only. Waits until the load is off (`load_off`), crawls (`crawl_start`), and clears it with a margin (`freed`) |
| `get_up` | `target: char:` (optional) | Lying only. Push-up, knees, stand. With a helper it reaches for their hand (`hand_grab`) and is pulled up (`stood_up`) |
| `offer_hand` | `target: char:` | Goes to the character, offers a hand (`hand_offered`) and pulls once it is taken |
| `gesture` | `target: char:`, `gesture: fist_bump \| shoulder_pat \| wave` | Both characters' hands meet at a shared contact point |
| `wait_for` | `until: event:<type>[@<who>]` or `next:<type>[@<who>]` | Synchronises one character with another's events. `event:` counts an event at any time, even before the wait began. `next:` counts only events after the wait begins, for example "the next strike" in a fight |

`walk_to` / `run_to` accept a `char:` or `prop:` target instead of `target_x`.

**Automatic events:** `pinned` / `load_off` (a prop resting on a lying character, detected from vertical contact impulses), `rope_taut` and `rope_snap`.

## Combat actions (Milestone 1)

| Action | Fields | What happens (the simulation decides the outcome at the moment of contact) |
|---|---|---|
| `strike` | `target: char:`, `move: jab \| cross \| hook \| uppercut \| front_kick \| side_kick \| roundhouse \| sweep`, `power` (0.3–2), `reaction` (optional: `flinch \| stagger \| knockdown`) | Closes to the move's range, which depends on the target height for kicks, then winds up, snaps, makes contact and recovers (`strike_start`, then `swing` at the snap). At contact the result is one of three outcomes. **whiff:** the target is out of reach, ducked under a head-height strike, or is already down (`whiff`, `evaded`). **blocked:** the target is guarding and facing the attacker, which sweeps go under (`blocked`, `block_hit`; the guard recoils and keeps guarding). **hit** (`hit`, `hurt`): the reaction comes from `power × move weight × strength`, or from `reaction`. A flinch snaps the head back, and a stagger knocks the target back with stepping feet. A **knockdown** is a ragdoll physics fall (`knockdown`, `body_fall`, `settled`, with `posture` face down or face up) |
| `guard` | `duration` / `until` | The fighting stance, fists up |
| `dodge` | `dodge: back \| duck` | `back` steps out of reach. `duck` drops under head height for about 0.5 s |

**Reactions interrupt the target.** Its queued actions then resume, and a `wait_for` is kept unless the hit was the event it was waiting for. A knocked-down character automatically gets up (from its front or its back) before its next action that needs standing. Between combat moves an `idle` is drawn as the fighting stance.

**QA checks:**
- `strike_contact`: the fist or foot is on the struck body point at contact;
- `fighters_do_not_overlap`;
- `knockdowns_settle`.

## Structures, acrobatics and symbols (Milestone 2)

**Structures.** Two new `ObstacleSpec.kind` values:
- `platform`: a solid box (`center`, `size`) whose top can be stood on.
- `glyph`: a fixed symbol (`glyph`, `size`, `weight` = stroke thickness, `color`). Its near-horizontal strokes can be stood on: the top bar of a `7` or a `π`, a `-`, both bars of a `=`.

Glyphs: `+ - x ÷ = < > ! ? π √ 0-9`. Aliases: `× − * /`. The strokes are defined in `scene/glyphs.py`. One definition drives the physics (rounded segments), the standable tops and the rendering.

Each standable top is a support surface with ends. Walking past an end steps off it (`step_off`) and drops. A walk that runs into a structure is rejected with the structure's name. Use `vault`, `climb` or `jump_to … onto` instead.

**Simulation guarantees.** Whatever moves a standing body (a walk, a strike's lunge, a dodge, a knockback, a landing slide, a roll), it stops at a structure's face (`bump` event), and moving past the end of a top steps off it. A landing whose next action is combat goes straight into the fighting stance. A roll evades head and body strikes, and an airborne body is never hit. Flips conserve angular momentum, so a landing earlier or later than planned lands under- or over-rotated. A thrown prop's impact is an impulse exchange; the `hit`/`blocked` event records `impulse`, `normal`, `prop_mass`, `body_mass`, `v_before` and `v_after`.

**Symbols as props.** `PropSpec.kind: "glyph"` (with `glyph`, `size`, `weight`, `mass`, `color`) is a dynamic compound body built from the glyph's strokes. It can be pushed, picked up, carried, swung and thrown.

| Action | Fields | What the simulation does | Events |
|---|---|---|---|
| `jump_to` | `target_x`, `height`, `onto: "obstacle:<id>"`, `flip: front\|back` | Ballistic jump that accounts for the height difference to the landing top (from a top, it lands on the floor by default). A flip rotates the body along a planned somersault that completes before landing | `takeoff`, `flip`, `impact` |
| `roll` | `distance` or `target_x` | Forward roll. Directly after a jump, it starts at touchdown (a landing roll) | `roll_start`, `roll_end` |
| `vault` | `target: "obstacle:<id>"\|"prop:<id>"` | Over a structure lower than 0.95 × body height: hand plant, legs over, landing | `vault_start`, `vault`, `impact` |
| `climb` | `target: "obstacle:<id>"` | From beside a top within reach: jump, hang from the edge, pull up, mantle, stand on it | `climb_start`, `ledge_grab`, `climbed` |
| `wall_kick` | `target_x`, `target: "obstacle:<id>"` (else the room wall ahead), `height`, `flip` | Run at the wall, two steps up it, push off on a ballistic arc to `target_x` | `wall_run`, `wall_contact` ×2, `wall_kick`, `flip` |
| `pick_up` | `target: "prop:<id>"` | Grip a light prop (mass × g ≤ 0.9 × strength) and carry it in both hands | `pick_up` |
| `throw` | `target: "char:<id>"\|"point:x,y"`, `power` | Wind up and release on a ballistic arc at the target. In flight, contact with a body is a **hit** (a reaction from the momentum) or **blocked** (guarding and facing). A duck or a step back can make it miss | `throw_start`, `throw`, `hit`/`blocked`, `prop_hit` |
| `strike` `move: flying_kick` | as for other strikes | A jumping lunge, with contact near the top of the arc | `takeoff`, `impact` |
| `strike` `move: swing_weapon` | as for other strikes, while carrying | Swings the carried prop. The reach is the arm plus the prop | as for other strikes |

## Depth lanes and film-time effects (Milestone 3)

**Depth lanes.** `CharacterPlacement.z` sets a character's starting lane (negative is nearer the camera). Any action may carry `lane`, and the body then moves in depth toward it at 70 units/s. Two standing bodies whose lanes are less than 28 apart cannot pass through each other (`body_block`). Lanes 28 or more apart pass one in front of the other. A falling ragdoll collides with standing bodies in its lane.

**`SceneSpec.time_fx`** (optional). The simulation is untouched; the film samples it through a time warp.

| Field | Default | Meaning |
|---|---|---|
| `hit_stop` | true | At each blow the impact frame holds |
| `hit_stop_frames` | 3 | Frames for a blow of power 1 (× (0.6 + 0.6 × power); blocks half) |
| `hit_stop_max` | 6 | Cap on the frames of one hold |
| `hit_stop_events` | `hit`, `block_hit`, `prop_hit` | Events that cause a hold |
| `slowmo` | [] | A list of `{at, before, after, rate, ramp}`: around the event `at` (goal syntax, e.g. `flip@kai[dir=back]`), story time runs at `rate` |
| `screen_fx` | true | Impact flash (heavy blows, at most 2 frames), chromatic split on the held frame, vignette pulse, speed lines in slow motion |
| `smears` | true | Smears on fast limbs; ghosts on fast props |
| `punch_in` | true | Camera punch-in on heavy blows; push-in during slow motion |

Sounds and effects are placed on the film clock. QA checks the warp (`time_warp_valid`, `hit_stop_frames`, `flash_safety`, `slowmo_bounds`).

## Levels, orbs, portals, beats (Milestone 4)

**`EnvironmentSpec.level`**: `{rows, cell, origin, legend}`. The grid is expanded into platforms, orbs, portals and markers. Its symbols:
- `#` block; `=` ledge;
- `o` jump orb, `b` boost orb, `^` pad, `*` collectible;
- `A`/`a` a portal pair;
- digits: markers.

`CharacterPlacement.at` places a character on a marker.

**`EnvironmentSpec.orbs`**: `{id, kind: jump|boost|pad|collect, center, radius, power, flip, color}`. Default `power`: jump 130 (apex), pad 170 (apex), boost 320 (u/s added).

**`EnvironmentSpec.portals`**: `{id, center, link, angle, height, color}`. `angle` is the direction the portal opens toward, in degrees. A crossing maps position and velocity rigidly to `link`, so the speed is kept. A walk that runs into a portal ends at it.

**`SceneSpec.music`**: `{bpm, offset, beats_per_bar, snap_cuts, snap_window, gain}`. It defines a film-time beat grid:
- shot boundaries near a beat snap onto it, except on a portal crossing;
- action `wait_beat` (`beats`: n) holds until the n-th next beat;
- the soundtrack is a beat-locked groove.

**`CameraSpec.bound_to_room`**: the view never shows past the room's walls.

Events: `orb_jump`, `orb_boost`, `orb_pad`, `collect`, `portal_enter`, `portal_exit`, `beat_wait_end`.

QA checks:
- `portal_transfers`, `orb_impulses`, `collectibles_once`;
- `beat_cuts`, `beat_waits`, `music_on_beat`;
- `particles_deterministic`, `particle_budget`.

## Breakables, morphs, diagrams, creatures, set dressing (Milestone 5)

**`PropSpec.breakable`**: `{impulse, scatter, grid}`.
- The prop breaks when the contact impulse it takes in one step reaches `impulse`.
- A glyph breaks into its strokes (pieces `"<glyph>#k"`); a box breaks into `grid`² blocks.
- The pieces are props `<id>~k` and exist once it breaks.

**`PropSpec.morphs`**: a list of `{to, at | on, delay, duration}`. A glyph prop changes into the glyph `to`. The mass, the centre of mass, its velocity and the angular momentum are kept. A character in the way makes it wait; a structure is cleared by the smallest nudge.

**`SceneSpec.diagrams`**: a list of `{id, kind, target, to, t0, t1 | on, duration, text, scale, unit, color}`.
- `kind`: `velocity`, `trajectory`, `label` (fields `{speed} {height} {mass} {name}`), `measure` or `impulse`.
- Targets: `char:`, `prop:`, `creature:` or `point:x,y`.

**`EnvironmentSpec.creatures`**: a list of `{id, body, size, position, mass, parts, path, height, stride, max_force, max_lift, breaks, morphs, z, depth}`.
- Each part is `{glyph, size, at, pivot, role: leg|arm|tail|head|eye, mass, swing, phase}`.
- The body becomes the prop `<id>.body` and the parts become `<id>.k`.

**`EnvironmentSpec.decor`**: a list of `{kind: window|panel|screen|pipe|lamp|bench|shelf, x, y, w, h, x2, y2, z, color, text, seed}`. It is drawn only; nothing collides with it. **`RoomSpec.grid_alpha`** sets the strength of the neon grid.

Events: `break`, `morph_start`, `morph`, `morph_blocked`, `creature_break`.

QA checks:
- `breaks_at_threshold`, `breaks_conserve_momentum`, `breaks_continuous`;
- `morphs_conserve_motion`, `morphs_hold_centre`, `morphs_no_pop`;
- `diagrams_truthful`, `diagrams_in_frame`;
- `creature_joints_hold`, `creature_breaks_at_threshold`, `creature_follows_path`;
- `causes_on_screen`.

## Acting, collapses, rescues, retries and films (Milestone 6)

**`act`** (an action): `{clip, duration, emotion, intensity, tempo, tremble}`.
- Plays a motion-library clip as a performance, then holds its last pose (breathing) for the rest of `duration`.
- Clips: `cheer`, `laugh`, `beckon` (over the shoulder), `wave_on` (facing the other), `cower`, `shock`, `reach_out`, `despair`, `kneel_look`, `rise`, `embarrassed`, `peer_down`, `lose_balance`, `recover_relief`, `recover_relief_shake`, `brace`.
- `emotion`: `neutral`, `afraid`, `scared`, `determined`, `relieved`, `tired`, `sad`, `joyful`, `embarrassed`. `intensity` exaggerates the clip, `tempo` speeds it up and `tremble` shakes the hands, arms and head.
- Each act emits `act` with `{clip, emotion}`, so a wait can name one: `"until": "event:act@iko[clip=rise]"`. Event waits accept the same `[key=value]` filters as goals.

**`ObstacleSpec.collapse`**: `{under, after, at, on, pieces, color}` makes a platform give way.
- It collapses at the first of: the character `under` having stood on it for `after` s, the time `at`, or the event `on`.
- It breaks into `pieces` planks (props `<id>~k`) that fall. From that moment it is no solid and no support, and whoever stands on it steps off.

**`CharacterPlacement.on`**: `"obstacle:<id>"` starts a character standing on a structure's top.

**Ledges and rescues:**
- **`catch_ledge`** `{target: obstacle:<id>}` is armed behind a walk or run. If the character falls, its hands catch the nearest corner of that top within reach (event `ledge_catch`).
- **`hang`** `{slip_at, distance, duration, until}` holds on. `slip_at` makes the near hand slip (event `hang_slip`). With `duration`, the character scrambles up unaided.
- **`pull_up`** `{target: char:<id>}`: the rescuer goes to the edge above the hanging character, kneels and reaches down. The two hands meet at one grip point (`hand_grab`), and the rescuer steps back as the other is pulled up and over (`pulled_up`).

**`gesture: nudge`** is a shoulder nudge (event `nudge`).

**`SceneSpec.fail`**: `{below, characters}`. Falling below the height `below` is a fail (event `fail`, once per character).

**`SceneSpec.hud`**: `{retries, retries_max, label, messages}`.
- A retry counter is drawn top right. It ticks down with a red flash at each `fail`.
- `messages` is a list of `{text, at | on, delay, duration, style: alert|info|success|title}`.

**`ExitSpec.unlock_on: "together:<id>,<id>"`**: the exit unlocks only when all of them stand within `open_radius` of it at once (event `exit_together`). After a character passes through an exit door, it has left the level.

**`RoomSpec.void_below`** draws the room below that height as a bottomless void with falling data. The floor is still there physically, far below a level built on platforms. It is drawn only.

**Films:**
- `SceneSpec.transition_in` is `cut`, `fade` or `rewind`: how `apex film` enters the scene from the previous one. A rewind freezes the last frame, then plays the previous scene backwards at high speed with a glitch and a tape-rewind sound, made from its own rendered frames.
- `SceneSpec.retry_of` marks a scene as a retry of another. It must restart from the same state.

Events: `act`, `collapse`, `ledge_catch`, `hang_slip`, `pulled_up`, `nudge`, `fail`, `exit_together`.

QA checks:
- per scene: `hands_meet` (the two hands touch at every hand grab and stay together while holding). `door_state_machine` re-derives a together unlock from the rendered bodies;
- per film (`apex film`): `retry_resets_consistent` (every body starts where it started in the attempt it repeats) and `retry_counter_consistent` (the counter carries from scene to scene, minus the fails, and a failed attempt is followed by a retry).

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
| `placements[]` | `{character, x, facing: ±1, z}`: `x` is on the floor; `z` is an optional drawing depth lane (−60…60, negative = nearer the camera). The nearer character is drawn slightly larger and on top. It does not affect physics |
| `actions[]` | Executed in order per character. `idle(duration)`, `walk_to(target_x, speed?)`, `run_to(target_x, speed?)`, `turn(face)`, `press(switch, hesitate?)`, `jump(height)`, `look_around(duration)`, `wait_grounded` (waits until no gravity transition is pending and the character is standing), `notice(target, duration?)` (a double take), `look_at(target, duration)`, `point(target, duration)`. `duck_slide(target_x, speed?)`: a feet-first slide that drops the hips to 30 units, decelerates by friction and rises straight into the next run. `jump_to(target_x, height, switch?)`: a ballistic jump to a landing point with an apex height; with `switch`, the hand slaps the button mid-air at the closest approach. `grab_swing(target "bar:<id>", release_deg, swings, face)` is armed while standing: when support is lost, the body tumbles feet-first and the hands lock onto the bar overhead (a pivot joint). The arms absorb 45 % of the catch, pumping kicks build the swing (booked as muscular work), and the release comes at the top of the swing on side `face` (+1 = counter-clockwise of hanging) once the angle exceeds `release_deg`. Its optional `duration` is a dangle: AXEL hangs, looks down and then at the exit before pumping, which leaves time for a camera turn. `reach_exit(target "exit:<id>", speed?, duration?)` walks to the doorway, waits at the threshold until the door is open, then walks through. With `duration`, AXEL stops in the doorway and looks back at the room for that long before stepping out. `target` is `switch:<id>`, `exit:<id>`, `bar:<id>` or `point:x,y`. Locomotion takes `style: normal|cautious` and an optional gaze `target` |
| `shots[]` | Contiguous, starting at 0 and ending at `duration` |
| `goals[]` | The story beats that must happen, **in order**, as `<event>[@<who>][[key=value]]`, for example `["push_lost@milo", "rope_snap@strap", "pinned@milo[by=post]", "freed@milo"]`. `who` is a character, prop or rope id. The dry run rejects a plan whose goals don't happen within `duration`. The setup solver (`apex.scene.solver`, see `docs/SETUP_SOLVER.md`) tunes the physical setup until they do |

Required fields per action are validated: for example, `walk_to` needs `target_x` and `press` needs `switch`.

## ShotSpec (one per shot, for every shot)

| Field | Purpose |
|---|---|
| `id`, `start`, `end` | Identifier and timing |
| `description` | Human-readable intent |
| `camera` | `mode: static|follow|track_x|dolly`, `target`, `center`, `center_end`, `view_height`, `view_height_end`, `offset`, `lead`, `stiffness`, `roll`, `roll_end`, `roll_mode: fixed|align_gravity`, `roll_rate` (deg/s cap for aligned rolls), `roll_ease: in_out|sine|linear` (easing for `roll → roll_end`; `sine` peaks at 1.57× the average rate, cubic `in_out` at 3×), `focus: body|upper|head` (the framing region, used by the guard), `shake` (strength of the event shake), `keep_in_frame`, `include` (targets kept in frame with the subject, e.g. `bar:rail`, `exit:door1`, `obstacle:duct`; QA `composition_required_objects`), `include_margin` (world units around each), `min_subject_frac` (overrides the per-kind minimum subject size checked by `composition_subject_size`) |
| `kind` | `establishing|wide|medium|close|insert|tracking`. QA checks inserts frame the switch, and close-ups frame their focus region |
| `character_states` | Expected state at shot start (documentation / QA hint) |
| `action_objectives` | What the shot must show |
| `object_interactions` | e.g. "hand contacts gswitch button" |
| `environment_state` | e.g. `{"gravity": "G0 -> G1"}` |
| `physics_requirements` | e.g. "ballistic fall", "feet-first contact with wall_right" |
| `sound_cues[]` | `{on_event, sound, gain}`. Bound to engine events, never to raw times |
| `fade_out` | Seconds of fade to black at the end of the shot |
| `cut_on`, `cut_offset` | An event-timed cut: the shot starts when `event:<type>[@<who>]` happens in the simulation, plus `cut_offset` seconds. `resolve_cuts` rewrites `start` and `end` from the simulated times. Shots without `cut_on` keep their planned share of the time between the anchored cuts around them |
| `exit_conditions[]` | `event:<type>`, `state:<idle|loco|press|...>`, `grounded_on:<surface>`. **Checked by QA** |

Character positions per shot are not hand-specified. They are the *output* of simulation: `SceneRuntime.evaluate(t)` returns every character's pose at any time.

Targets (`look_at`, `notice`, `point`, camera `include`): `switch:<id>`, `exit:<id>`, `bar:<id>`, `obstacle:<id>` (any beam or bar, its centre), `point:x,y`.

**Composition rules (QA):** every shot kind has a minimum on-screen subject size, and the `include` objects must stay in frame. The camera may not roll while the subject moves faster than 260 u/s (`no_roll_during_fast_action`). Turn the camera during still beats.

## Motion library (`src/apex/motion/clips/*.json`)

The animator plays character performances from reusable clips, not from code. A clip is a list of named key poses. Each key sets any subset of the rig-relative channels:

- `crouch` and `shift` (fractions of the standing pelvis height);
- `lean`, `chest`, `head`, `twist`, `hip_twist`;
- `arm_n`/`arm_f`, `elbow_n`/`elbow_f`;
- the free-leg offsets;
- `eye`, `squash`, `gaze`.

Each key also chooses how the curve leaves it: `smooth` (monotone cubic), `ease`, `snap`, `slow_in`, `back` (overshoot), `linear` or `hold`.

Clips also declare:

- **phases** (`anticipation`, `follow_through`, …);
- **contacts**: `{effector, on: "surface" | "joint:<name>", t0, t1, s, h, toward, frac, blend}`. Examples are a hand planted on the floor in a hard landing, or hands on the knees while catching breath. The animator enforces them with IK.

A request performs a clip with `Performance(tempo, intensity, mirror, emotion, anticipation, follow_through)`. The emotions are `neutral`, `afraid`, `determined`, `relieved`, `tired`, `excited` and `curious`. Because the channels are relative to the rig, the same clip plays on AXEL and PIP. Clips: `lose_balance`, `fall_flail`, `brace`, `land_hard`, `land_medium`, `recover_relief`, `recover_relief_shake`.

## Events (engine output)

`footstep`, `turn`, `press_contact`, `switch_activated`, `gravity_shift`, `gravity_settled`, `lost_support`, `brace`, `impact`, `recovered`, `takeoff`, `prop_impact`, `notice`, `point`, `slide_start`, `slide_end`, `grab`, `grab_missed`, `release`, `graze` (glancing contact with a surface that cannot support the body under the current gravity: not a landing), `door_unlocking`, `door_unlocked`, `door_open`, `look_back`, `exit_reached`, `door_close`. Each has a time, a character and data (surface, speeds, points).

## Example

See `examples/gravity_switch_1d.json` (the 30 s story: every action above, two signed gravity rotations, the door state machine), `examples/gravity_switch_1c.json` (acting, shot vocabulary, gravity-aligned roll), `examples/gravity_switch_1b.json` and `examples/motion_test.json`.
