// Building blocks for the Comlogue social templates: page shell, phone mockups, logo, icons.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
export const REPO = resolve(here, '../../..');
const SCREENSHOTS = resolve(REPO, 'docs/screenshots');

export const POST = [1080, 1350];   // 4:5 feed post or carousel slide
export const STORY = [1080, 1920];  // 9:16 story, reel frame or highlight cover
export const SQUARE = [1080, 1080];

// Fonts are inlined as data URIs so pages render the same anywhere, offline.
const fontsCss = readFileSync(resolve(here, 'fonts/fonts.css'), 'utf8').replace(/url\(([^)]+\.woff2)\)/g, (_, file) =>
  `url(data:font/woff2;base64,${readFileSync(resolve(here, 'fonts', file)).toString('base64')})`);
const styles = readFileSync(resolve(here, 'styles.css'), 'utf8');

export function page({ bg = 'paper', dark = bg !== 'paper', body }) {
  return `<!doctype html><html><head><meta charset="utf-8">
<style>${fontsCss}\n${styles}</style></head>
<body><div class="canvas bg-${bg}${dark ? ' on-dark' : ''}">${body}</div></body></html>`;
}

/** An app screenshot from docs/screenshots in an iPhone frame. */
export function phone({ shot, w, x, y, rotate = 0, z = 2 }) {
  const src = pathToFileURL(resolve(SCREENSHOTS, `${shot}.png`)).href;
  return `<div class="phone" style="--w:${w}px; left:${x}px; top:${y}px; transform:rotate(${rotate}deg); z-index:${z}">
    <img src="${src}" alt=""></div>`;
}

export function glow({ x, y, size, opacity = 0.7 }) {
  return `<div class="glow" style="left:${x}px; top:${y}px; width:${size}px; height:${size}px; opacity:${opacity}"></div>`;
}

let gradientId = 0;
/** The app icon's two overlapping rings: two voices in one conversation. */
export function logo({ light = true, size = 64 } = {}) {
  const id = `g${gradientId++}`;
  const a = light ? '#fff' : `url(#${id})`;
  const b = light ? 'rgba(255,255,255,.62)' : `url(#${id})`;
  return `<svg viewBox="0 0 104 64" style="width:${size * 1.625}px; height:${size}px" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="0" x2="1"><stop offset="0" stop-color="#5146E6"/><stop offset=".6" stop-color="#8B5CF6"/><stop offset="1" stop-color="#F2708A"/></linearGradient></defs>
    <circle cx="70" cy="32" r="23" fill="none" stroke="${b}" stroke-width="9" ${light ? '' : 'opacity=".55"'}/>
    <circle cx="34" cy="32" r="23" fill="none" stroke="${a}" stroke-width="9"/></svg>`;
}

export function brand({ x = 84, y, light = true, text = 'Comlogue', right = false }) {
  const pos = right ? `right:${x}px` : `left:${x}px`;
  return `<div class="brand" style="${pos}; top:${y}px; color:${light ? '#fff' : 'var(--ink)'}">${logo({ light, size: 40 })}${text}</div>`;
}

const paths = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  arrow: '<path d="M4 12h15M13 6l6 6-6 6"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
  bell: '<path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  pause: '<path d="M8 5v14M16 5v14"/>',
  people: '<circle cx="8" cy="8" r="3"/><circle cx="16.5" cy="8" r="3"/><path d="M2.5 19a5.5 5.5 0 0 1 11 0M12.5 15.5a5.5 5.5 0 0 1 9 3.5"/>',
  briefcase: '<rect x="3" y="7" width="18" height="13" rx="2.5"/><path d="M8.5 7V5.5A2 2 0 0 1 10.5 3.5h3a2 2 0 0 1 2 2V7M3 13h18"/>',
  sparkles: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
  question: '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.2a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .9-1 1.5v.5M12 16.8v.2"/>',
  wave: '<path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  phone: '<rect x="6" y="2.5" width="12" height="19" rx="3"/><path d="M11 18.5h2"/>',
};

export function icon(name, { color = 'currentColor', width = 2.4 } = {}) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`;
}

/** Carousel progress dots: `index` of `count`. */
export function dots({ index, count, x = 84, y }) {
  return `<div class="dots" style="left:${x}px; top:${y}px">${Array.from({ length: count }, (_, i) => `<i class="${i === index ? 'on' : ''}"></i>`).join('')}</div>`;
}

export const COMING_SOON = 'Coming soon on iPhone';
