# Review packet: Gravity Switch - Escape Room (1D, 30 s) / escape

Video under review: `APEX_1D_v3_gravity_switch_escape_30s_1080p.mp4`

## A. Objective technical metrics (correctness, not quality)

QA: **PASSED**, 63 checks (63 PASS).

| Check | Status | Metric | Threshold |
|---|---|---|---|
| joint_hierarchy[axel] | PASS |  |  |
| bone_lengths[axel] | PASS | 1.098 | 1.13 |
| character_continuity[axel] | PASS |  |  |
| invalid_positions[axel] | PASS | 0 | 0 |
| surface_penetration[axel] | PASS | 3.756 | 4 |
| no_teleport_joints[axel] | PASS | 3116 | 3200 |
| no_teleport_root[axel] | PASS | 1451 | 2200 |
| foot_sliding[axel] | PASS | 1.04 | 1.5 |
| gravity_transitions_caused_by_switch | PASS |  |  |
| gravity_direction[axel] | PASS | 2.213 | 3 |
| collision_events_valid | PASS | 3 |  |
| scene_geometry_stable | PASS | 8 |  |
| camera_config_valid | PASS | 0 | 0 |
| subject_in_frame | PASS | 1 | 0.95 |
| min_shot_length | PASS | 0.65 | 0.5 |
| camera_roll_rate | PASS | 106.4 | 150 |
| gravity_aligned_roll[s06_recover] | PASS | 1.728 | 3 |
| gravity_aligned_roll[s15_relief_door] | PASS | 0.7799 | 3 |
| gravity_indicator_matches_physics | PASS | 0 | 0.5 |
| screen_direction_across_cuts | PASS | 0 | 0 |
| static_layout | PASS |  |  |
| scarf_integrity[axel] | PASS | 1.25 | 1.35 |
| scarf_inside_room[axel] | PASS |  |  |
| dust_inside_room | PASS |  |  |
| gravity_angle_report | PASS |  |  |
| camera_roll_follows_gravity_direction | PASS | 0 | 0 |
| landings_on_supporting_surfaces | PASS | 0 | 0 |
| hand_on_switch_at_contact | PASS | 0.002531 | 22 |
| grip_attachment[axel] | PASS | 0 | 1.5 |
| swing_energy_conserved[axel] | PASS | 0.007766 | 0.02 |
| obstacle_clearance | PASS | 16.6 | 0 |
| door_state_machine[door1] | PASS |  |  |
| composition_subject_size | PASS | 0.1192 |  |
| composition_required_objects | PASS | 0 | 0 |
| no_roll_during_fast_action | PASS | 0 | 0 |
| audio_event_sync | PASS | 0 | 0 |
| deterministic_replay | PASS |  |  |
| video_dimensions | PASS |  |  |
| video_fps | PASS | 24 | 24 |
| frame_count | PASS | 720 | 720 |
| frame_duration | PASS | 30 | 30 |
| av_duration_match | PASS | 0 | 0.07167 |
| full_decode | PASS | 720 | 720 |

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
| s01_establish | 0.00-1.60 | | |
| s02_notice | 1.60-2.55 | | |
| s03_approach | 2.55-5.60 | | |
| s04_insert | 5.60-7.25 | | |
| s05_shift | 7.25-9.60 | | |
| s06_recover | 9.60-11.45 | | |
| s07_door_pov | 11.45-12.15 | | |
| s08_point | 12.15-13.20 | | |
| s09_switch_pov | 13.20-13.85 | | |
| s10_slide | 13.85-16.45 | | |
| s11_slap | 16.45-19.00 | | |
| s12_reestablish | 19.00-19.95 | | |
| s13_catch_swing | 19.95-22.10 | | |
| s14_drop_land | 22.10-23.75 | | |
| s15_relief_door | 23.75-25.90 | | |
| s16_exit | 25.90-30.00 | | |

## C. AI Director suggestions (advisory; not a score)

Not generated (no AI provider configured, or not requested). Suggestions never replace human scores.
