// Renders every asset in assets.mjs to a PNG at its exact size, then preview.png: the profile grid as it will look.
// Usage, from marketing/instagram:  npm install && npm run render   (or: node src/render.mjs [path filter])
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { assets } from './assets.mjs';
import { page } from './kit.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const filter = process.argv[2] ?? '';
const work = mkdtempSync(join(tmpdir(), 'comlogue-ig-'));

async function shoot(browser, html, [width, height], out) {
  const tab = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  // A file:// page can load the app screenshots, which are file:// URLs too.
  const file = join(work, 'page.html');
  writeFileSync(file, html);
  await tab.goto(pathToFileURL(file).href, { waitUntil: 'load' });
  await tab.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((img) => img.complete ? null : new Promise((done) => { img.onload = img.onerror = done; })));
    const broken = [...document.images].filter((img) => !img.naturalWidth).map((img) => img.src);
    if (broken.length) throw new Error(`Missing image: ${broken.join(', ')}`);
  });
  mkdirSync(dirname(out), { recursive: true });
  await tab.screenshot({ path: out, clip: { x: 0, y: 0, width, height } });
  await tab.close();
}

const browser = await chromium.launch();
try {
  const chosen = assets.filter((a) => a.path.includes(filter));
  for (const asset of chosen) {
    await shoot(browser, asset.html, asset.size, resolve(OUT, asset.path));
    console.log(`${asset.path}  ${asset.size.join('×')}`);
  }

  // The profile grid crops each 4:5 post to 3:4 around its centre; newest first, three across.
  const posts = assets.filter((a) => a.path.startsWith('posts/')).map((a) => a.path).sort().reverse();
  if (!filter || filter.startsWith('posts')) {
    const cells = posts.map((p) => `<div class="cell"><img src="${pathToFileURL(resolve(OUT, p)).href}"></div>`).join('');
    await shoot(browser, page({ bg: 'paper', body: `
      <style>
        .grid { position:absolute; inset:60px; display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; }
        .cell { aspect-ratio: 3 / 4; overflow:hidden; background:#ddd; }
        .cell img { width:100%; height:100%; object-fit:cover; }
      </style>
      <div class="grid">${cells}</div>` }), [1200, 1460], resolve(OUT, 'preview.png'));
    console.log('preview.png');
  }
} finally {
  await browser.close();
  rmSync(work, { recursive: true, force: true });
}
