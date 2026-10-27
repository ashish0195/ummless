# Product decisions

The product owner asked us to "take all the decisions". This file records each decision, why we made it, and
how to change it. The source requirements are in [`spec/notion-product-spec.md`](spec/notion-product-spec.md);
earlier visual concepts are reviewed in [`spec/design-reference.md`](spec/design-reference.md).

## 1. Name and positioning

- **Product name: Comlogue** (communication + dialogue), matching the Notion spec ("Open Comlogue").
  "Ummless" was a placeholder and framed the product around filler words, which is only one small signal
  here. The repository keeps the `ummless` name. To rename the app, change `CFBundleDisplayName` and
  `Brand.name` in the iOS project.
- **Promise:** "Notice how you communicate, try one small change, see what improved."

## 2. Scoring model (non-negotiables from the spec)

- **No overall numeric score.** It is deferred until the scoring method and coverage rules are validated.
  The API has no `overall_score` field.
- Seven dimensions: Clarity, Structure, Listening, Warmth, Persuasion, Concision, Storytelling.
- Each dimension has its own **status**: `assessed`, `provisional` (early read from limited evidence),
  `not_enough_evidence`, or `not_assessed` (never attempted). Only the first two carry a level.
- **Level** is a 5-band rubric (1 Emerging · 2 Developing · 3 Capable · 4 Strong · 5 Exceptional), shown with
  words, not points. **Evidence confidence** (low/moderate/high) is shown separately from level.
- Missing evidence is never a low level. Unassessed axes on the communication web are drawn as unavailable
  (dashed spoke and a "?"), never as zero, and the polygon is never closed across a gap.
- Every assessed dimension links to the **moments** (quotes plus playable audio) that support it.
- Results say "initial assessment" or "communication profile", never "diagnosis", and are scoped to the
  sampled context ("In this AI roleplay…").

## 3. The three-check pipeline (applies to every route and every later recording)

1. **Audio usability.** Server-side metrics on the decoded audio: speech duration, active speech level,
   noise floor and estimated SNR, clipping, overlap between speakers, and transcription confidence
   (token logprobs where the model supports them). Audio is checked in 10-second windows so usable sections
   survive when part of a recording is bad.
2. **Speaker attribution.**
   - *AI roleplay:* the user's isolated microphone turn is the user. We still run diarization on each turn to
     detect background voices, and drop the non-dominant speaker's segments.
   - *Upload / live recording:* diarization (`gpt-4o-transcribe-diarize`). With a consented voice reference,
     the reference clip is passed as a known speaker, and a local acoustic check (MFCC + pitch similarity)
     flags conflicts. Confirmation is **always** required on the first conversation, and again whenever the
     match is missing, weak or conflicting. "Yes, that's me" / "Choose another speaker" / "I'm not in this
     recording" are always offered, and correction triggers reassessment. Speaker labels are never assumed to
     carry across files.
3. **Evidence per dimension.** Deterministic opportunity checks (e.g. listening needs at least two
   exchanges where someone else said something substantive and the user replied) plus an LLM judgement
   against a written rubric that must cite moments. Server-side guards overrule the model: no opportunity
   or too little attributed speech means `not_enough_evidence`, whatever the model said.

Thresholds live in `backend/app/domain/evidence.py` and `backend/app/audio/quality.py`, marked
**"pilot calibration required"**. Total duration alone is never a pass criterion.

## 4. Onboarding order and questions

Welcome → **rank contexts** (friends & social, networking, meetings, interviews) → **what should feel easier**
(multi-select: explaining myself, contributing, connecting, persuading, being concise) → **goal area**
(negotiation, business, conversational, storytelling, public communication; one is suggested from the
earlier answers) → **language** (picker) → **choose an input**.

The input screen shows honest time estimates: guided AI conversation **10–15 min**; upload "a few minutes
plus processing"; live recording "as long as your conversation". Voice setup (~1 min) and any recovery are
estimated **separately**, as the spec asks. There is also a "Skip for now — start a goal-based course"
link, because users may start the course while filling gaps.

**Which questions?** We use the spec's five activities as the guided assessment rather than "tell me about
yourself". They are short, varied, low-stakes, and each one creates a *specific opportunity* for certain
dimensions (listening needs someone to listen to; persuasion needs a case to make). Follow-ups are dynamic:
the AI responds to what the user actually said, following each activity's policy.

**AI avatar?** A voice character with an animated "voice orb", not a photoreal face. Faces trigger
uncanny-valley effects and add little evidence for verbal skills. The character (Maya) has a small,
consistent backstory so users have something to respond to in "Meet someone new".

## 5. The timer

The suggested duration appears as a ring that drains. When it runs out, it turns into a gentle overtime
counter ("+0:23 · time's a suggestion — finish your thought"). **Recording never stops or extends on its
own.** Recording status, pause and stop are always visible. When the user stops, they see "Done" / "Redo".

## 6. Recording rules by location: active or passive?

**Decision: active, but only at the moment it matters ("just in time"), and never on the landing screen.**

- Showing legal text to everyone up front would deter the majority who choose AI roleplay, which needs no
  third-party consent.
- When a user picks **Record** or **Upload**, they see one compact card: their region's rule (detected from
  device region settings, so no location-permission prompt; changeable in one tap), a plain-English summary,
  a "How to ask" script, and one required checkbox.
- **Product policy everywhere: everyone in the conversation must agree to be recorded.** This is the strictest
  common standard, so the app never needs to decide whether a one-party state applies. The regional note is
  context, not a loophole. The UI says it is general information, not legal advice (the spec notes that a
  consent step does not by itself establish legal compliance).
- Rules data lives on the server (`/v1/meta/recording-rules`) so legal can update it without an app release.

## 7. Voice reference (biometric-adjacent data)

- **Optional, opt-in, purpose-limited:** "to find your speaking turns in recordings". The consent text is
  versioned and stored with a timestamp. Declining keeps manual identification and AI roleplay available.
- The enrollment prompt is neutral ("describe your morning") and is **never** scored.
- Stored: an 8-second clip for the diarization model plus acoustic features for conflict checks. It can be
  replaced or deleted at any time. Deleting it stops automatic matching; recordings and results have their
  own delete controls.
- **Legal review needed before launch:** voiceprints can be biometric identifiers under Illinois BIPA, Texas
  CUBI and Washington law, which require written release, a public retention schedule, and no sale. The
  default retention is "until you delete it, or after 18 months of inactivity". The reference is sent to
  OpenAI only as a known-speaker sample during diarization calls, and the consent text discloses this.

## 8. Style ("charisma") and conversational twin

- **Style** is descriptive and provisional. It needs at least 2 minutes of attributed speech from at least
  2 different activities or recordings. The output is an archetype (e.g. "The Explainer") plus observable
  traits. It is never derived from enrollment, poor audio, or anyone else's speech. Otherwise: "We need more
  conversation to describe your style."
- **Conversational twin (beta), per aspect rather than per person.** The question was "how do we do this?".
  1. Compute a style vector from attributed user speech: pace (wpm), pause length and rate, sentence length,
     question rate, hedge rate, concrete-detail rate, narrative density, and turn length.
  2. Compute the same vector for **reference speakers** offline from properly licensed or public-domain
     audio and transcripts (`backend/scripts/build_twin_profile.py`).
  3. Match **per aspect**, e.g. "your pausing resembles X", using normalized distance. We do not give a
     single "you are X" verdict, which sounding alike would not support anyway.
  - **We ship illustrative archetype references, not living celebrities.** Naming a real person in a
    commercial product implies endorsement and raises right-of-publicity issues, and their speech needs
    licensing. Adding public-domain historical speakers (e.g. US presidential speeches, which are US
    government works) is supported by the script. Legal should sign off on the list.
  - Shown only when the relevant aspects have enough evidence; otherwise "Your conversational twin is not
    ready yet" plus a next task. It never blocks the profile or course.

## 9. Course, missions and the weekly loop

- Five goal tracks × four modules (one per week). Each module has one target behavior and four missions:
  **Learn & try**, **Remix**, **Real-life mission** (with an AI alternative), and **Weekly reveal**.
- Mission attempts are AI conversations (the partner raises a realistic objection). Feedback says *where*
  the target behavior appeared, gives one change, and compares retries against the same target ("shorter
  isn't automatically better").
- The course is ordered by the profile when evidence exists ("Tailored to your profile"), otherwise by goal
  ("Based on your goal"). Gaps get optional targeted tasks. Users can switch module or goal at any time.
- **Practice completion is separate from skill.** The communication web only updates from assessable
  recordings or assessments. Reflections inform goals but are not skill evidence.
- Weekly target (user-chosen, default 3 sessions), optional reminders, and an easy return after a missed
  week. No streak resets, leaderboards or XP. The daily rep (section 15) is the smallest unit of practice; the
  course stays the main path.

## 10. Extra practice (beyond the spec, from the earlier concepts)

- **Spar:** realistic AI personas (Skeptical CFO, Interviewer, Upset teammate, First date, Landlord,
  Negotiation counterpart) or "describe any scenario"; difficulty Kind/Real/Brutal; a coach whisper between
  turns; a report with momentum and "rewrite this moment".
- **Talks / shadowing:** public-domain speeches plus original exemplar scripts, an AI style breakdown, and
  line-by-line "repeat after" with an on-device rhythm match (pause placement and pace).
- **Event prep:** add an upcoming interview, meeting or date, and the AI builds three rehearsal scenarios.
- **Meeting debrief** for recorded or uploaded multi-speaker conversations: talk share, best moment,
  decisions, a follow-up summary, and one thing to try.

**Deferred (documented, not built):** the social layer (communities, pods, live rooms, DMs, events),
leaderboards, Clone Mode (cloning a real person's voice raises consent issues), and real-time earpiece
whispers in live meetings (needs reliable live diarization).

## 11. Access and pricing

- **Free:** baseline (all routes), gap-fill tasks, recovery and retries (never paywalled), one practice
  mission, the full course preview, one spar per week, one talk, **the daily rep (always, with unlimited
  retries)**, one group discussion and one panel interview.
- **Pro:** full course, unlimited spar, all talks, every group discussion and panel, event prep, and weekly
  reveal insights.
- Pricing hypotheses (configurable, shown before purchase), with a 7-day trial everywhere:
  - **US and other markets:** **$14.99/month** or **$95.99/year** (46% less than 12 monthly payments).
  - **India:** **₹399/month** or **₹2,499/year** (47% less). That is about a quarter of the US price, in line
    with what Indian users pay for other self-improvement subscriptions and with local purchasing power.
  - The App Store products stay `comlogue.pro.monthly` and `comlogue.pro.yearly`; the India price is set as
    a territory price in App Store Connect. In the app, StoreKit's localized price always wins; the server's
    `pricing` for the user's market is only a fallback label.

## 12. Languages and culture

- UI: English, with all strings localizable. Conversation and feedback languages are English, Spanish,
  French, German, Portuguese, Italian, Dutch, Hindi, **Hinglish** (Hindi–English code-mixing in Latin
  script, as many Indians speak at work), Japanese, Korean, Chinese, and Arabic. The model evaluates in the
  chosen language. Onboarding offers one-tap picks for the market: English, Hinglish and हिन्दी in India;
  English and Español in the US.
- Filler and hedge statistics are only computed where we have validated word lists (English for now);
  elsewhere they show as unavailable rather than wrong.
- **Accent and pronunciation are never scored.** Low transcription confidence leads to abstaining, not a
  lower level.
- "Country-specific communication styles": the rubric prompt tells the model that norms of directness,
  warmth and turn-taking vary by culture, and that it should not penalize a style that fits the user's
  context. A region-aware style guide is a pilot item.

## 13. AI models (all configurable in `backend/.env`)

| Job | Default | Fallbacks |
| --- | --- | --- |
| Evidence assessment, feedback, reports | `gpt-6.1-sol` (reasoning: medium) | `gpt-6-sol`, `gpt-5.5` |
| Live conversation turns, coach whispers | `gpt-6-luna` (reasoning: low) | `gpt-5.4-mini`, `gpt-5-mini` |
| Turn transcription (with confidence) | `gpt-4o-transcribe` | `gpt-4o-mini-transcribe` |
| Diarization + known-speaker matching | `gpt-4o-transcribe-diarize` | — |
| Partner voices | `gpt-4o-mini-tts` (voices `marin`, `cedar`, `coral`…) | on-device speech synthesis in the app |

If a model is not enabled on the account, the backend falls through to the next one and remembers which
worked. `AI_PROVIDER=mock` runs the whole product offline with clearly labeled demo output; the app shows a
"Demo mode" badge.

## 14. Pilot metrics to instrument

First-task completion, voluntary retries, return for the next mission, real-life application, improvement
on a fresh scenario, and the coverage funnel (what share of sessions reach each check). Engagement and
learning are reported separately.

## 15. The habit loop: one 60-second rep a day

The user asked for an app people come back to every day. We used what behaviour-change research says makes a
habit stick, and avoided the patterns that make people feel guilty and leave.

- **A tiny daily action.** The *daily rep* is one spoken answer to a short prompt (30–90 seconds), with one
  target behaviour, feedback on that target and an unlimited "try again with that change". It's free for
  everyone and counts as a practice session. Prompts are picked per user and day: weighted towards the course
  focus, the goal and the market, lighter at weekends, seasonal in season (Diwali, Thanksgiving, appraisal
  season), and never repeated within 30 days. One shuffle per day, before the first attempt.
- **A plan, not a streak.** Onboarding ends with a practice plan: sessions per week (2–7, default 3), days,
  a time, and an optional *anchor* ("After my morning chai", "After my morning coffee"). Tying practice to an
  existing routine is an implementation intention, one of the best-supported habit techniques. Reminders follow
  the plan.
- **Weeks on target instead of daily streaks.** Progress is "3 of 3 this week" plus a Monday-to-Sunday dot strip.
  The run counts consecutive weeks that met the target. A missed day never resets anything, and Monday is a
  fresh start.
- **Planned breaks.** Exams, travel, a wedding in the family: a break of 1 or 2 weeks (or until a date) pauses
  reminders and nudges, and a week overlapping a break neither counts nor breaks the run.
- **Welcome back, no guilt.** After 7 or more quiet days, Today opens with "Welcome back — your progress is
  saved. Start with a 60-second rep." instead of what was missed.
- **Close the loop on real conversations.** The day after an interview, pitch or hard talk the user added, a
  check-in asks "How did it go?" (Today shows the same prompt). A tap and a sentence get a coach reply tied to the
  current course focus, and the reflection counts as real-life practice. Transfer to real life is what the course
  is for, and the spec's pilot metric for it now includes these reflections.
- **Celebrate real progress.** Milestones such as the first rep, 10 and 30 reps, and 2, 4, 8 and 12 weeks on
  target get a one-time celebration with a share option. There's still no XP, no leaderboard and no league.
- **The rep is everywhere the user already is:** the Today screen's first card, home and lock screen widgets
  (today's prompt and the week), Siri and Shortcuts ("Start today's rep"), and tomorrow's actual prompt in
  tomorrow's reminder.

## 16. Notifications that bring people back (and stop when they don't)

- **What we send** (each one can be turned off, and all go to the in-app inbox too):
  - practice reminders at the planned time and days;
  - event prep the evening before and the morning of anything added in Practice;
  - results when a recording, an assessment or feedback is ready;
  - a "how did it go?" check-in after an event or a real-life mission;
  - the weekly reveal on Sunday evening;
  - milestones;
  - tips and product news, which are off by default.
- **When we stay quiet:**
  - quiet hours (22:00–08:00 by default, in the user's timezone);
  - at most 2 pushes a day;
  - nothing but results and event prep during a planned break.
- **Nudges are rare and they give up:**
  - after 3 quiet days and again after 8, at most one in 72 hours;
  - none after two unopened ones until the user comes back;
  - none at all without a weekly target.
  - This keeps the app from becoming notification spam, which is the fastest way to lose the permission for
    good.
- **Asking for permission:** never at first launch. We ask at a moment of intent, right after the user sets
  a plan or adds an event, on a priming screen that shows what they'll get. "Not now" is a first-class choice,
  and the app can deliver quietly (provisional authorization) instead.
- **Delivery has two paths.**
  - Practice reminders are scheduled on the device, so they work offline and without a push server.
  - Server pushes (APNs token auth) carry results, event prep, check-ins and nudges.
  - When the server can't push to a device, the app schedules the event and check-in reminders locally, so the
    user still gets them.
  - The app keeps at most 48 pending local notifications (iOS allows 64).
- **Every notification opens the right screen** through a `comlogue://` deep link, and actions such as
  "Start now" or "Remind me later" (about two hours on, never in quiet hours) work from the lock screen. The
  app badge is the unread inbox count.
- **Calendar (optional):** with permission, the app reads upcoming event titles on the device and suggests
  rehearsals ("Final HR round at Zenith on Thursday — rehearse it?"). A title leaves the device only if the
  user adds the event.

## 17. Built for India and the US

The market comes from the region (`IN` → India, `US` → US, anything else → the US-style global default) and
changes content, formats and price, not the product's rules.

- **India:**
  - campus placements, HR and technical rounds, viva voce, appraisal conversations, client calls with US
    teams, and **group discussions (GDs)**: an AI moderator and 2–3 AI participants, one dominant, one
    thoughtful and one quiet;
  - salaries in LPA, rent in Bengaluru or Pune, "₹ lakh and crore" figures;
  - dates such as "27 Oct", a Hinglish-speaking team lead persona, and an Indian English voice for spoken
    fallbacks;
  - consent text in Hindi (drafts pending legal review).
- **US:** behavioural (STAR) interviews, panel interviews, performance reviews, networking mixers, roommate
  and neighbour conflicts, and Thanksgiving-season prompts.
- **Interviews track.** We added a sixth goal track, *Job interviews*: introduce yourself, STAR stories, "Why
  should we hire you?", and asking good questions and closing strongly. It is a deviation from the spec's five
  goal areas. Interviews and placements are the most common reason people in India practise speaking, and
  one of the top reasons in the US. The India version swaps in placement scenarios.
- **Accent and dialect fairness.** Indian English and code-switching are never scored or "corrected". A
  rewrite may offer a "global English" version, labelled as an option, only when the context calls for it
  (e.g. a call with US clients).
- **India's DPDP Act:**
  - Comlogue is for adults. Onboarding asks the user to confirm they're 18 or older before analysis consent,
    because the Act treats under-18s as children who need verifiable parental consent.
  - The app shows a grievance contact and offers a full data export (JSON, without audio), alongside the
    existing deletion controls.
  - The DPDP Rules were notified on 13 Nov 2025, and most notice and consent duties apply from about
    13 May 2027. See [LAUNCH.md](LAUNCH.md).
