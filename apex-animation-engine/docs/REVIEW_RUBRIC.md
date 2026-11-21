# Human review rubric (quality upgrade, Task 5)

APEX keeps two kinds of evidence apart:

1. **Objective technical metrics (QA).** These measure correctness: no teleporting joints, no foot sliding, gravity obeyed, the subject in frame, audio in sync, a decodable video. A pass means the film is *valid*. It says nothing about whether it is *good*.
2. **Subjective quality scores.** Only human reviewers give these, using the anchors below. The AI Director may *suggest corrections* from the shot list, the event timeline and the QA notes. Its text is labelled "advisory; not a score", and no AI output is ever recorded as a quality score.

## Producing a review packet

```bash
apex render examples/gravity_switch_1d.json -o out/film.mp4 --samples 3 --qa-json out/qa.json --review-dir out/review
apex review examples/gravity_switch_1d.json out/review --video out/film.mp4 --qa-json out/qa.json [--ai]
```

`REVIEW.md` has three sections, always in this order:

- **A. Objective technical metrics**, copied from the QA report;
- **B. Human review rubric**, with the anchors and a notes table per shot;
- **C. AI Director suggestions**, which are optional. They need `APEX_AI_PROVIDER` / `OPENROUTER_API_KEY` in the backend environment and never appear in the scores.

`review_scores.json` is a blank sheet: every score starts as `null`. Each reviewer fills in a copy. `apex.qa.review.aggregate_scores(sheets)` reports the mean, the spread and the number of reviewers for each criterion. A spread above 2 means the reviewers disagree, so discuss it and do not average it away.

## Procedure (repeatable)

1. Watch the full 1080p video once at normal speed, with sound. Only judge story and emotion on this pass.
2. Watch it again, pausing at every cut and impact. Use the contact sheet (`review/<video>_contact_sheet.png`) and the motion diagnostics.
3. Score each criterion 1–10 against the anchors. Give the score the description matches best, and do not round up.
4. For every score below 8, write at least one concrete fix with a timestamp ("22.9 s: the landing reads light, the far arm floats").
5. Fill in the notes table for each shot.
6. At least two reviewers. Report the mean and the spread. Never report a single number without its spread and the number of reviewers.

## Criteria and anchors

| Criterion | 3 | 5 | 7 | 9 |
|---|---|---|---|---|
| Character acting | generic poses; reactions missing or mechanical | clear intent in the key beats; uniform timing; acting reads only in close-ups | distinct, motivated reactions; varied timing; visible anticipation and follow-through | specific, surprising, consistent personality; every beat earns its time |
| Action choreography and body mechanics | no weight; contacts slide or float | physically plausible; impacts read; some floaty or stiff moments | strong lines of action, clear arcs, convincing weight shifts and contacts | dynamic, inventive staging with flawless weight and contact |
| Camera clarity and staging | the action leaves the frame or is confusing; disorienting moves | the action is readable; some shots too wide or too tight, or moves without motivation | every shot has a purpose; spatial orientation is always clear | the camera amplifies the story; the cutting rhythm feels authored |
| Visual consistency and art direction | inconsistent style; artefacts | coherent style; flat lighting or noisy effects | consistent, attractive style; effects support the action | a distinctive, polished look throughout |
| Sound quality and sync | sounds missing or wrong | in sync, but sounds are synthetic or thin | layered, believable sound with a supporting score | sound design adds character and drama |
| Story coherence | the viewer cannot follow what happens or why | the plot can be followed with effort | cause and effect are obvious without narration | a tight, satisfying arc with set-ups that pay off |
| Emotional readability | the character's feelings cannot be read | the major emotions read | the emotional arc is clear and felt | the audience feels with the character throughout |

The reference films (*Animation vs. Math*, *Animation vs. Geometry Dash*, *The Dark Age*) are the calibration point for 9. Agree before scoring that a 9 means "comparable to those". Their content is never reproduced.
