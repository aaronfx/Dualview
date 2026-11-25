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
