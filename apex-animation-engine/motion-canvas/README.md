# APEX Motion Canvas preview (experimental)
From the engine root, using the editable Python install:
```powershell
python -m apex.scene.presentation_export examples/the_rescue.json --scene rescue -o motion-canvas/src/native.json
cd motion-canvas
npm install
npm run check
npm run dev
```
Open the local Vite address. The native export is generated, not checked in.
This is a diagnostic world-space joint/prop preview; it is not yet a replacement for the native renderer. No native camera, depth sorting, glyph outlines, effects, audio, or automated MP4 export yet. Do not judge reference parity from this prototype.
