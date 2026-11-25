import {defineConfig} from 'vite';
import {createRequire} from 'node:module';

// Motion Canvas 3.17 ships a CommonJS plugin. Resolve its actual callable
// export explicitly when Vite loads our ESM configuration.
const require = createRequire(import.meta.url);
const loaded = require('@motion-canvas/vite-plugin');
const motionCanvas = typeof loaded === 'function' ? loaded : loaded.default;
if (typeof motionCanvas !== 'function') {
  throw new TypeError('Motion Canvas Vite plugin does not expose a callable factory');
}
export default defineConfig({plugins: [motionCanvas({project: './src/project.ts'})]});
