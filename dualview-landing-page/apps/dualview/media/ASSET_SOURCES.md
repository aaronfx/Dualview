# Landing page assets

## Social platform logos

- Local files: `social/youtube.svg`, `social/instagram.svg`, `social/tiktok.svg`, `social/facebook.svg`.
- Source: https://github.com/simple-icons/simple-icons (Simple Icons v16 via `https://cdn.jsdelivr.net/npm/simple-icons@16/icons/[slug].svg`). Downloaded 9 October 2026.
- Simple Icons project license: CC0-1.0. Platform marks remain associated with their respective owners.
- Used as output-destination cues beside landscape and portrait videos, rather than as partner/customer logos. This page describes saving MP4s and manually uploading to social pages; it does not claim platform account connections or automated posting.

## Current recording demo video

- Local files: `recording-demo.mp4` and `recording-poster.jpg`.
- Source title: “A woman dancing in the sun”.
- Source page: https://mixkit.co/free-stock-video/a-woman-dancing-in-the-sun-1121/
- Download: https://assets.mixkit.co/videos/1121/1121-720.mp4
- License: Mixkit Stock Video Free License, verified on the individual item page on 9 October 2026; commercial and personal usage allowed. License overview: https://mixkit.co/license/#videoFree
- Preparation: first 10 seconds, 1280 × 720, 24fps, H.264, no audio, faststart. Poster extracted at 2 seconds with FFmpeg.
- Presentation: the same clip in recording, landscape, and vertical previews. Timers and playback are synchronized. The vertical preview shows a fixed crop positioned at 42% of source width to retain the subject.
- Recording controls are an interactive website demonstration, not a live camera capture. Page copy explicitly identifies stock-video footage. No endorsement or real app capture is claimed.
- The previous Spencer Backman still photograph is no longer used; its source information below records the earlier design iteration.

## DualView logo

`dualview-logo.svg` translates the paths and colors from `android/app/src/main/res/drawable/dualview_icon.xml`, the icon selected in the Android application manifest. The web version rounds the background corners; the frame geometry and recording mark are unchanged. The unused Flutter launcher PNG is not the app's current icon.

## Mountain photograph

- Local file: `mountain-hiker.jpg`, downloaded at 1800px width on 9 October 2026.
- Photographer: Spencer Backman.
- Photo: “Man wearing black jacket standing on mountain”.
- Source: https://unsplash.com/photos/man-wearing-black-jacket-standing-on-mountain-5DcvcczzYg0
- Download: https://images.unsplash.com/photo-1513382848136-770cf055a751?auto=format&fit=crop&fm=jpg&q=85&w=1800
- License reviewed: https://unsplash.com/license (Unsplash License, permits downloading and using images in commercial projects; restrictions still apply).
- Usage: sample imagery in paired landscape/vertical frames, explicitly credited as stock imagery. This is not represented as an actual DualView recording or an endorsement by the photographer or subject.
- Cropping: the wide and tall preview use the same image and centered crop. CSS sets the tall image to the width of the equivalent landscape frame so both use the same source region vertically.

No image is hotlinked at runtime. Replace the sample with permission-cleared real app footage for a product demonstration before making claims about actual captured output quality.
