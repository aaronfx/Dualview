# Review packet: Foundry Flip (generalization test) / flip

Video under review: `APEX_T6_foundry_flip_generalization_1080p.mp4`

## A. Objective technical metrics (correctness, not quality)

QA: **PASSED**, 51 checks (51 PASS).

| Check | Status | Metric | Threshold |
|---|---|---|---|
| joint_hierarchy[pip] | PASS |  |  |
| bone_lengths[pip] | PASS | 1.092 | 1.13 |
| character_continuity[pip] | PASS |  |  |
| invalid_positions[pip] | PASS | 0 | 0 |
| surface_penetration[pip] | PASS | 3.88 | 4 |
| no_teleport_joints[pip] | PASS | 2800 | 3200 |
| no_teleport_root[pip] | PASS | 1501 | 2200 |
| foot_sliding[pip] | PASS | 1.323 | 1.5 |
| gravity_transitions_caused_by_switch | PASS |  |  |
| gravity_direction[pip] | PASS | 2.454 | 3 |
| collision_events_valid | PASS | 2 |  |
| scene_geometry_stable | PASS | 8 |  |
| camera_config_valid | PASS | 0 | 0 |
| subject_in_frame | PASS | 0.9979 | 0.95 |
| min_shot_length | PASS | 0.85 | 0.5 |
| camera_roll_rate | PASS | 115.4 | 150 |
| gravity_indicator_matches_physics | PASS | 0 | 0.5 |
| screen_direction_across_cuts | PASS | 0 | 0 |
| static_layout | PASS |  |  |
| dust_inside_room | PASS |  |  |
| gravity_angle_report | PASS |  |  |
| camera_roll_follows_gravity_direction | PASS | 0 | 0 |
| landings_on_supporting_surfaces | PASS | 0 | 0 |
| hand_on_switch_at_contact | PASS | 0 | 22 |
| obstacle_clearance | PASS | 22.74 | 0 |
| door_state_machine[hatch] | PASS |  |  |
| composition_subject_size | PASS | 0.1592 |  |
| composition_required_objects | PASS | 0 | 0 |
| no_roll_during_fast_action | PASS | 0 | 0 |
| audio_event_sync | PASS | 0 | 0 |
| deterministic_replay | PASS |  |  |
| video_dimensions | PASS |  |  |
| video_fps | PASS | 24 | 24 |
| frame_count | PASS | 468 | 468 |
| frame_duration | PASS | 19.5 | 19.5 |
| av_duration_match | PASS | 0 | 0.07167 |
| full_decode | PASS | 468 | 468 |

These numbers show the animation is technically valid. They say nothing about how good it is.

## B. Human review rubric (score 1-10 per criterion; anchors below)

Review the full-resolution video at least twice (once for story, once frame by frame). Score each criterion against the anchors, then note concrete fixes with timestamps. Each reviewer fills one `review_scores.json` copy.

### Character acting (`character_acting`)
- **3**: poses are generic; reactions missing or mechanical
- **5**: clear intent in key beats; timing uniform; acting reads only in close-ups
- **7**: distinct, motivated reactions; varied timing; anticipation and follow-through visible
- **9**: specific, surprising, consistent personality; every beat earns its time

Score: ____   Notes / timestamps:

### Action choreography and body mechanics (`action_choreography`)
- **3**: weight absent; contacts slide or float
- **5**: physically plausible; impacts read; some floaty or stiff moments
- **7**: strong lines of action, clear arcs, convincing weight shifts and contacts
- **9**: dynamic, inventive staging with flawless weight and contact

Score: ____   Notes / timestamps:

### Camera clarity and staging (`camera_clarity`)
- **3**: action leaves frame or is confusing; disorienting moves
- **5**: action readable; some shots too wide/tight or moves unmotivated
- **7**: every shot has a purpose; spatial orientation always clear
- **9**: camera amplifies the story; cutting rhythm feels authored

Score: ____   Notes / timestamps:

### Visual consistency and art direction (`visual_consistency`)
- **3**: inconsistent style; artefacts
- **5**: coherent style; flat lighting or noisy effects
- **7**: consistent, attractive style; effects support the action
- **9**: distinctive, polished look throughout

Score: ____   Notes / timestamps:

### Sound quality and sync (`sound_quality`)
- **3**: missing or wrong sounds
- **5**: sync correct; sounds synthetic or thin
- **7**: layered, believable sound with a supporting score
- **9**: sound design adds character and drama

Score: ____   Notes / timestamps:

### Story coherence (`story_coherence`)
- **3**: the viewer cannot follow what happens or why
- **5**: the plot is followable with effort
- **7**: cause and effect obvious without narration
- **9**: tight, satisfying arc with set-ups that pay off

Score: ____   Notes / timestamps:

### Emotional readability (`emotional_readability`)
- **3**: the character's feelings cannot be read
- **5**: major emotions readable
- **7**: emotional arc clear and felt
- **9**: the audience feels with the character throughout

Score: ____   Notes / timestamps:

### Per-shot notes

| Shot | Time | What works | What to fix |
|---|---|---|---|
| s01_establish | 0.00-2.20 | | |
| s02_notice | 2.20-3.75 | | |
| s03_pov | 3.75-4.60 | | |
| s04_run_slide | 4.60-7.10 | | |
| s05_slap | 7.10-10.00 | | |
| s06_flip | 10.00-12.75 | | |
| s07_relief | 12.75-15.20 | | |
| s08_exit | 15.20-19.50 | | |

## C. AI Director suggestions (advisory; not a score)

Not generated (no AI provider configured, or not requested). Suggestions never replace human scores.
