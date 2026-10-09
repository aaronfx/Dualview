# CyronTech LTD website

Static HTML/CSS/JavaScript site. No npm installation, build command, or framework migration is needed.

## Structure

```
index.html                 CyronTech homepage
site.css                   Homepage styles and responsive layouts
studio.css                 Purple/dark CyronTech redesign and software illustrations
phone.css                  Modern handset illustration and Gopipways product styling
layout.css                 Consolidated five-section layout and consistent card grids
recording.css              Landscape phone recording demo, timer and record control
site.js                    Demo playback, reveal animations, local brief download
media-demo.js              Shared demo controller with cancellation and failure handling
assets/cyrontech-badge.png  Current purple/blue CyronTech CT badge
assets/cyrontech-logo.svg   Full wordmark with embedded badge and tagline
apps/dualview/index.html   Existing DualView landing page
apps/dualview/...          DualView styles, scripts, video, logo and platform assets
```

The app page links back to CyronTech. More app folders can be added under `apps/` later.

The 9 October 2026 audit added mobile navigation, stronger keyboard focus, 44px primary/link targets, larger supporting copy, and safe disabled form controls until the local download handler is installed. Changed CSS/JS URLs carry a revision query to refresh cached files. Playback race conditions are covered by local regression tests outside the upload package. See `exports/CyronTech-Homepage-Audit.md` in the workspace for findings, launch recommendations, and verification limits.

The hero video demo now uses a landscape phone frame and the DualView landing-page recording cues: moving sample footage, a playback-linked REC pulse, elapsed time, record/stop control, crop guide, and synchronized portrait preview. Both website controls pause/resume the same two videos. Autoplay is disabled for reduced-motion preferences.

The homepage is organized into five main sections: company introduction, a grouped product showcase with the phone demo and both apps, a consistent three-card services grid, the global mission, and project contact. Repeated feature sections and duplicate workflow blocks have been removed.

The homepage now features DualView and the live Gopipways web platform, with a global company mission: create world-leading apps that solve real problems. The DualView phone illustration has a metal frame, slim bezels, front-camera cutout, status icons, side buttons, and user-controlled sample-video playback. It is a website illustration, not a claim that this is the shipped app interface.

The revised homepage uses a full-width violet hero, dark benefit sections, layered original software illustrations, scroll reveals, a drawn workflow curve, and synchronized DualView video. Its visual direction is inspired by the Spaceship business-email page; no Spaceship images, logos, copy, pricing, or service claims are used. The earlier CyronTech design remains separately in the local `exports/cyrontech-site-v1` backup and is not included in this package.

## Update the existing Vercel project

1. Extract the ZIP. Open `cyrontech-site`.
2. In GitHub, open the existing `dualview-landing-page` directory in `aaronfx/Dualview`.
3. Upload the CONTENTS of `cyrontech-site` into that directory, preserving `assets/` and `apps/`. Replace the existing `index.html` with the new CyronTech homepage. Do not place another `cyrontech-site` folder inside it, and do not upload the ZIP as the site source.
4. Commit the update. Vercel will deploy the connected production branch by default.
5. Keep Root Directory `dualview-landing-page`, Framework Preset `Other`, Build Command overridden to empty, and Output Directory `.`. No environment variables are needed for this preview.
6. Visit your Vercel URL: `/` should show CyronTech and `/apps/dualview/` should show DualView.

Old root-level DualView styles/media may remain after an upload; the new homepage and app page do not use those old root copies. They can be removed separately after verifying deployment.

If you instead move all site files to the repository root, change Vercel Root Directory to `./`. These are alternate layouts; use one consistently.

## Local preview

From this folder:

```powershell
python -m http.server 5185 --bind 127.0.0.1
```

Open http://127.0.0.1:5185/ .

## Before public launch

- Supply the company's public contact email. The current project brief form downloads a local text file only and sends no data.
- Connect a real email/waitlist provider if launch signup is needed. DualView signup remains disabled.
- Finalize the applicable privacy policies and add their links.
- Add a real Play Store listing when available. No release date, store link, prices, clients or endorsements are invented.
- Remove each page's `noindex` meta tag and preview notice after the launch details are ready.
- Choose and connect the company domain. Domain purchase is not required to review this site.
- Confirm the Vercel plan permits the intended business use.

The homepage supports reduced motion, paired sample-video play/pause, keyboard navigation, and responsive layouts. Its new logo is an AI-generated design concept, not a trademark clearance.

See `assets/ASSET_SOURCES.md` and `apps/dualview/media/ASSET_SOURCES.md` for asset notes.
