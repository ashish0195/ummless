# Launch checklist

What's needed to take Comlogue from this repository to the App Store, and what still needs a human decision.

## 1. Backend in production

- [ ] Deploy `backend/` (Docker image; see `backend/README.md`) behind HTTPS, e.g. Render, Fly.io or Railway.
- [ ] Use Postgres (`DATABASE_URL`) and S3-compatible storage for media. SQLite and local disk are for development only.
- [ ] Set `ENVIRONMENT=production`, `OPENAI_API_KEY`, a long random `SECRET_KEY` (`openssl rand -hex 32`), and `ALLOW_DEV_ENTITLEMENTS=false`. In production the server refuses to start with a short or placeholder key.
- [ ] Confirm which OpenAI models your account can use and set `ASSESSMENT_MODELS`, `CONVERSATION_MODELS`, `TRANSCRIPTION_MODELS`, `DIARIZATION_MODELS` and `TTS_MODELS`. The backend falls back automatically, but the first choice should be the model you want.
- [ ] Turn on App Store transaction verification (`APP_STORE_REQUIRE_VERIFICATION=true` once Apple root-certificate checks are wired in). See the billing section in `backend/README.md`.
- [ ] Point the Release build at it: the `API_BASE_URL` build setting (currently the placeholder `https://api.comlogue.app`).
- [ ] Push notifications (APNs): in the Apple Developer portal create a key with *Apple Push Notifications service* and keep the `.p8` file safe (it can be downloaded only once). Set `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_PRIVATE_KEY_PATH` (or `APNS_PRIVATE_KEY`) and `APNS_BUNDLE_ID` as secrets — never in the repository. Without them the server is inbox-only and the app falls back to local reminders. Check with `POST /v1/notifications/test`. Steps in `backend/README.md` → "Setting up APNs".
- [ ] The notification scheduler runs inside the API (`NOTIFICATIONS_TICK_SECONDS`, default 5 minutes). Keep at least one instance running at all times; scaling to more is safe.
- [ ] Set `SUPPORT_EMAIL`, `GRIEVANCE_EMAIL` and, once appointed, `GRIEVANCE_OFFICER` (shown in the app via `Meta.support`).

## 2. App Store Connect

- [ ] Create the app with bundle ID `com.comlogue.app` (or change `PRODUCT_BUNDLE_IDENTIFIER`).
- [ ] Enable the **Push Notifications** capability for the App ID (`ios/Config/Comlogue.entitlements` sets `aps-environment`; distribution builds are signed for production) and the App Group `group.com.comlogue.app` used by the widgets.
- [ ] Create a subscription group "Comlogue Pro" with `comlogue.pro.monthly` ($14.99) and `comlogue.pro.yearly` ($95.99, 7-day free trial). The prices are hypotheses from the spec; change them in App Store Connect and in `backend/.env`.
- [ ] **India pricing:** in App Store Connect set a custom price for India rather than the automatic equivalent: ₹399/month and ₹2,499/year (`PRICE_MONTHLY_INR`, `PRICE_YEARLY_INR` on the server for display). App Store prices in India include GST. The app always shows StoreKit's localized `displayPrice` at purchase.
- [ ] Make the app available in India and the US (and decide on other countries). Add the India keywords and a Hindi or Hinglish promotional text only if the in-app copy supports it.
- [ ] Host the privacy policy and terms at the URLs in `Brand` (`Comlogue/Core/Domain/DomainCatalog.swift`), or change them there.
- [ ] Set a Development Team in Xcode, then archive and upload.

### Suggested listing

**Name:** Comlogue: Communication Coach
**Subtitle:** Speak clearly. Be understood.
**Promotional text:** One 1-minute speaking practice a day, AI partners who push back, and feedback only where there's evidence. Rehearse interviews, GDs, pitches and hard talks.

**Description:**
> Comlogue is a communication coach that listens to how you actually talk, and helps you get a little better every day.
>
> Start with five short conversations with an AI partner, or upload or record a real conversation, with everyone's permission. Comlogue checks the audio, makes sure it's assessing your voice, and gives feedback on clarity, structure, listening, warmth, persuasion, concision and storytelling. It only does this where there's real evidence. Skills it can't assess yet are marked "Not enough evidence yet", never scored low.
>
> Then make it a habit. Each day brings one 1-minute speaking practice with a single thing to try, feedback on that one thing, and as many retries as you like. Pick the days and time that suit you. There are no streaks to lose: a missed day never erases progress, and you can plan a break for exams or travel.
>
> • Missions for your goal: job interviews, business communication, negotiation, conversation, storytelling or public speaking
> • Group discussions and panel interviews with several AI voices, then a report
> • Spar with realistic AI personas, from kind to brutal
> • Rehearse an upcoming interview, placement, client call or difficult talk, then reflect on how it went
> • Shadow great speeches line by line and match their rhythm
> • Reminders that respect your quiet hours, plus home and lock screen widgets
> • English, Hinglish, Hindi and ten more languages; your accent is never scored
> • Delete any recording, or everything, at any time

**Keywords** (100 bytes at most; the name already covers "communication" and "coach"):
- US: `public speaking,confidence,interview,presentation,speech,storytelling,negotiation,conversation,pitch`
- India: `spoken english,interview,group discussion,GD,placement,HR round,public speaking,confidence,speech`

**Category:** Education (secondary: Productivity)

### App privacy ("nutrition label")

| Data type | Linked to user | Tracking | Purpose |
| --- | --- | --- | --- |
| Audio data | Yes | No | App functionality |
| Other user content (transcripts, reflections) | Yes | No | App functionality |
| Device ID (anonymous install ID) | Yes | No | App functionality |
| Purchase history | Yes | No | App functionality |
| Product interaction (practice sessions, notification opens) | Yes | No | App functionality, Analytics |

Calendar access is optional and read on the device only: event titles leave it only when the person adds one as an
event, so calendar data isn't "collected" in Apple's sense.

### Review notes (paste into App Review information)

> Comlogue analyses speech to give communication feedback. To test without recording others, choose "Talk with an AI partner" on the first screen. Microphone access is used only while the person is recording. Background audio mode is used so a recording of a meeting continues when the screen locks; recording status, pause and stop are always visible. Users can delete their recordings, their voice sample, or their whole account in Settings → Privacy & data.

## 3. Needs legal review before launch

- **Voice reference (biometric-adjacent).** Illinois BIPA, Texas CUBI and Washington's biometric law may apply to voiceprints. Confirm the consent text (`backend/app/domain/consents.py`), the written retention schedule (currently "until you delete it, or 18 months of inactivity") and the published policy.
- **Recording others.** The product requires everyone's agreement everywhere. Have counsel review the regional guidance text in `backend/app/domain/recording_rules.py`.
- **Third-party processing.** Audio is processed by OpenAI. Check your data processing terms and whether you need zero data retention.
- **Conversational twin references.** The shipped references are illustrative archetypes. Adding real people (even public-domain speeches) needs sign-off.
- **Children.** Positioned for adults (the spec says "students over 25"). Set the age rating accordingly. The app asks people to confirm they're 18 or older before recording analysis consent (`onboarding.age_confirmed`), in line with the DPDP Act's definition of a child.
- **India — Digital Personal Data Protection Act, 2023.** The DPDP Rules were notified on 13 November 2025; most obligations, including the notice and consent duties, apply from about 13 May 2027. Before then, with counsel:
  - finalise the consent and notice texts, and the **Hindi drafts** in `backend/app/domain/content/consent_translations.py` (marked DRAFT; served as `ConsentText.translations`);
  - publish a grievance contact and, once appointed, a grievance officer (`Meta.support`), with a response process;
  - confirm the India recording guidance in `backend/app/domain/recording_rules.py` ("Ask everyone first"; legal review pending);
  - confirm that `GET /v1/me/export` (access) and account deletion (erasure) meet the Act's rights and timelines;
  - review cross-border processing (audio is processed by OpenAI outside India) and the notice wording for it.
- **US state privacy laws.** The export and deletion endpoints cover access and deletion requests; confirm the privacy policy wording per state (e.g. California).

## 4. Pilot readiness

- [ ] Calibrate the thresholds marked "pilot calibration required": audio quality, speaker matching, and per-dimension evidence minimums.
- [ ] Review `feedback_reports` ("Not quite right?") weekly. They're the fastest signal of miscalibrated feedback.
- [ ] Track the pilot metrics from the spec: first-task completion, voluntary retries, return for the next mission, real-life application, improvement on a fresh scenario. Run `python scripts/pilot_metrics.py --since YYYY-MM-DD` from `backend/`. It reports engagement and learning separately, with each metric's definition.
- [ ] Habit loop: watch daily-rep completion, push open rate and push → session conversion (same report, engagement only). If nudges don't convert, lower their frequency before adding more; never add streak-loss messages.
- [ ] Run the pilot in both markets (US and India) and compare: prompt fit, pricing, notification timing (quiet hours default to 22:00–08:00 local) and how Indian English and Hinglish speakers feel the feedback treats them.
