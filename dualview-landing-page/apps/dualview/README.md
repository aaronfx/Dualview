# DualView landing page

Shoot once. Post both ways.

This is the current responsive HTML/CSS/JavaScript landing-page design, with the DualView app logo, local sample video, social platform logos, and workflow animations. No npm install or build step is needed.

## Upload to GitHub

Extract the ZIP and upload the contents of `dualview-landing-page` into your repository root. Keep `index.html` at the root and preserve the `media` folder and all file names. Do not upload only the HTML or the ZIP itself as the site source.

## Preview locally

From this directory run:

```sh
python -m http.server 5184
```

Open http://localhost:5184/.

## Hosting

This folder can be served as a static website. For GitHub Pages, choose the branch containing these files and its root directory as the publishing source. For a Git-connected host, use this repository as a plain static project without a build command.

## Current launch status

The page is a design preview: it retains its preview banner and noindex tag. Launch-email signup is visibly disabled until a real form provider and privacy policy are connected. Finalize these before public launch. Videos are labeled stock demonstrations, not footage recorded in the app. See `media/ASSET_SOURCES.md` for asset provenance.

No Flutter app files, signing keys, passwords, personal skills, or development screenshots are included.
