---
name: gopipways-video-production
description: Produce narrated stick-figure / doodle-explainer videos (vertical 9:16 or landscape) from a voiceover audio file, entirely in code (HTML canvas + Playwright + ffmpeg). Use for Gopipways, Adlytics or client story/explainer/ad videos, parables, trend explainers, or any "animate this voiceover" request. Covers audio timing, scene planning, character rig, continuous environment, interactions (doors, hands touching faces, phones), transitions, vertical layout, rendering, QA and the mistakes already made once.
---

# Gopipways video production (code-drawn stick-figure explainers)

Reference implementation lives in `stranger-video/` of this repo:
- `index5.html` = current engine (vertical 1080x1920, one continuous village, real interactions). Read it before building anything new.
- `index3.html` = landscape/doodle-card version (white backgrounds, props, labels). `index4.html` = vertical adaptation of v3.
- `render.js` = Playwright frame renderer (`PAGE=index5.html node render.js <outDir> 24 [t1,t2,...]`).
- Outputs: `the-stranger*.mp4`.

## 0. What the user wants (learned over many rounds of feedback)
- Look like the reference videos: thick black outline, round white heads, flat muted colour, doodle props, one idea per beat. Detailed illustrated look cannot be matched in code; be honest about this and offer the hybrid (user supplies generated scene images, we animate) when they want painted detail.
- Animations must be REAL and SPECIFIC, never generic. Every narrated action must be literally shown: if the narration says he wipes tears, the hand must reach and touch the face; if a door is opened/closed, the door must visibly open/close and people must use it properly.
- The environment must be one continuous world that blends with the characters (ground, shadows, houses, weather, time of day), not figures floating on blank white.
- Scenes must match the voiceover line by line, with a visible transition at every scene change (never more than ~5 s without a cut/transition; we use 24 scenes in 50 s).
- Vertical 9:16 is the delivery format for social. All on-screen text must stay inside the frame.
- Always deliver the file to the user (SendUserFile), commit, push to the designated branch, and keep a draft PR.


## 0b. Orientation rule (decided by the user: "use the length for the orientation")
- Pick the orientation from the narration length, do not ask unless the user overrides:
  - under 90 seconds -> VERTICAL 9:16 (1080x1920), the short-form format (Reels, TikTok, Shorts).
  - 90 seconds or longer -> LANDSCAPE 16:9 (1280x720), the long-form / YouTube format.
- State the choice and the length in the reply ("49.6 s, so vertical"), and offer the other orientation if they want both.
- Engine support (stranger-video/index5.html): vertical is the default. Landscape = `ORIENT=landscape`, which makes the page add `#render&landscape` (canvas 1280x720, no vertical offset, zoom 1.0, caption 42 px at the bottom). Render length comes from the audio: `DUR=<seconds>` (defaults to `window.DURATION`).
```
PAGE=index5.html node render.js $OUT 24                      # vertical 1080x1920
PAGE=index5.html ORIENT=landscape node render.js $OUT 24     # landscape 1280x720
DUR=132.4 PAGE=index5.html ORIENT=landscape node render.js $OUT 24
```
- For a NEW story, copy `index5.html` to a new file, replace the scene list (`add(...)` blocks) and `CAPS`, set `window.DURATION` to the audio length, keep the engine/helpers. Check both orientations at least on a few frames; long landscape videos need more scenes (about one per phrase) and more varied camera/zoom so it does not feel static.
- New-character ideas for Jesus/angel stories (not built yet): robe + soft glow for Jesus, wings + halo for angels, shepherd, disciples, crowds; settings: manger, hillside, sea/boat, desert road, garden, empty tomb, heaven/clouds; effects: golden rays, star, dove, calming waves. Add them as presets using the same `figure()` rig and keep hands touching real targets.

## 1. Inputs and audio analysis
1. Get the narration mp3 (ElevenLabs etc.). `ffprobe` for duration.
2. Cut points: use silence detection, which is robust even when no transcript exists:
   `ffmpeg -i narr.mp3 -af silencedetect=noise=-32dB:d=0.28 -f null - 2>&1 | grep silence`
   Speech segments between silences = phrases = scene boundaries.
3. Transcript: the sandbox usually cannot download Whisper models (HF proxy 403). `pip install pocketsphinx` works offline (model bundled): convert to 16k mono wav, decode, print word segments with times. Accuracy is poor (it garbled the climax of the Stranger story), so ALWAYS tell the user which lines are guesses and ask for the real script. Put captions in an editable `CAPS=[[start,end,"text"],...]` array.
4. Never claim to have heard the audio. Say timing came from silence detection and a rough transcript.

## 2. Scene planning
- One scene per phrase (2-3 s). Write a beat sheet: time range, what is literally shown, which character does what, which prop, which environment state (weather, time of day, door state).
- Alternate framing: wide establishing, medium two-shot, close-up for the emotional contact beat (use a per-scene zoom spec `[zoom, focusX, focusY]`).
- Colour/mood changes carry the story: rain -> clearing sky -> warm gold at the miracle; interior scenes for private moments (prayer, small meal).
- Keep one timeline of world positions (`camAt(t)`, `strX(t)`) so characters and camera move continuously between scenes.

## 3. Engine architecture (canvas 2D, deterministic `draw(t)`)
- Everything is a pure function of time `t` (so frames can be rendered in any order). `window.draw=draw`.
- Design space 1280x720 (`W,H`), ground baseline `GY=600`. For vertical, canvas is `CW=1080,CH=1920`; each scene is drawn inside a transform that centres the design area (`translate(CW/2,CH/2-140)`, scale `G~0.96*(1+0.06*u/dur)` slow push-in). Fill backgrounds with huge rects (`BIG=3000`) so nothing ends at the design edges.
- Scenes: `add(start,end,bgColour,(u,t)=>{...},[zoom,fx,fy])`, `u` = local time.
- Transitions (0.4 s, rotating): slide left, circle reveal, slide down, cross-fade. Render outgoing scene frozen on its last frame and incoming scene to offscreen canvases, then composite.
- Captions: bold 60 px white with black stroke, lower third (`y=CH-420`), max width 940. Text helper `txt()` measures itself and shrinks/shifts to stay inside a 70 px margin, using `c.getTransform()`; use it for ALL screen text.

### Character rig (`figure(f)`)
- Stick figure with 2-bone IK for arms and legs: `ik(shoulder, target, l1=30, l2=30)`. Parameters: `x,y,s(scale),flip(+1/-1 facing),hipY,feet[[x,y],[x,y]],hands[[x,y],[x,y]],lean,tilt,hs(head scale),hair,hood,coat,face{m,up,mo,brow,blink}`.
- Local units: height ~160, head radius 22, global `FS` (2.25) scales everything. Facing: `flip:-1` faces screen-left, local +x is forward.
- `figure()` RETURNS `{hx,hy,hr}` (head centre/radius in design coords). Use it to aim other characters' hands at it. `loc(f,wx,wy)` converts a world point into that character's local hand coordinate (needed because of flip and scale).
- Presets: `stranger()` (hood + grey cloak), `mother()`, `boy()` (s .72, big head hs 1.45), `villager()`. Preset functions must `return figure(...)`.
- Walk cycle: `walkFeet(p,stride,lift)`, `walkArms(p)`, with `p=t*6.5`. Sit pose `sitS(fx)`, kneel `hipY:-40 feet [[-14,0],[26,0]]`.
- Always draw a ground shadow (`shadowAt`) under people.

### Environment
- `street(t,cam,{dry,warm,panel})`: sky gradient (rain-grey -> warm gold via `warmAt(t)`), parallax mountains, ground, road band, puddles, grass, trees, fence, house A and the mother's house at world x `HX=1700`. `rainFx(t,amount)` draws rain over everything.
- `interior(t,{morning})`: wall, floor, window (rain streaks or sunlight cone), bed, shelf. Use for prayer / small-meal beats.
- World coordinates + `cam` offset: screen x = world x - cam. Keep characters out of the front of the door when it is closed.

## 4. Real interactions (the things the user caught)
### Doors (`houseExt`, `doorPanel`, `doorOpen(t)`, `doorEdge(t)`, `inDoorway`)
- Door state is a function of time (opens when she answers, closes only after she is outside).
- Panel is hinged on the RIGHT and swings toward the viewer so it never blocks the path to the left.
- People inside the doorway are drawn clipped to the doorway rectangle BEFORE the door panel (`inDoorway(cam,fn)`); stepping out = walk forward toward the viewer (y from GY-22 to GY) then sideways. People outside are drawn AFTER the panel. This is what stops "walking through the wall".
- Closing the door: character stops beside the house facing away, reaches back with the near arm; the hand target is the door's free edge (`doorEdge(t)`) so the hand follows the panel while it swings shut. Only then does she walk off.
### Hand on face (wiping tears)
- Draw the kneeling character first, take its `{hx,hy,hr}`, place the child at `hx+104`, target the cheek `(hx+hr*0.78, hy+hr*0.3+wobble)`, convert with `loc()`, draw a cloth at the hand, add tear drops on the cheek that fade as it is wiped, switch the face to a smile afterwards, and use a close-up zoom. Verify in a frame that the cloth is ON the face.
### Footprints
- Define the path once: `PP(f)` returns world x, y and scale (perspective: smaller and higher as he walks away). Place each print exactly under his foot when he passes (`tpass`), rotate toes along the walking direction, make them start faint then glow at the narrated moment. Reuse the same `trailWorld()` in every later scene so the trail always matches where he walked. Do NOT cut away from the walk with a separate unrelated trail scene; keep the walk and the glow in one continuous shot.
### Phone call
- Never a floating prop over the face. Sequence: buzz in pocket (body shake) -> hand goes to pocket -> pulls phone out to chest height -> screen lit with caller avatar, "CALLING" text, red/green buttons -> ring arcs and glow -> close-up zoom. Next beat: at ear, listening, eyes widen, then joy jump and a readable message card ("YOU GOT THE JOB!") placed above, away from faces. Keep other characters out of the arc area.
### General
- Objects handed over must be at the real hand position (compute from `loc` inverse, not guessed).
- Any text placed with `at()` must not overlap faces, roofs or props; check frames.

## 5. Render and encode
```
cd stranger-video
PAGE=index5.html node render.js $OUT 24            # all frames (JPEG via canvas.toDataURL)
PAGE=index5.html node render.js $OUT 24 12,18.9    # only selected times -> t12.jpg ... for QA
ffmpeg -framerate 24 -i $OUT/f%05d.jpg -i narration.mp3 -c:v libx264 -pix_fmt yuv420p -crf 21 -c:a aac -shortest out.mp4
```
- Use scratchpad dirs for frames. Do not `rm -f $VAR/*` (the safety check blocks it); write into fresh directories instead.
- Playwright is Node (`require('playwright')`), no pip package.
- ~1200 frames render in about 25-60 s.

## 6. QA loop (mandatory before sending)
1. Render ~24 sample frames (one per scene plus the interaction moments, e.g. door at 28.95/29.15/29.4/29.7, wipe at 18.9/19.6/20.4) and build contact sheets with ffmpeg `hstack`/`xstack`; view them.
2. Check: text cut off at edges, text over faces/roofs, characters overlapping doors or each other, objects not in hands, wrong facing direction, glow/trail not under feet, empty bands, caption overlap.
3. Verify audio stream exists (`ffprobe`), duration matches.
4. Tell the user honestly: what was verified from stills only, what is a guess (transcript), what is still simple.

## 7. Delivery checklist
- `SendUserFile` the mp4 (display render first time, attach when re-sending).
- Commit to the designated branch with the session attribution lines, push, ensure a draft PR exists and is subscribed (`subscribe_pr_activity`). Vercel bot comments are noise; only react to failed checks or real reviews.
- Keep older versions in the folder; name new ones `-v2`, `-v3`.
- Ask only for what is missing: the real script, orientation, any scene timestamps that still look wrong.

## 8. Known limits and honest statements
- Code-drawn stick figures are simpler than painted/illustrated references. Offer the hybrid (user-generated images, we animate with camera moves, rain, glow, captions).
- No voice generation or lip-sync audio here; a talking-mouth meme needs mouth shapes keyed to the audio envelope (not built yet).
- Transcription is unreliable offline; always confirm key lines.
- Vertical frame: the scene occupies a band in the middle; recompose scenes or add headline/CTA areas if the user wants bigger characters.

## 9. Mistakes already made (do not repeat)
- Blank white backgrounds / generic props -> user said it does not blend with the story.
- Door panel drawn over people, people walking out through the wall, standing in front of the closed door.
- Boy's hand not touching the face; fixed with anchor-based IK targeting + close-up.
- Footprints on an unrelated perspective trail instead of where he stepped.
- Phone scene too small, covering faces, no pull-out animation.
- Text clipped in vertical (labels placed at fixed x). Always route text through the clamping `txt()`.
- Guessing the climax line from a bad transcript; flag it and ask.
- Pre-setting FS/scale inconsistently between figure and props; compute prop positions from the same `FS`.

## 10. Reference studies
- `reference-faith-in-god.md`: study of the @faithingod02 "Faith in God" Shorts channel (title formula, hashtags, story arc, visual style, numbers). Use it when planning Jesus/angel parable videos.
- `story-and-title-framework.md`: title formulas, a bank of 20 emotional titles, the hook/body/payoff/CTA structure with timings, CTA bank and three ready narration scripts. Use it to write or pick the story before building scenes.

## 11. Thumbnails (Ink-Explainer style reference)
- Style learned from the "Ink Explainer" channel (user screenshot): one big expressive stick-figure face on a saturated background, 1-3 hook words in thick black-outlined letters (yellow + white), usually ending in a question mark (NO SLEEP? / STILL SURVIVED? / BORN TO KILL?), a tiny scene or prop on the other side, high contrast, 16:9, readable at phone-thumbnail size.
- Our generator: `stranger-video/thumb.js` (run `node thumb.js thumbnails`) calls `drawThumb('A'|'B'|'C')` in `lastloaf.html` and writes 1280x720 PNGs. Make 3 variants per video for A/B testing: A = object + emotion ("LAST LOAF?"), B = mystery character ("WHO WAS HE?"), C = reveal question ("HE KNEW HER NAME?").
- Face rules: worried/sad brows need a NEGATIVE `brow` value (positive makes the face look angry). Keep text clear of faces; no more than 3 words; yellow first line, white second.
- `reference-ink-explainer.md`: study of the Ink Explainer channel (the model for a long-form doodle-explainer channel): title/thumbnail formula, hit distribution, measured pacing (cut every ~2.8 s), and how to adapt it to a faith channel.

## 12. Long horizontal explainer pipeline (Ice Age video, 7 min, 1920x1080)
Source: `ice-age/` (core.js engine copy, props.js, scenes1-3.js, main.js, `ice.html` is the concatenation). Lessons:
- **Timing**: silencedetect splits at commas and mid-sentence, so sentence-to-segment mapping drifts. Use pocketsphinx word times (`Decoder(samprate=16000, logfn='/dev/null')`, default model) and difflib-align the script words to the ASR words; interpolate unmatched words. Sentence starts landed within about 1 s. Use `T(i)` = start time of sentence i.
- **Scenes**: `add(start,end,bg,(u,t)=>{...},[zoom,fx,fy])`; ends are re-chained so there are no gaps; keep every scene at 5 s or less (check with a script).
- **Layout**: design 1280x720, scale 1.5 to 1920x1080; sentence captions at the bottom, so keep labels above y=560; never put zoom on scenes with top labels (text leaves the frame); keep tag/label text inside its box (shorten the text).
- **QA**: render every scene midpoint, tile contact sheets (PIL, 5x4, label index), fix, then render the full run. 4 parallel Playwright shards (`render2.js <out> <fps> <shard> <n>`) render 10k frames in under 2 minutes.
- **Mux**: frames at 24 fps + narration + low pink-noise wind bed (lowpass 900, volume 0.06).

## 13. Generated-image (Ken Burns) pipeline (Ice Age video, preferred when images exist)
`ice-age/ken_main.js` + `build_ken.py` + `render3.js`. User supplies one image per scene (`001.jpg`..); scene timings come from the word-aligned scene list. Serve the images over local http (`python3 -m http.server`) so the canvas is not tainted, then render 4 shards. Effects: 7 pan/zoom moves by index, 0.3 s crossfade/slide/circle transitions, yellow outlined keyword labels (Ink Explainer style), sentence captions, vignette, light snow overlay on outdoor scenes, text overlay for button images. Master encode crf 23 is ~190 MB; web encode (`-crf 29 -maxrate 3500k`) is ~94 MB.
