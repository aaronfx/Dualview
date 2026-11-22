# Director's Cut engine support — implementation branch

**Status:** Draft PR #8. These are opt-in engine facilities; the original CORE RUN builder is **not** rewritten and its six technical QA failures remain open. Do not merge until the new suite, full regression suite, and a revised 720p film have been reviewed.

## 1. Plot-critical physical props across scenes

Give the energy core a unique **prop ID** (for example, "core") in each environment where it appears. Its appearance may change, but preserve its identity.

Each scene declares expected owners at its boundaries:

```json
{
  "story_props": [{"prop": "core", "owner_in": "vex", "owner_out": "iko"}]
}
```

"world" means the prop is not in anybody's hands. A non-world owner at scene start places the prop in that character's hands at frame zero and begins a real carry span. The engine does **not** silently pick it up midway through the scene.

The new film-wide `plot_prop_continuity` check simulates each scene and verifies actual carry spans, pickup/release events, the owner at each boundary, and the matching owner between successive scenes. A character-to-character transfer requires both a release and a pickup event. A loose prop cannot jump between different environments.

**Important limit:** This is a verified *ownership handoff*, not a continuous rigid-body simulation across biomes. Independent scenes still have separate world coordinates, physics and entry placements.

## 2. Place, release and disarm

Actions:

```json
{"character": "iko", "type": "place_prop", "target": "point:100,95", "duration": 0.6}
{"character": "iko", "type": "drop_prop"}
{"character": "pell", "type": "throw", "target": "char:vex", "disarm": true}
```

`place_prop` moves a currently carried prop along a timed hand path toward a reachable point or another prop's current location, with obstacle checks. It then releases the prop into ordinary dynamics. Failed reach or structure checks do not fake a placement.

`drop_prop` releases with the carrier's current motion.

`disarm: true` is opt-in. A **successful unblocked** strike or thrown-object hit releases the target's carried prop with a physical velocity and spin. It does not trigger on a whiff or successful guard.

**Important limit:** This is currently **body-impact-driven disarming**, not exact weapon-to-weapon collision detection. For PELL to knock VEX's staff *itself* away, further contact geometry and tests may be appropriate; do not claim a staff-to-staff collision occurs based on this flag alone.

## 3. Physical core restoration

Add an actual restoration socket region to the final scene:

```json
{
  "restoration": {
    "prop": "core",
    "at": [100, 95],
    "radius": 25,
    "max_speed": 12
  }
}
```

The engine emits `core_restored@core` only **after** the core was released via `place_prop`, is not being carried, is within the socket radius, and has remained slow enough for at least 0.12 seconds. Stage an actual supporting platform/fixture so it can physically settle. A scene cannot gain a restoration event just because the core passes through the area.

## 4. Event-driven lighting

Add per-scene world-power changes whose triggers must be actual simulation events:

```json
{
  "world_power": {
    "initial": 0.3,
    "cues": [
      {"on": "core_restored@core", "level": 1.0, "fade": 2.0}
    ]
  }
}
```

The renderer currently shades the sky and distant backdrop layers, not a full physically based lighting system. Lighting is deterministic and follows the story clock, not the number or order of frames rendered.

For a theft scene, a `pick_up@vex[prop=core]` cue can dim the world once the real pickup event occurs.

## 5. Narrative event chain and strict film QA

Project-level `film_goals` are verified from the full simulation's scene-by-scene events in order:

```json
{
  "film_goals": [
    {"scene": "city", "event": "pick_up@vex[prop=core]"},
    {"scene": "arena", "event": "disarmed@vex"},
    {"scene": "summit", "event": "core_restored@core"}
  ]
}
```

This is a **technical narrative-event check**, not a substitute for human evaluation of whether the theft, rescue or restoration is understandable on screen. Use the existing `causes_on_screen` cinematic check as well.

To refuse a full movie if scene/film QA fails:

```bash
apex film examples/core_run.json -o out/core_run/final.mp4 --strict-qa --preset final
```

Strict mode deliberately rejects `--only`: the final acceptance render must rebuild every scene, so stale cached segments cannot quietly be used.

## 6. Validation

```bash
cd apex-animation-engine
python -m pip install -e ".[dev]"
PYTHONPATH=src python -m pytest -q tests/test_directors_cut_engine.py
PYTHONPATH=src python -m pytest -q
```

GitHub Actions in this PR runs both commands with Linux Skia prerequisites.

## 7. Known unfinished work

- The first CORE RUN builder still uses the original rivalry-then-reconciliation story, not the stolen-core Director's Cut.
- The six first-draft technical QA failures are not yet addressed here.
- A proper core-carry narrative across the five worlds must be authored, rendered and QA-checked.
- There is no general scene-to-scene rigid-body state transfer.
- The current world-power grade is limited to sky and backdrop.
- Body-impact disarming must not be mistaken for direct weapon-to-weapon impacts.
- Full production quality cannot be claimed until human viewing and QA of the 720p Director's Cut.
