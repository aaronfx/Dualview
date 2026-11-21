# Renderer evaluation (quality upgrade, Task 4)

**Decision:** keep the Skia renderer. Put it behind a small adapter (`apex.render.base`) so another backend can be added later without touching the pipeline. Nothing found in this pass needs a different renderer to fix. The weaknesses that remain are art-direction and content problems, not limits of Skia.

## What Skia does well here

- Deterministic CPU rasterisation, so renders hash identically (`deterministic_replay` QA).
- Anti-aliased vector strokes. These suit the stick-figure style, at any resolution.
- Gradients, blur image filters and additive blending. These give bloom, glows, light shafts, contact shadows and the motion-trail ghosts.
- It runs headless on any CI machine with no GPU.

## Measured limits

| Limit | Effect on the film | Workaround in place | Would another renderer fix it? |
|---|---|---|---|
| CPU only: about 1.3 s per 1080p frame with 3 motion-blur sub-samples | A 30 s render takes about 17 minutes | Preview scale (`--scale 0.5`) and stills for iteration; the final render runs overnight in CI | A GPU backend (moderngl/wgpu) would be about 10× faster. That changes speed, not quality |
| No real 3D lighting. Everything is a projected 2.5D room | Light is painted on: shafts, glows and haze | Hand-placed gradients and the projected contact shadows | Only a full 3D renderer. That would mean redesigning the art, which the brief forbids |
| Motion blur is temporal supersampling (3 samples) plus drawn trails | Very fast limbs can show 2–3 discrete copies | `motion_trails` ghosts the fast limbs between samples | A velocity-buffer blur would be smoother. It could be added in Skia as a post pass |
| No text shaping or fonts are needed for the film itself | — | — | — |
| The room colours used to be hard-coded constants | A second environment could not have its own look | **Fixed:** `EnvironmentSpec.theme` (`ThemeSpec`) drives the accent, alert, plane, background and dust colours. The defaults reproduce the original lab exactly | — |
| The open-door light is still the lab's cyan | In the amber foundry the open hatch glows cyan. It reads as daylight beyond, but it is not themed | None yet (listed in the defect report) | No. It is a small change to `ThemeSpec` |

## The adapter

```python
from apex.render.base import Renderer, make_renderer, BACKENDS
r = make_renderer("skia", width, height, env, styles, rigs)   # BACKENDS = {"skia": "apex.render.skia_renderer:SkiaRenderer"}
img = r.render(frame_state, camera_state, red_flash, fx, fade=..., trails=...)   # -> HxWx4 uint8
```

`Renderer` is a `typing.Protocol` with `W`, `H` and `render(...)`. A new backend registers a `"module:Class"` path in `BACKENDS`. It must return the same RGBA array, and the pipeline, QA (which probes frames) and the review tools then work unchanged.

**Migration path, if it is ever needed:**

1. Implement `render()` in the new backend, for example with GPU strokes.
2. Diff its frames against Skia's for the regression scenes (1B, 1C, 1D, Foundry Flip). Allow a small perceptual tolerance, since anti-aliasing differs.
3. Switch the default only once the visual review shows a real gain.

## Effects and sound polish in this pass

- **Impact burst** (`fx: burst`): impacts above 1000 u/s get 14 radial streaks, 10 debris specks and a short glow, on top of the ring and dust.
- **Motion trails:** ghost limbs from the poses 1/60 s and 1/30 s earlier, drawn only for limbs whose end effector moved more than 14 px. They are tinted with the character's glow colour.
- **Theme per environment:** the foundry's amber/charcoal palette against the lab's cyan/steel.
- **Audio:**
  - stereo mix, with each cue panned by its world x using an equal-power law (clamped to ±0.7);
  - a convolution room reverb (0.7 s synthetic impulse response, 14 % wet) on the effects bus;
  - the impact rebuilt as layers: thud, body, sub-bass sweep, crunch, debris ticks and ring;
  - the hum and the music bed on both channels.

**Recorded samples (added after the first quality pass).** A curated library of 33 freely licensed recordings is layered with the synthesiser (`apex/audio/samples.py`, `audio/sfx/`, credits in `audio/sfx/CREDITS.md`). The recordings are:

- metal footsteps;
- body thuds on the floor and metal impacts;
- the switch click;
- a force-field hum and a low boom for the gravity shift;
- air whooshes;
- a key/lock sound and sci-fi door open/close;
- a machine room-tone loop.

All are CC0 packs from OpenGameArt, and the licence on each pack's page was checked.

**How they are played:**

- Each cue picks a file per layer, deterministically from the seed. It applies about ±6 % pitch and ±1.5 dB gain variation.
- Harder impacts play lower.
- `synth_mix` keeps some of the synthesised body under each sample.

**Layer levels** were matched to the synthesised sounds by measuring each isolated sound (peak and RMS), not by ear. A human listening pass is still needed.

**Result:** the footsteps changed from pitched tonal blips to broadband transients (checked on spectrograms). The integrated loudness of the 1D mix is −17.8 LUFS (−16.9 synth-only) with a −1.0 dBFS peak and no clipped samples.

**Not covered by samples:** the music stingers (notice, startle, chime, resolve) and the slide scrape are still synthesised.
