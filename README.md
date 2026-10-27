# Comlogue

**An AI communication coach.** Talk with an AI partner, upload real conversations, or record one. Comlogue
checks the audio, makes sure it's assessing *your* voice, and gives feedback on seven communication skills
only where there's real evidence. Then it coaches you one small change at a time, with a 1-minute speaking practice
each day that turns practice into a habit. Built for the US and India.

<p align="center"><img src="ios/Comlogue/Resources/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png" width="120" alt="Comlogue app icon"></p>

| | |
| --- | --- |
| **iOS app** | SwiftUI · iOS 17+ · `ios/` |
| **Backend** | Python 3.13 · FastAPI · OpenAI API · `backend/` |
| **Spec** | [`docs/spec/notion-product-spec.md`](docs/spec/notion-product-spec.md) |
| **Decisions** | [`docs/PRODUCT_DECISIONS.md`](docs/PRODUCT_DECISIONS.md) |
| **API contract** | [`docs/API.md`](docs/API.md) |
| **Architecture** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **Marketing** | [`marketing/instagram/`](marketing/instagram/) · Instagram launch kit |

## Screenshots

Captured from the iOS Simulator against the demo backend by `.github/workflows/screenshots.yml`. Push a commit
whose message starts with `[screenshots]` to refresh them.

| Welcome | One question | How to start | Your profile |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/welcome.png" width="190" alt="Welcome screen"> | <img src="docs/screenshots/goal.png" width="190" alt="What do you want to get better at?"> | <img src="docs/screenshots/getStarted.png" width="190" alt="Two ways to start"> | <img src="docs/screenshots/results.png" width="190" alt="Partial communication profile with gaps for missing evidence"> |

| Today | Course | Mission | Rehearse |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/today.png" width="190" alt="Today"> | <img src="docs/screenshots/course.png" width="190" alt="Course map"> | <img src="docs/screenshots/mission.png" width="190" alt="Mission"> | <img src="docs/screenshots/spar.png" width="190" alt="Rehearsing a hard conversation with an AI partner"> |

| Practice | You | Pro | Dark mode |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/practice.png" width="190" alt="Practice hub"> | <img src="docs/screenshots/you.png" width="190" alt="Profile"> | <img src="docs/screenshots/paywall.png" width="190" alt="Paywall"> | <img src="docs/screenshots/dark-results.png" width="190" alt="Results in dark mode"> |

**The daily habit**

| Today's practice | Feedback | Reminders | Notifications |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/daily.png" width="190" alt="Today's 1-minute practice"> | <img src="docs/screenshots/dailyFeedback.png" width="190" alt="Feedback on a daily practice"> | <img src="docs/screenshots/plan.png" width="190" alt="Reminders tied to a routine"> | <img src="docs/screenshots/notifications.png" width="190" alt="Notification settings"> |

| Inbox | Panel interview | Interview report | Dark mode |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/inbox.png" width="190" alt="In-app inbox"> | <img src="docs/screenshots/group.png" width="190" alt="A panel interview with several AI voices"> | <img src="docs/screenshots/groupReport.png" width="190" alt="Report after a group conversation"> | <img src="docs/screenshots/dark-daily.png" width="190" alt="Daily practice in dark mode"> |

**Built for India**

| Today | Group discussion | Practice | Pro in ₹ |
| :---: | :---: | :---: | :---: |
| <img src="docs/screenshots/todayIndia.png" width="190" alt="Today for an Indian account"> | <img src="docs/screenshots/groupIndia.png" width="190" alt="A campus placement group discussion"> | <img src="docs/screenshots/practiceIndia.png" width="190" alt="Practice with placement scenarios"> | <img src="docs/screenshots/paywallIndia.png" width="190" alt="Paywall in rupees"> |

| Reminders | Consent in Hindi |
| :---: | :---: |
| <img src="docs/screenshots/planIndia.png" width="190" alt="Reminders tied to morning chai"> | <img src="docs/screenshots/consentIndia.png" width="190" alt="Analysis consent with a Hindi option"> |

## What's inside

- **Simple by design:** a one-time, four-step walkthrough (welcome, one goal, a reminder tied to a routine,
  consent), then one obvious action per screen, plain words, and detail one tap away.
- **A daily 1-minute practice:**
  - one short speaking prompt a day, picked for the user's goal, focus skill and market;
  - feedback on one target behaviour, with unlimited retries;
  - free for everyone.
- **A habit that sticks, with no guilt:**
  - a practice plan (sessions per week, days, time and an anchor such as "after my morning chai");
  - "weeks on target" instead of streaks;
  - planned breaks, a warm welcome back, and milestone celebrations.
- **Notifications that bring people back and know when to stop:**
  - practice reminders, event prep the evening before and the morning of, results, check-ins and the weekly
    reveal;
  - quiet hours, at most two a day, and nudges that give up after two;
  - push via APNs plus on-device reminders, an in-app inbox, a badge, and deep links;
  - home and lock screen widgets.
- **Group discussions and panel interviews:** a moderator and 2–3 AI participants with distinct voices and
  behaviours (one dominant, one thoughtful, one quiet), then a report.
- **Made for India and the US:**
  - India gets campus placements, HR rounds, GDs, viva, client calls with US teams, Hinglish, ₹ pricing and
    Hindi consent text;
  - the US gets behavioural interviews, performance reviews and networking;
  - accents and dialects are never scored.
- **Two ways to start:** a guided AI conversation (five short activities, 10–15 min) or a 1-minute practice.
  Uploading or recording a real conversation is one tap away. Every analysis passes audio-quality,
  speaker-attribution and evidence checks.
- **An evidence-gated communication profile** across Clarity, Structure, Listening, Warmth, Persuasion,
  Concision and Storytelling:
  - Each skill shows a level and, separately, how confident we are, plus the moments that support it.
  - Skills without enough evidence show "Not enough evidence yet". There is no overall score.
- **Voice matching that asks first:** an optional, consented voice sample, and confirmation of which speaker
  is you ("Yes, that's me" / "Choose another speaker" / "I'm not in this recording").
- **A course that adapts:** six goal tracks (including job interviews) of four weekly modules each. Every module has Learn & try,
  Remix, a Real-life mission and a Weekly reveal. Missions are AI conversations with feedback tied to one
  target behaviour, retries, and before/after comparisons.
- **Practice tools:**
  - Rehearse a conversation with an AI partner (friendly, realistic or tough), with a coach whisper between
    turns and a report that suggests rewrites of key moments.
  - Shadow great talks line by line with an on-device rhythm match.
  - Rehearse an upcoming event.
  - Get a debrief of a recorded meeting.
- **Privacy built in:** just-in-time recording consent with regional rules, and deletion of each recording,
  the voice sample, or everything.
- **Siri and Shortcuts:** "Start today's practice", "Start today's mission", "Quick practice" and "Record a
  conversation".
- **Honest when things go wrong:** unclear audio, an uncertain speaker or a server-side failure leads to a
  specific next step ("Try again", "Choose another speaker", a short gap-filling scenario), never a low score.

## Quick start

### 1. Run the backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add OPENAI_API_KEY to use real AI; leave it empty for demo mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You also need `ffmpeg` (`brew install ffmpeg` or `apt install ffmpeg`). Or run `docker compose up --build` in
`backend/`. See [`backend/README.md`](backend/README.md) for configuration, deployment and costs.

Without an `OPENAI_API_KEY` the backend runs in **demo mode**. Every flow works offline with clearly labelled
simulated output, and the app shows a "Demo mode" badge.

### 2. Run the iOS app

1. Open `ios/Comlogue.xcodeproj` in Xcode 16 or later.
2. Pick an iPhone simulator and press Run. Debug builds talk to `http://localhost:8000`.
3. On a physical iPhone, set your Mac's local IP (e.g. `http://192.168.1.20:8000`) in
   **Settings → Developer → Server**, or change the `API_BASE_URL` build setting.
4. To try purchases locally, the scheme uses `ios/Comlogue.storekit`. Edit the scheme if Xcode doesn't pick
   it up.

Set your team under *Signing & Capabilities* before running on a device.

## Tests

```bash
cd backend && pytest -q            # backend (mock AI, synthetic audio)
cd ios && swift test               # app core: models, API client, audio math, contract tests
```

`backend/scripts/export_contract_fixtures.py` captures real API responses into `contract-fixtures/`. The
Swift contract tests decode them with the app's own models, so the app and backend can't drift apart.

CI (`.github/workflows/ci.yml`) runs the backend tests, then the Swift core and contract tests on Linux
against fixtures that backend just exported. It also builds and smoke-tests the backend Docker image, and
does a full Xcode build of the app for the iOS Simulator on macOS.

## Repository layout

```
backend/            FastAPI app, AI pipeline, tests, Dockerfile
contract-fixtures/  Real API responses used by the Swift contract tests
docs/               Spec, decisions, API contract, architecture
ios/
  Comlogue.xcodeproj
  Comlogue/         App sources (App, Core, Platform, DesignSystem, Features, Resources)
  ComlogueWidgets/  Home and lock screen widgets (WidgetKit extension)
  Shared/           Code shared by the app and the widgets (the App Group snapshot)
  CoreTests/        SwiftPM tests for the platform-independent core
  Package.swift     Builds Comlogue/Core and Shared as packages for testing
```

## Not in this version

The social layer from the early concepts (communities, pods, live rooms, DMs), leaderboards, and real-time
earpiece coaching are deferred. So is cloning a real person's voice, which raises consent issues. The
reasons are in [`docs/PRODUCT_DECISIONS.md`](docs/PRODUCT_DECISIONS.md#10-extra-practice-beyond-the-spec-from-the-earlier-concepts).
