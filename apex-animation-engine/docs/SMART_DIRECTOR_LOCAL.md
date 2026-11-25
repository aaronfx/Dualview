# Smart Director local foundation D0/D1

This branch extends the existing standalone APEX engine; no alternate renderer,
physics engine or paid API is needed for the bounded crossing demonstration.
Base: semantic-transposition commit 8d3a317 (includes Studio & EDU V2).
Do not merge into main or claim reference-quality completion without native proof.

## Windows

From the repository's apex-animation-engine folder, with Python 3.12, Git,
FFmpeg and ffprobe available:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_windows.ps1 -QuickTests -RenderSmoke
    .\.venv\Scripts\python.exe -m apex.ai.director_local capabilities --out out\capabilities.json
    .\.venv\Scripts\python.exe examples\smart_director_crossing.py --out out\smart_director --render

The capabilities command requires an existing output directory. The demo
writes director_trace.json, project.json on success, native video.mp4,
qa.json and a review packet. A separate render_status.json is written only
after native QA and full FFmpeg decode pass. Artistic approval is still manual.

## Tools

- catalogue: all ActionType primitives from the native schema, known events,
  actual motion clips, parameter guidance, native authority and limitations.
- cross_and_collect: typed objective; use native geometry proposals, preserve
  other actors' queues, rehearse the whole scene, reject missing ordered
  physical events and Inspector failures, replay event-driven shot staging.
- rehearse: compare supplied native action candidates against one unchanged
  world and explicit goals, bounded to eight trials and sixty-second scenes.
- story: existing OpenRouter/other provider StoryDirector, with existing spend
  policy, setup solver and logs. Offline template mode is explicit. A story
  plan is not an accepted movie.
- render: native renderer, QA, decode; no standalone prototypes.

## Status and limits

The action catalogue is schema-derived availability, not a certification
that every combination works. Crossing proposal generation remains bounded
to the existing native planner. Generic ensemble rehearsal compares supplied
candidates; it is not yet a general objective-to-action planner. Paid story
planning still uses the existing StoryDirector; no new autonomous LLM tool
calling or visual critic is claimed. No cloud deployment.

The semantic-transposition branch has known final-evaluation failures;
do not weaken the original assertions. The opt-in ink renderer, continuous locomotion profile, industrial depth,
visual prop diagnostic and signed-term rehearsal have now been wired into
this branch. The prior package's broader ensemble and movie acceptance
suite is not yet fully integrated. Fresh Windows validation is still required before a consolidated D0 acceptance.

## Budgeted AI mission execution

Configure your approved provider using the existing APEX AI environment variables
and spending policy (see docs/AI_SPEND.md). Start with a small objective and an
existing scene. Do not put keys in project JSON or briefs. Paid calls are off by
default. Use a fresh output directory on every run.

    .\.venv\Scripts\python.exe -m apex.ai.director_local mission out\world.json brief.txt --scene cross --reason "Evaluate native mission direction" --out out\mission_001 --render

The model sees the current scene and a capability catalogue, and selects either
cross_and_collect, rehearse, or unsupported. Unknown tools, scene switches and
unproved results are rejected. Up to two provider calls are allowed, subject to
the pre-existing tighter budget limits. Native execution, not model text,
provides the acceptance evidence. This first mission interface requires an
existing world; it does not yet build a whole multi-scene movie from scratch.

## Local production studio (incremental D2–D8)

Launch from apex-animation-engine:

    .\.venv\Scripts\python.exe -m apex.api.local_studio

Open http://127.0.0.1:8078/ . The loopback-only app queues one production
at a time. Offline mode uses existing templates; the paid mode uses the
existing budgeted StoryDirector. Projects can also be submitted as native
ProjectSpec JSON to POST /projects. Preview, native QA, decoded-pixel and
pacing reports are generated locally. Final rendering requires an explicit
owner review of the exact preview. An interrupted job can be resumed;
unchanged, passing native scene segments are content-fingerprinted and reused.

Ensemble mission tool: bounded causal task DAG with native event waits,
validated alternative action queues and independently verified dependencies.
Actor evidence and approvals are stored per production in SQLite. The critic
reports native pacing, overlap and missed actions plus decoded near-black
and static runs. It is not a learned image/video critic. No unrestricted
improvisation or reference-quality acceptance claim. Actual paid model tests,
Windows smoke, complete benchmark films and visual acceptance remain required.

## Local CLI production and revision

    python -m apex.ai.director_local produce brief.txt --offline --out out/local_001
    python -m apex.ai.director_local resume --out out/local_001
    python -m apex.ai.director_local revise scene_id --out out/local_001 --revision out/local_002
    python -m apex.ai.director_local approve --out out/local_001 --review "Watched and approved"

A revision is separate from the original production, changes only one scene's
native actions, and only accepts a strict QA-passing candidate with improved
measured pacing. Identical scene files are copied for hash-checked reuse; the
owner must review the new preview. For natural-language generation without
--offline the existing provider requires explicit approved credentials and
budget. Automatic staging adds only absent score cues and optional visual
profiles; it never removes story goals or changes physical layout.

## High-level actor objectives and optional image critic

The new objectives mission tool compiles observe, signal, collect, climb,
exit, help_up and attack into bounded native alternatives. The ensemble DAG
checks scene dependencies and actual completion events; unsupported intents
are refused. This is not unrestricted in-scene improvisation.

Optional local vision review: install and run an appropriate Ollama vision
model yourself, then run:

    python -m apex.ai.director_local vision-review out/local_001/preview.mp4 --model YOUR_INSTALLED_VISION_MODEL --out out/local_001/vision.json

Only a fixed loopback Ollama endpoint is used. Six timestamped actual frames
are reviewed as advisory findings; no cloud video upload and no automatic
model installation. No tested model or hardware speed is asserted. Human
artistic approval and native QA remain mandatory.
