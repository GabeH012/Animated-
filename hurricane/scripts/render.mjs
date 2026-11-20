// node scripts/render.mjs preview|final  - bundle once to build/, render the composition
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import os from 'node:os';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const BROWSER = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const mode = process.argv[2] ?? 'preview';
const serveUrl = await bundle({entryPoint: path.join(ROOT, 'src', 'index.ts'), outDir: path.join(ROOT, 'build')});
const composition = await selectComposition({serveUrl, id: 'NukeHurricane', browserExecutable: BROWSER});
const final = mode === 'final';
const outputLocation = path.join(ROOT, 'out', final ? 'nuke-hurricane-4K.mp4' : 'preview-half.mp4');
let last = -1;
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation,
  scale: final ? 2 : 0.5,
  crf: final ? 16 : 23,
  imageFormat: final ? 'png' : 'jpeg',
  pixelFormat: 'yuv420p',
  browserExecutable: BROWSER,
  chromiumOptions: {gl: 'swangle'},
  concurrency: Math.max(1, os.cpus().length),
  audioBitrate: '320k',
  onProgress: ({progress}) => {
    const p = Math.floor(progress * 20);
    if (p !== last) {
      last = p;
      console.log(`${mode} ${Math.round(progress * 100)}%`);
    }
  },
});
console.log('done', outputLocation);
