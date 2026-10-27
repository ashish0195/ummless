// Every Instagram asset: where it's written, its size and its page. Minimal on purpose: one short headline, at
// most one line under it, one phone. The details live in the captions (../captions.md), not on the image.
import { page, phone, glow, brand, logo, icon, dots, POST, STORY, SQUARE, COMING_SOON } from './kit.mjs';

const assets = [];
const add = (path, size, html) => assets.push({ path, size, html });

// ================================================================ feed posts (1080 × 1350)
// Numbered in posting order. The grid shows the newest first, so the backgrounds alternate per row:
//   09 paper   08 aurora  07 night
//   06 aurora  05 night   04 paper
//   03 night   02 paper   01 aurora

/** Headline, an optional line, and a phone rising from the bottom edge. */
function phonePost({ bg, title, sub, shot, size = '' }) {
  const dark = bg !== 'paper';
  return page({ bg, body: `
    ${brand({ y: 84, light: dark })}
    <div class="block" style="top:196px">
      <div class="hero ${size}">${title}</div>
      ${sub ? `<div class="sub">${sub}</div>` : ''}
    </div>
    ${glow({ x: 190, y: 640, size: 700, opacity: dark ? 0.55 : 0.3 })}
    ${phone({ shot, w: 600, x: 240, y: sub ? 640 : 590 })}
  `});
}

/** Words only, centred, for the posts that are a single idea. */
function wordPost({ bg, title, sub, size = 'xl' }) {
  const dark = bg !== 'paper';
  return page({ bg, body: `
    <div class="center">
      <div class="hero ${size}">${title}</div>
      ${sub ? `<div class="sub">${sub}</div>` : ''}
    </div>
    ${brand({ y: 1206, light: dark })}
  `});
}

add('posts/01-meet-comlogue.png', POST, page({ bg: 'aurora', body: `
  ${glow({ x: 90, y: 260, size: 900, opacity: 0.45 })}
  <div class="center">
    ${logo({ light: true, size: 110 })}
    <div class="hero m" style="margin-top:56px">Say what you mean.<br>Be understood.</div>
    <div class="sub">A friendly AI coach. One minute a day.</div>
    <div class="soon">${COMING_SOON}</div>
  </div>
`}));

add('posts/02-one-minute.png', POST, phonePost({
  bg: 'paper', title: 'Speak better.<br>One minute a day.', shot: 'daily' }));

add('posts/03-gd.png', POST, phonePost({
  bg: 'night', title: 'Practise the GD<br>before the real one.', size: 's', shot: 'groupIndia' }));

add('posts/04-no-streaks.png', POST, phonePost({
  bg: 'paper', title: 'No streaks<br>to lose.', sub: 'Miss a day. Nothing resets.', shot: 'today' }));

add('posts/05-hard-talk.png', POST, phonePost({
  bg: 'night', title: 'Rehearse the<br>hard conversation.', size: 's', shot: 'spar' }));

add('posts/06-one-thing.png', POST, phonePost({
  bg: 'aurora', title: 'One thing<br>to try next.', sub: 'Feedback you can use today.', shot: 'dailyFeedback' }));

add('posts/07-hinglish.png', POST, wordPost({
  bg: 'night', title: 'Hinglish?<br><span class="grad-soft">Bilkul.</span>',
  sub: 'Practise in English, <span class="deva">हिन्दी</span> or Hinglish.' }));

add('posts/08-interview.png', POST, phonePost({
  bg: 'aurora', title: 'Rehearse the<br>interview first.', shot: 'group' }));

add('posts/09-accent.png', POST, wordPost({
  bg: 'paper', title: 'Your accent<br>is not a <span class="grad-text">mistake.</span>',
  sub: 'We coach clarity. Never accent.', size: '' }));

// ================================================================ carousels (1080 × 1350 slides)

const swipe = (light) => `<div class="swipe" style="right:84px; top:1214px; color:${light ? '#fff' : 'var(--ink)'}">Swipe
  ${icon('arrow', { color: light ? '#fff' : 'var(--ink)', width: 3 }).replace('<svg', '<svg style="width:34px;height:34px"')}</div>`;

/** A tip: its number, a short title, and the same sentence before and after. */
function tipSlide({ dark, n, count, title, said, tryText }) {
  return page({ bg: dark ? 'night' : 'paper', body: `
    <div class="block" style="top:110px">
      <div class="num ${dark ? 'grad-soft' : 'grad-text'}">${n}</div>
      <div class="h2" style="margin-top:34px">${title}</div>
    </div>
    <div class="block pair" style="top:620px">
      <div class="said"><b>Instead of</b>${said}</div>
      <div class="try"><b>Try</b>${tryText}</div>
    </div>
    ${dots({ index: n, count, y: 1240 })}
  `});
}

function carousel(name, { dark, cover, tips, cta }) {
  const count = tips.length + 2;
  const slide = (i) => `carousels/${name}/${String(i + 1).padStart(2, '0')}.png`;
  add(slide(0), POST, page({ bg: dark ? 'night' : 'aurora', body: `
    ${glow({ x: 200, y: 500, size: 900, opacity: 0.45 })}
    <div class="block" style="top:150px"><div class="hero xl">${cover}</div></div>
    ${dots({ index: 0, count, y: 1240 })}
    ${swipe(true)}
  `}));
  tips.forEach((tip, i) => add(slide(i + 1), POST, tipSlide({ dark, n: i + 1, count, ...tip })));
  add(slide(count - 1), POST, page({ bg: 'aurora', body: `
    ${brand({ y: 84 })}
    <div class="block" style="top:196px"><div class="hero s">${cta.title}</div></div>
    ${glow({ x: 190, y: 600, size: 700, opacity: 0.55 })}
    ${phone({ shot: cta.shot, w: 560, x: 260, y: 560 })}
    ${dots({ index: count - 1, count, y: 1240 })}
  `}));
}

carousel('meetings', {
  cover: '5 ways to<br>sound clearer<br>in meetings',
  tips: [
    { title: 'Lead with<br>the point.', said: '“So, I looked into a few things this week, and…”',
      tryText: '“We should push the launch by a week. Here\'s why.”' },
    { title: 'One idea<br>per sentence.', said: '“We could migrate, but there\'s the vendor and also the budget, which…”',
      tryText: '“The migration is doable. The vendor is the risk.”' },
    { title: 'Pause before<br>what matters.', said: '“…and, um, basically, the main thing is the deadline.”',
      tryText: '“The main thing is… the deadline.”' },
    { title: 'Name the<br>next step.', said: '“Cool, let\'s keep thinking about it.”',
      tryText: '“Priya drafts the plan by Thursday. We decide Friday.”' },
    { title: 'Hand the<br>floor over.', said: '“Any questions? No? Great.”',
      tryText: '“Sam, what would make this work for your team?”' },
  ],
  cta: { title: 'Practise one<br>of these a day.', shot: 'daily' },
});

carousel('gd-guide', {
  dark: true,
  cover: 'How to stand<br>out in a GD',
  tips: [
    { title: 'Enter early with<br>one clear point.', said: '“I think there are many aspects to this topic…”',
      tryText: '“Hybrid wins: two office days for teamwork, three at home for focus.”' },
    { title: 'Build on someone<br>by name.', said: '“I also feel the same thing.”',
      tryText: '“Building on Ananya\'s point about commute costs…”' },
    { title: 'Add something<br>new.', said: '“Yes, yes, I completely agree with everyone.”',
      tryText: '“One thing we haven\'t covered: what happens to new joiners?”' },
    { title: 'Bring in the<br>quiet person.', said: '(Two people argue. Everyone else waits.)',
      tryText: '“Karthik, you\'ve worked remotely. What did you see?”' },
    { title: 'Offer the<br>summary.', said: '“So… yeah, that\'s all from my side.”',
      tryText: '“So we agree on flexibility, and differ on how many office days.”' },
  ],
  cta: { title: 'Rehearse a GD<br>tonight.', shot: 'groupIndia' },
});

// How it works: three steps, each one phone and a few words.
const steps = [
  { title: 'Pick what you want<br>to get better at.', shot: 'goal' },
  { title: 'Practise for<br>one minute.', shot: 'daily' },
  { title: 'Get one thing<br>to try next.', shot: 'dailyFeedback' },
];
const howCount = steps.length + 2;
add('carousels/how-it-works/01.png', POST, page({ bg: 'aurora', body: `
  ${glow({ x: 200, y: 500, size: 900, opacity: 0.45 })}
  <div class="block" style="top:150px"><div class="hero xl">How<br>Comlogue<br>works</div></div>
  ${dots({ index: 0, count: howCount, y: 1240 })}
  ${swipe(true)}
`}));
steps.forEach((step, i) => add(`carousels/how-it-works/${String(i + 2).padStart(2, '0')}.png`, POST, page({ bg: 'paper', body: `
  <div class="block" style="top:110px">
    <div class="num grad-text">${i + 1}</div>
    <div class="h2" style="margin-top:30px">${step.title}</div>
  </div>
  ${glow({ x: 190, y: 640, size: 700, opacity: 0.3 })}
  ${phone({ shot: step.shot, w: 560, x: 260, y: 640 })}
  ${dots({ index: i + 1, count: howCount, y: 1240 })}
`})));
add(`carousels/how-it-works/${String(howCount).padStart(2, '0')}.png`, POST, page({ bg: 'aurora', body: `
  ${glow({ x: 90, y: 260, size: 900, opacity: 0.45 })}
  <div class="center">
    ${logo({ light: true, size: 110 })}
    <div class="hero m" style="margin-top:56px">Say what you mean.<br>Be understood.</div>
    <div class="soon">${COMING_SOON}</div>
  </div>
  ${dots({ index: howCount - 1, count: howCount, y: 1240 })}
`}));

// ================================================================ stories (1080 × 1920; copy stays between y≈250 and y≈1600)

// Leaves room for a poll sticker ("Easy 😎 / Hard 😅") between y≈1150 and y≈1450; add it in the Instagram app.
add('stories/01-todays-prompt.png', STORY, page({ bg: 'aurora', body: `
  ${glow({ x: 90, y: 500, size: 900, opacity: 0.45 })}
  <div class="block" style="top:300px">
    <div class="sub" style="margin-top:0">Today's 1-minute practice</div>
    <div class="hero" style="margin-top:34px">Explain your job to a 10-year-old.</div>
    <div class="sub" style="margin-top:64px">Out loud. Go.</div>
  </div>
  ${brand({ y: 1540 })}
`}));

add('stories/02-gd-tonight.png', STORY, page({ bg: 'night', body: `
  <div class="block" style="top:280px"><div class="hero">Rehearse your<br>GD tonight.</div></div>
  ${glow({ x: 190, y: 780, size: 700, opacity: 0.55 })}
  ${phone({ shot: 'groupIndia', w: 620, x: 230, y: 640 })}
`}));

add('stories/03-coming-soon.png', STORY, page({ bg: 'aurora', body: `
  ${glow({ x: 90, y: 600, size: 900, opacity: 0.45 })}
  <div class="center">
    ${logo({ light: true, size: 130 })}
    <div class="hero" style="margin-top:64px">Say what<br>you mean.<br>Be understood.</div>
    <div class="soon">${COMING_SOON}</div>
  </div>
`}));

// ================================================================ reel (frames for reel.sh, 1080 × 1920) and its cover

const reelFrames = [
  page({ bg: 'aurora', body: `
    ${glow({ x: 90, y: 600, size: 900, opacity: 0.45 })}
    <div class="center"><div class="hero xl">Speak<br>better in<br>one minute<br>a day.</div></div>` }),
  ...[['1', 'Get a prompt.', 'daily'], ['2', 'Say it out loud.', 'activity'], ['3', 'Get one thing<br>to try.', 'dailyFeedback']]
    .map(([n, title, shot]) => page({ bg: 'paper', body: `
      <div class="block" style="top:280px">
        <div class="num grad-text">${n}</div>
        <div class="hero" style="margin-top:24px">${title}</div>
      </div>
      ${glow({ x: 190, y: 900, size: 700, opacity: 0.3 })}
      ${phone({ shot, w: 620, x: 230, y: 760 })}` })),
  page({ bg: 'aurora', body: `
    ${glow({ x: 90, y: 600, size: 900, opacity: 0.45 })}
    <div class="center">
      ${logo({ light: true, size: 130 })}
      <div class="hero" style="margin-top:64px">Comlogue</div>
      <div class="soon">${COMING_SOON}</div>
    </div>` }),
];
reelFrames.forEach((html, i) => add(`reels/frames/${i + 1}.png`, STORY, html));
add('reels/cover.png', STORY, reelFrames[0]);

// ================================================================ profile picture and highlight covers

add('profile/avatar.png', SQUARE, page({ bg: 'aurora', body: `
  <div class="center">${logo({ light: true, size: 300 })}</div>
`}));

const highlights = [['daily-practice', 'wave'], ['gd-prep', 'people'], ['interviews', 'briefcase'], ['how-it-works', 'sparkles'], ['faq', 'question']];
for (const [name, glyph] of highlights) {
  add(`profile/highlight-${name}.png`, STORY, page({ bg: 'aurora', body: `
    <div class="center"><div class="highlight">${icon(glyph, { color: '#fff', width: 1.8 })}</div></div>
  `}));
}

export { assets };
