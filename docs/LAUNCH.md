# Launch checklist

What's needed to take Comlogue from this repository to the App Store, and what still needs a human decision.

## 1. Backend in production

- [ ] Deploy `backend/` (Docker image; see `backend/README.md`) behind HTTPS, e.g. Render, Fly.io or Railway.
- [ ] Use Postgres (`DATABASE_URL`) and S3-compatible storage for media. SQLite and local disk are for development only.
- [ ] Set `OPENAI_API_KEY`, a long random `SECRET_KEY`, and `ALLOW_DEV_ENTITLEMENTS=false`.
- [ ] Confirm which OpenAI models your account can use and set the `OPENAI_*_MODELS` lists. The backend falls back automatically, but the first choice should be the model you want.
- [ ] Turn on App Store transaction verification (Apple root certificates). See the billing section in `backend/README.md`.
- [ ] Point the Release build at it: the `API_BASE_URL` build setting (currently the placeholder `https://api.comlogue.app`).

## 2. App Store Connect

- [ ] Create the app with bundle ID `com.comlogue.app` (or change `PRODUCT_BUNDLE_IDENTIFIER`).
- [ ] Create a subscription group "Comlogue Pro" with `comlogue.pro.monthly` ($14.99) and `comlogue.pro.yearly` ($95.99, 7-day free trial). The prices are hypotheses from the spec; change them in App Store Connect and in `backend/.env`.
- [ ] Host the privacy policy and terms at the URLs in `Brand` (`Comlogue/Core/Domain/DomainCatalog.swift`), or change them there.
- [ ] Set a Development Team in Xcode, then archive and upload.

### Suggested listing

**Name:** Comlogue: Communication Coach
**Subtitle:** Speak clearly. Be understood.
**Promotional text:** Talk with an AI partner, or bring a real conversation. See what's working, with evidence, and practise one small change at a time.

**Description:**
> Comlogue is a communication coach that listens to how you actually talk.
>
> Start with five short conversations with an AI partner, or upload or record a real conversation, with everyone's permission. Comlogue checks the audio, makes sure it's assessing your voice, and gives feedback on clarity, structure, listening, warmth, persuasion, concision and storytelling. It only does this where there's real evidence. Skills it can't assess yet are marked "Not enough evidence yet", never scored low.
>
> Then practise with missions built around your goal: business communication, negotiation, conversation, storytelling or public speaking. Each mission has one clear target, an AI partner who pushes back, feedback on your attempt, and a real-life version to try for real.
>
> • Spar with realistic AI personas, from kind to brutal
> • Shadow great speeches line by line and match their rhythm
> • Rehearse an upcoming interview, pitch or difficult talk
> • Get a debrief of a recorded meeting: who spoke, your best moment, decisions
> • Delete any recording, or everything, at any time

**Keywords:** communication,public speaking,confidence,interview,presentation,speech coach,storytelling,negotiation,conversation,AI coach

**Category:** Education (secondary: Productivity)

### App privacy ("nutrition label")

| Data type | Linked to user | Tracking | Purpose |
| --- | --- | --- | --- |
| Audio data | Yes | No | App functionality |
| Other user content (transcripts, reflections) | Yes | No | App functionality |
| Device ID (anonymous install ID) | Yes | No | App functionality |
| Purchase history | Yes | No | App functionality |

### Review notes (paste into App Review information)

> Comlogue analyses speech to give communication feedback. To test without recording others, choose "Talk with an AI partner" on the first screen. Microphone access is used only while the person is recording. Background audio mode is used so a recording of a meeting continues when the screen locks; recording status, pause and stop are always visible. Users can delete their recordings, their voice sample, or their whole account in Settings → Privacy & data.

## 3. Needs legal review before launch

- **Voice reference (biometric-adjacent).** Illinois BIPA, Texas CUBI and Washington's biometric law may apply to voiceprints. Confirm the consent text (`consents.voice_reference` in the backend), the written retention schedule (currently "until you delete it, or 18 months of inactivity") and the published policy.
- **Recording others.** The product requires everyone's agreement everywhere. Have counsel review the regional guidance text in `backend/app/domain/recording_rules.py`.
- **Third-party processing.** Audio is processed by OpenAI. Check your data processing terms and whether you need zero data retention.
- **Conversational twin references.** The shipped references are illustrative archetypes. Adding real people (even public-domain speeches) needs sign-off.
- **Children.** Positioned for adults (the spec says "students over 25"). Set the age rating accordingly.

## 4. Pilot readiness

- [ ] Calibrate the thresholds marked "pilot calibration required": audio quality, speaker matching, and per-dimension evidence minimums.
- [ ] Review `feedback_reports` ("Not quite right?") weekly. They're the fastest signal of miscalibrated feedback.
- [ ] Track the pilot metrics from the spec: first-task completion, voluntary retries, return for the next mission, real-life application, improvement on a fresh scenario. Report engagement and learning separately.
