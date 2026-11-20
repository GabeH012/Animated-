// node scripts/stills.mjs [t1 t2 ...]  - bundle once (fixed outDir), render stills at the given seconds, make a grid
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
export const BROWSER = '/opt/pw-browsers/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell';
const outDir = path.join(ROOT, 'build');
const qa = path.join(ROOT, 'images', 'hurricane', 'qa', 'stills');
fs.mkdirSync(qa, {recursive: true});

const times = process.argv.slice(2).map(Number);
const ts = times.length
  ? times
  : [0, 1.3, 1.6, 2.2, 2.6, 3.0, 3.4, 3.8, 4.3, 5.2, 6.05, 7.0, 7.95, 8.15, 8.6, 9.6, 10.9, 11.6, 12.2, 12.7, 13.4, 14.78];

const serveUrl = await bundle({entryPoint: path.join(ROOT, 'src', 'index.ts'), outDir});
const composition = await selectComposition({serveUrl, id: 'NukeHurricane', browserExecutable: BROWSER});
const files = [];
for (const t of ts) {
  const frame = Math.min(composition.durationInFrames - 1, Math.round(t * 60));
  const output = path.join(qa, `f${String(frame).padStart(4, '0')}.png`);
  await renderStill({composition, serveUrl, frame, output, scale: 0.5, browserExecutable: BROWSER, chromiumOptions: {gl: 'swangle'}});
  files.push(output);
  console.log('still', t, frame);
}
// grid with ffmpeg: 6 per row, frame number + time drawn under each
const cols = 6;
const rows = Math.ceil(files.length / cols);
const inputs = files.flatMap((f) => ['-i', f]);
const scaled = files.map((_, i) => `[${i}:v]scale=270:480,drawtext=text='${ts[i].toFixed(2)}s':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[v${i}]`).join(';');
const pads = Array.from({length: rows * cols - files.length}, (_, i) => `color=c=gray:s=270x480:d=1[p${i}]`);
const labels = [...files.map((_, i) => `[v${i}]`), ...pads.map((_, i) => `[p${i}]`)];
const layout = labels.map((_, i) => `${(i % cols) * 270}_${Math.floor(i / cols) * 480}`).join('|');
const filter = [scaled, ...pads, `${labels.join('')}xstack=inputs=${labels.length}:layout=${layout}`].join(';');
execFileSync('ffmpeg', ['-v', 'error', '-y', ...inputs, '-filter_complex', filter, '-frames:v', '1', path.join(ROOT, 'images', 'hurricane', 'qa', 'contact.png')]);
console.log('contact sheet done');
