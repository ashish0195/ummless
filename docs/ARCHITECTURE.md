# Architecture

```mermaid
flowchart LR
    subgraph iOS["iOS app (SwiftUI, iOS 17+)"]
        UI["Feature screens"] --> Models["@Observable models"]
        Models --> Core["Core: API client, models, audio math,\nnotification planner, deep links"]
        Models --> Platform["Platform: recorder, player, speech, StoreKit,\nnotifications, calendar"]
        Platform -- "App Group snapshot" --> Widgets["Widgets extension"]
    end
    Core -- "HTTPS JSON + multipart audio" --> API
    subgraph Backend["Backend (FastAPI)"]
        API["Routers /v1/*"] --> Services["Services: conversations, assessments,\nrecordings, course, spar, daily reps,\ngroup, notifications…"]
        Services --> Jobs["Async job runner"]
        Scheduler["Notification scheduler"] --> Services
        Services --> Audio["Audio: ffmpeg, quality, voiceprint, stats"]
        Services --> AI["AI provider (OpenAI or mock)"]
        Services --> Push["Push sender (APNs or inbox only)"]
        Services --> DB[("SQL database")]
        Services --> Media[("Media storage")]
    end
    AI -- "transcribe · diarize · reason · speak" --> OpenAI["OpenAI API"]
    Push -- "HTTP/2, token auth" --> APNs["Apple Push Notification service"]
    APNs --> iOS
```

## iOS app (`ios/`)

| Layer | Folder | Notes |
| --- | --- | --- |
| App shell | `Comlogue/App` | `AppModel` holds the session, cached server data and the active full-screen flow. `FlowHost` routes flows. |
| Core | `Comlogue/Core` | Foundation-only. Codable models that mirror `docs/API.md`, `APIClient` (async/await, multipart, re-auth), `AudioMath` (VAD, pauses, quality issues, rhythm match). Also built as a SwiftPM package (`ios/Package.swift`) and tested on Linux. |
| Platform | `Comlogue/Platform` | AVFoundation recorder and player, on-device speech fallback (with Indian English voices for India), Keychain identity, StoreKit 2, `NotificationManager` (permission, APNs registration, categories and actions, local scheduling, badge), `WidgetBridge`, `CalendarScanner` (EventKit), haptics. |
| Design system | `Comlogue/DesignSystem` | Theme tokens (light/dark), pill buttons, cards, `VoiceOrb`, `CommunicationWeb`, `SuggestionTimerRing`, recording status bar. |
| Features | `Comlogue/Features/*` | Onboarding (a one-time, four-step walkthrough with the reminder routine and 18+ consent), conversation engine, assessment, recordings, results, today, daily practice, inbox, course and missions, practice (spar, group discussions and panels, talks, events), you, settings (practice plan, notifications), paywall. |
| Widgets | `ComlogueWidgets`, `Shared` | WidgetKit extension: today's practice (home and lock screen) and the week. It reads a `WidgetSnapshot` the app writes to the App Group `group.com.comlogue.app`, so it never needs the network or the token. `Shared` is compiled into both targets and tested as a SwiftPM target. |

Key behaviours:

- **One conversation engine.** `ConversationScreen` and `ConversationModel` serve the guided assessment, missions and spar. Each turn is recorded on the user's isolated microphone, sanity-checked on device, then uploaded. The server transcribes it, checks it and replies with the partner's next line as TTS audio. The app falls back to on-device speech when there is no audio.
- **The timer never stops the recording.** `AudioRecorder` has no auto-stop. The ring turns into an overtime counter.
- **Honest recovery.** Unusable turns or recordings produce specific issues and recovery actions, never a score.
- **Configurable server.** The `API_BASE_URL` build setting (Debug defaults to `http://localhost:8000`) can be overridden at runtime in Settings → Developer → Server.
- **Reminders are planned on the device.** `NotificationPlanner` (pure, tested on Linux) turns the practice plan, the next week's daily-practice prompts, events and settings into at most 48 local notifications:
  - quiet hours, at most two a day, nudges that only fire if the app stays closed;
  - re-planned on every refresh.
  - When the server reports `push_enabled`, it delivers event prep, check-ins, nudges and the weekly reveal by push, and the device keeps only practice reminders.
- **Deep links everywhere.** Notifications, the inbox, widgets and App Intents all use `comlogue://` links (`DeepLink`). A tap that cold-launches the app is queued in `PendingLink` until the session is ready.

## Backend (`backend/`)

- **FastAPI** with SQLAlchemy (SQLite by default, Postgres via `DATABASE_URL`) and local media storage behind an interface ready for S3.
- **Auth**: anonymous device tokens (HMAC-signed). Sign in with Apple can be layered on later.
- **AI provider interface** with two implementations:
  - `openai`: `gpt-4o-transcribe` (with logprobs for confidence) for turns, `gpt-4o-transcribe-diarize` with the consented voice reference as a known speaker for recordings, a reasoning model for evidence assessment and feedback via Structured Outputs, a fast model for live partner replies, and `gpt-4o-mini-tts` for partner voices. Each role has a model fallback chain.
  - `mock`: deterministic and offline, used by tests and demo mode. Responses carry `demo_mode: true` and the app shows a badge.
- **Pipelines** run as async background jobs. Clients poll the resource; restarts re-queue stuck work.
  - Recording: decode → quality (10-second windows) → diarize → attribution rules → [wait for confirmation] → evidence assessment → debrief.
  - Assessment: turns are already checked → finalize → evidence assessment across activities → style eligibility → profile update.
- **Evidence guards**: deterministic minimums per dimension override the model. No opportunity, or too little attributed speech, gives `not_enough_evidence` with a null level.
- **Markets** (`domain/markets.py`, `domain/market_content.py`, `domain/content/`): the region decides `us`, `in` or `global`, which selects daily prompts, personas, group panels, course variants (names, places, ₹ or $), event kinds, date formats, pricing and the default timezone. Weeks run Monday to Sunday in the user's timezone.
- **Daily reps** (`services/daily.py`): one prompt per user and day, chosen deterministically and stored, so tomorrow's reminder can name tomorrow's prompt. Attempts are one-turn conversations judged like missions.
- **Group conversations** (`services/group.py`): a moderator and 2–3 participants, each with a stance and a voice. After each user turn a structured-output call returns one or two in-character lines. There's a scripted fallback, and the moderator closes.
- **Notifications** (`services/notifications.py`, `push.py`):
  - Every notification is an inbox row first, idempotent by a per-user dedupe key.
  - Pushes follow the user's categories, quiet hours (in their timezone), a daily cap of two and planned breaks.
  - Results notifications are produced by the jobs that finish the work.
  - Event prep, check-ins, nudges and the weekly reveal come from a scheduler thread that runs every few minutes.
  - Delivery goes through APNs with ES256 provider tokens when `APNS_*` is set, and is inbox-only otherwise. Invalid tokens are dropped and transient errors are retried.
- **Schema changes**: `migrations.py` adds missing nullable columns to existing tables at startup. Alembic is still planned before the first production schema change.

## Data and privacy

- Audio, transcripts and results belong to the user and are deletable individually or all at once (`DELETE /v1/me`, which also removes devices and notifications). `GET /v1/me/export` downloads everything stored about the user as JSON, without audio.
- Calendar access is optional. Event titles are classified on the device and leave it only when the user adds one as an event.
- The voice reference is opt-in, versioned and consented, stored separately, and deletable without touching recordings.
- Other speakers' speech is used only as context and never enters the user's profile.
- Secrets live in environment variables only. The app never holds the OpenAI key.

## Contract testing

`backend/scripts/export_contract_fixtures.py` captures real responses from the backend in mock mode into `contract-fixtures/`. `ios/CoreTests/ContractTests.swift` decodes every fixture with the app's own models and checks the spec's invariants (no overall score, no level without evidence, no fractional-second timestamps).
