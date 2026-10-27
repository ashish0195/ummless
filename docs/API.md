# Comlogue API — contract (v1 + v2 additions)

This is the contract between the iOS app and the backend. The backend's generated OpenAPI document
(`docs/openapi.json`) and the contract fixtures (`contract-fixtures/*.json`, decoded by the Swift tests) are
generated from the implementation and must agree with this file.

## Conventions

- Base path `/v1`. JSON bodies, **snake_case** keys. The app decodes with `convertFromSnakeCase`, so keys must
  not rely on acronym casing (`audio_url` → `audioUrl`).
- Auth: `Authorization: Bearer <token>` on every endpoint except `POST /v1/auth/device`, `GET /v1/health` and
  signed media URLs.
- Timestamps: ISO 8601 UTC **without fractional seconds**, e.g. `"2026-10-26T21:00:00Z"`. Dates: `"2026-10-30"`.
- IDs are opaque strings with prefixes: `usr_`, `asm_`, `cnv_`, `rec_`, `att_`, `med_`, `evt_`, `ref_`, `rfl_`,
  `fbk_`, `dev_`, `ntf_`.
  Content IDs (activities, missions, personas, talks) are readable slugs (e.g. `business.m1.learn`).
- Nullable fields are always present (`null`), never omitted. Arrays are never null.
- Audio/media URLs are **relative** (`/v1/media/med_…?exp=…&sig=…`); the client resolves them against its base URL.
  Media endpoints accept either the signature or the bearer token. `EvidenceMoment.audio_url` /
  `RewriteMoment.audio_url` / `SpeakerCandidate.sample_url` point to a **short clip** of just that moment — play it
  from the start; `start_seconds`/`end_seconds` locate the moment in the source for display only. Any media URL
  can be `null` (e.g. demo mode, or no audio) — the app then hides playback or speaks the text on-device.
- Errors: HTTP status + `{"error": {"code": "string", "message": "Human-readable"}}`.
  Codes: `unauthorized` 401 · `consent_required` 403 · `not_found` 404 · `conflict` 409 · `file_too_large` 413 ·
  `unsupported_media` 415 · `validation_error` 422 · `subscription_required` 402 · `rate_limited` 429 ·
  `ai_unavailable` 503 · `internal` 500.
- Multipart uploads use the field `audio` for the file; other fields are form strings (JSON-encoded when noted).

## Shared enums

```
DimensionId     = "clarity" | "structure" | "listening" | "warmth" | "persuasion" | "concision" | "storytelling"
DimensionStatus = "assessed" | "provisional" | "not_enough_evidence" | "not_assessed"
Confidence      = "low" | "moderate" | "high"
Usable          = "yes" | "partly" | "no"
ActivityId      = "meet_someone_new" | "explain_interest" | "respond_to_someone" | "make_a_case" | "tell_a_story"
TrackId         = "negotiation" | "business" | "conversational" | "storytelling" | "public_speaking"
ContextId       = "social" | "networking" | "meetings" | "interviews"
EaseId          = "explaining" | "contributing" | "connecting" | "persuading" | "concise"
Difficulty      = "kind" | "real" | "brutal"
MissionType     = "learn_and_try" | "remix" | "real_life" | "weekly_reveal"
```

Level bands: `1 Emerging · 2 Developing · 3 Capable · 4 Strong · 5 Exceptional`. There is **no overall score**.

## Shared objects

```
Issue          { code: string, title: string, detail: string, severity: "blocking" | "warning" }
                 // codes: file_unreadable, no_speech, too_short, too_quiet, noisy, clipping, overlapping_voices,
                 //        background_voices, low_intelligibility, multiple_speakers, user_not_found,
                 //        speaker_uncertain, too_little_user_speech, transcription_failed,
                 //        trimmed (a long recording was analyzed up to the length limit)
Partner        { name: string, role: string, voice: string, symbol: string, color_hex: string }
Turn           { index: int, speaker: "partner" | "user", text: string, audio_url: string?, created_at: ISODate,
                 quality: TurnQuality?, coach_whisper: string?, excluded: bool }
TurnQuality    { usable: Usable, issues: [Issue], speech_seconds: number, duration_seconds: number }
EvidenceMoment { quote: string, note: string?, source_type: "conversation" | "recording", source_id: string,
                 turn_index: int?, start_seconds: number?, end_seconds: number?, audio_url: string? }
NextStep       { type: "activity", activity_id: ActivityId, title: string, minutes: int }
DimensionResult{ dimension: DimensionId, title: string, status: DimensionStatus,
                 level: int?, level_label: string?, confidence: Confidence?,
                 summary: string?, strengths: [string], one_change: string?,
                 evidence: [EvidenceMoment], missing_reason: string?, next_step: NextStep?,
                 assessed_at: ISODate?, context_label: string? }
SpeechPatterns { words_per_minute: number?, filler_per_minute: number?, top_fillers: [string],
                 hedges_per_minute: number?, avg_pause_seconds: number?, longest_turn_seconds: number?,
                 talk_share: number?, user_speech_seconds: number, language_supported: bool }
RewriteMoment  { dimension: DimensionId?, you_said: string, try_instead: string, why: string,
                 source_type: "conversation" | "recording", source_id: string, turn_index: int?,
                 start_seconds: number?, end_seconds: number?, audio_url: string? }
StyleResult    { status: "ready" | "provisional" | "not_ready", archetype: string?, description: string?,
                 traits: [string], message: string? }
RecoveryAction { type: "retry" | "record_again" | "upload_another" | "ai_practice" | "identify_speaker"
                       | "gap_fill" | "starter_course" | "continue", title: string, activity_id: ActivityId? }
Recovery       { problem: "file_unreadable" | "audio_unclear" | "speaker_uncertain" | "too_little_evidence"
                         | "no_dimensions" | "processing_failed",   // processing_failed = our side; offer "retry"
                 title: string, message: string, actions: [RecoveryAction], extra_minutes: int? }
AnalysisResult { status: "complete" | "partial" | "none", headline: string, summary: string,
                 dimensions: [DimensionResult]  // always 7, canonical order
                 speech_patterns: SpeechPatterns?, first_win: RewriteMoment?, style: StyleResult,
                 recovery: Recovery?, context_label: string, created_at: ISODate }
```

`AnalysisResult.status`: `complete` = all 7 assessed/provisional; `partial` = at least one; `none` = zero
(then `recovery` is set and offers `starter_course`).

## Auth & meta

### `POST /v1/auth/device`
Body `{ device_id: string, platform: "ios", app_version: string }` →
`{ token: string, user_id: string, is_new: bool }`. Same device_id → same user.

### `GET /v1/health` → `{ status: "ok", demo_mode: bool, version: string }`

### `GET /v1/meta`
```
{ demo_mode: bool, api_version: "1",
  languages: [{ code, name }], tracks: [{ id: TrackId, title, subtitle, symbol }],
  contexts: [{ id: ContextId, title }], ease_targets: [{ id: EaseId, title }],
  dimensions: [{ id: DimensionId, title, description, symbol, color_hex }],
  activities: [{ id: ActivityId, title, prompt, duration_label, suggested_seconds, dimensions: [DimensionId] }],
  assessment_estimate_minutes: [int, int], voice_setup_estimate_minutes: int,
  pricing: { monthly_usd, yearly_usd, trial_days, monthly_product_id, yearly_product_id, note },
  consents: { analysis: ConsentText, voice_reference: ConsentText, recording: ConsentText },
  limits: { free_spar_per_week: int, free_talks: int, max_upload_mb: int, max_recording_minutes: int } }
ConsentText { version: string, title: string, body: string, bullets: [string] }
```

### `GET /v1/meta/recording-rules?region=US-CA`
```
{ region: string, region_name: string, rule: "all_party" | "one_party" | "mixed" | "unknown",
  headline: string, detail: string, policy: string, how_to_ask: string, disclaimer: string,
  regions: [{ code, name }] }
```

## Me

```
Me { user_id, created_at, demo_mode: bool,
     onboarding: { completed: bool, contexts_ranked: [ContextId], ease_targets: [EaseId], goal_track: TrackId?,
                   language: string, region: string?, analysis_consent_version: string?,
                   analysis_consented_at: ISODate?, course_started: bool },
     practice_settings: { weekly_target: int, reminder_time: string? /*"HH:MM"*/, reminder_days: [int] /*1=Mon*/ },
     voice_reference: VoiceReference, entitlement: Entitlement,
     has_results: bool, next_step: "onboarding" | "choose_input" | "home" }
VoiceReference { status: "none" | "active", created_at: ISODate?, duration_seconds: number?, consent_version: string? }
Entitlement    { tier: "free" | "pro", expires_at: ISODate?, source: "none" | "app_store" | "dev", product_id: string? }
```
- `GET /v1/me` → `Me`
- `PATCH /v1/me` body `{ onboarding?: {…partial, analysis_consent_version?: string, course_started?: bool},
  practice_settings?: {…partial} }` → `Me`. Only fields present in the body change (send `null` to clear, e.g.
  `reminder_time`). Setting `analysis_consent_version` records consent time server-side. Setting `goal_track` also
  switches the course track.
- `next_step`: `onboarding` until `onboarding.completed`; then `home` once the user has any evidence-backed result
  **or** chose "start a goal-based course for now" (`course_started: true`); otherwise `choose_input`.
- `DELETE /v1/me` → `204`. Deletes every recording, result, voice reference and the account.

Audio-accepting endpoints return `403 consent_required` until analysis consent is recorded.

## Voice reference

- `GET /v1/voice-reference` → `VoiceReference`
- `POST /v1/voice-reference` multipart `audio`, `consent_version`, `consent_accepted=true` →
  `{ status: "active" | "rejected", issues: [Issue], message: string, reference: VoiceReference }`.
  Checks: usable audio, ≥ 8 s of speech, a single speaker. The prompt is never scored.
- `DELETE /v1/voice-reference` → `204`. Stops automatic matching; recordings/results untouched.

## Conversations (AI voice engine)

One engine powers assessment activities, missions and spar. The partner always speaks first (turn 0).

```
Conversation { id, kind: "assessment_activity" | "mission" | "spar", status: "active" | "finished",
               partner: Partner, setup: ConversationSetup, turns: [Turn], awaiting: "user" | "none",
               user_turns: int, max_user_turns: int,
               assessment_id: string?, mission_id: string?, demo_mode: bool, created_at: ISODate }
ConversationSetup { title, context, target_behavior: string?, suggested_seconds: int, tips: [string],
                    activity_id: ActivityId?, mission_id: string?, persona_id: string?, difficulty: Difficulty?,
                    quick: bool }
TurnResult  { conversation: Conversation, user_turn: Turn, partner_turn: Turn?, retry_suggested: bool, done: bool }
FinishResult{ conversation: Conversation, result_ref: { type: "assessment" | "mission_attempt" | "spar_report",
                                                        id: string }? }
```
- `POST /v1/conversations` body
  `{ kind: "mission" | "spar", mission_id?, quick?: bool, persona_id?, custom_scenario?, difficulty?, event_id?, prep_id? }`
  → `Conversation`. (Assessment conversations are created via the assessment endpoints.)
- `GET /v1/conversations/{id}` → `Conversation`
- `POST /v1/conversations/{id}/turns` multipart `audio`, `elapsed_seconds`, `client_metrics` (JSON, optional) →
  `TurnResult`. If the turn is not usable, `partner_turn` is null, `retry_suggested` is true and the turn is
  `excluded`. Recording the turn again simply posts another turn. If transcription itself fails (AI outage) the
  endpoint returns `503 ai_unavailable` and stores nothing — resend the same audio.
- Mission conversations accept an optional `difficulty`: `"brutal"` is the app's **Harder challenge** (the partner
  raises a tougher, more specific objection and doesn't concede easily), `"kind"` makes it gentler; absent ⇒
  default behaviour. It is echoed in `setup.difficulty`.
- `POST /v1/conversations/{id}/finish` → `FinishResult`. Missions → feedback is generated asynchronously
  (poll `GET /v1/missions/{id}`). Spar → poll `GET /v1/spar/reports/{conversation_id}`.

## Assessments (guided AI roleplay and gap-fill tasks)

```
Assessment { id, route: "roleplay", purpose: "baseline" | "gap_fill",
             status: "in_progress" | "processing" | "complete" | "needs_recovery",
             stage: string?, activities: [AssessmentActivity], estimate_minutes: [int, int],
             target_dimensions: [DimensionId], result: AnalysisResult?, created_at, completed_at: ISODate? }
AssessmentActivity { id: ActivityId, title, prompt, duration_label, suggested_seconds, dimensions: [DimensionId],
                     status: "pending" | "in_progress" | "done" | "skipped", conversation_id: string? }
```
- `POST /v1/assessments` body `{ purpose: "baseline" | "gap_fill", activity_ids?: [ActivityId], target_dimensions?: [DimensionId] }`
- `GET /v1/assessments/{id}` · `GET /v1/assessments` → `{ items: [Assessment] }`
- `POST /v1/assessments/{id}/activities/{activity_id}/start` → `Conversation` (idempotent)
- `POST /v1/assessments/{id}/activities/{activity_id}/skip` → `Assessment`
- `POST /v1/assessments/{id}/finalize` → `Assessment` (`processing`; poll until `complete`/`needs_recovery`).
  Finalizing with some activities skipped is allowed — the result is partial, never penalized. Allowed again from
  `needs_recovery` (e.g. after `processing_failed`, or after redoing an activity — starting an activity moves the
  assessment back to `in_progress`).

## Recordings (upload & live)

```
Recording { id, title, source: "upload" | "live",
            status: "processing" | "needs_speaker_confirmation" | "assessing" | "complete" | "needs_recovery"
                  | "failed" | "no_user",
            stage: "decoding" | "checking_audio" | "identifying_speakers" | "assessing" | null,
            duration_seconds: number?, created_at, quality: RecordingQuality?, speakers: [SpeakerCandidate],
            attribution: Attribution, result: AnalysisResult?, debrief: MeetingDebrief?, recovery: Recovery? }
RecordingQuality { usable: Usable, issues: [Issue], usable_seconds: number, total_seconds: number }
SpeakerCandidate { label, display_name, speech_seconds, turns: int, sample_url: string?, sample_text: string?,
                   is_proposed_user: bool, match: "reference" | "acoustic" | "loudest" | "none",
                   match_strength: "strong" | "weak" | "conflict" | null }
Attribution { status: "pending" | "confirmed" | "auto" | "not_present", user_speaker_label: string?,
              requires_confirmation: bool,
              reason: "first_conversation" | "uncertain_match" | "no_reference" | "conflict" | null, message: string? }
MeetingDebrief { talk_share: [{ label, display_name, is_user: bool, share: number }], best_moment: EvidenceMoment?,
                 decisions: [string], follow_up_summary: string?, one_thing_to_try: string? }
```
- `POST /v1/recordings` multipart `audio`, `source`, `title?`, `consent` (JSON:
  `{ attested: true, region: string?, rule: string?, consent_version: string }`) → `Recording` (`processing`).
- `GET /v1/recordings` → `{ items: [Recording] }` · `GET /v1/recordings/{id}` → `Recording`
- `POST /v1/recordings/{id}/speaker-confirmation` body `{ decision: "confirm" | "choose" | "not_present", speaker_label?: string }`
  → `Recording`. Allowed again later (correction ⇒ reassessment).
- `POST /v1/recordings/{id}/retry` → `Recording`. Only for `failed` recordings whose `recovery.problem` is
  `processing_failed` (our side); `409` otherwise.
- Speaker `label`s are opaque per-file identifiers (e.g. `"A"`, `"B"`, or `"me"` when the diarizer matched the
  voice reference). Show `display_name`; send `label` back. Labels never carry across files.
- `GET /v1/recordings/{id}/transcript` → `{ segments: [{ speaker, is_user: bool, start, end, text, excluded: bool, exclusion_reason: string? }] }`
  (`speaker` here is the display name).
- `DELETE /v1/recordings/{id}` → `204` (audio + derived results; profile recomputed).

State machine: `processing` → (`failed` | `needs_recovery` | `needs_speaker_confirmation` | `assessing`) →
`complete` | `needs_recovery` | `no_user`.

## Profile

```
Profile { basis: "assessment" | "partial" | "goal_only" | "none", headline: string, summary: string?,
          dimensions: [DimensionResult], speech_patterns: SpeechPatterns?, style: StyleResult, twin: TwinResult,
          first_win: RewriteMoment?, history: [HistoryEntry], sources: [ProfileSource], updated_at: ISODate? }
HistoryEntry  { dimension: DimensionId, status: DimensionStatus, level: int?, level_label: string?,
                assessed_at: ISODate, context_label: string, source_type: "assessment" | "recording", source_id: string }
ProfileSource { type: "assessment" | "recording", id, title, created_at: ISODate, status: string }
TwinResult { status: "not_ready" | "ready", message: string, disclaimer: string, next_step: NextStep?,
             matches: [{ aspect, aspect_title, reference_name, reference_blurb, closeness: number /*0–1*/,
                         your_value: string, reference_value: string }] }
```
- `GET /v1/profile` → `Profile`. Per dimension, the most recent assessed/provisional estimate wins; unusable
  new audio never replaces an older valid estimate.

## Course & missions

```
Course { track: Track, basis: "profile" | "goal", basis_label: string, basis_explainer: string,
         focus_module_id: string, modules: [CourseModule], gap_tasks: [GapTask], today: TodayPlan?,
         is_pro: bool, free_mission_id: string? }
Track { id: TrackId, title, subtitle, symbol }
CourseModule { id, index: int, title, dimension: DimensionId, target_behavior, summary,
               status: "current" | "available" | "completed", completed_missions: int, missions: [MissionSummary] }
MissionSummary { id, type: MissionType, title, minutes: int, status: "available" | "completed" | "locked",
                 locked_reason: "subscribe" | null }
GapTask { dimension: DimensionId, activity_id: ActivityId, title, minutes: int, reason }
TodayPlan { mission: MissionSummary, module_title: string, quick: { mission_id, title, minutes: int }? }
Mission { id, module_id, track_id: TrackId, type: MissionType, title, dimension: DimensionId, minutes: int,
          context, target_behavior, why_it_matters,
          example: { text, audio_url: string?, explanation }, steps: [string], suggested_seconds: int,
          real_life: { prompt, ai_alternative_title, reflection_questions: [string] }?,
          attempts: [MissionAttempt], reflections: [Reflection],
          status: "available" | "completed" | "locked", locked_reason: "subscribe" | null, takeaway: string? }
MissionAttempt { id, conversation_id, attempt_number: int, quick: bool, status: "processing" | "complete" | "failed",
                 feedback: AttemptFeedback?, created_at }
AttemptFeedback { assessable: Usable, target_met: "yes" | "partly" | "no" | "unclear", headline: string,
                  where: EvidenceMoment?, what_worked: [string], one_change: string?, missing_evidence: string?,
                  comparison: { previous_attempt_id, summary, changes: [string], note }?, issues: [Issue] }
Reflection { id, text, went: "well" | "mixed" | "hard" | null, coach_reply: string?, created_at }
```
- `GET /v1/course` → `Course` (works with no results: `basis: "goal"`).
- `POST /v1/course/track` `{ track: TrackId }` → `Course` · `POST /v1/course/focus` `{ module_id }` → `Course`
- `GET /v1/missions/{id}` → `Mission` (locked missions still return content for the preview)
- `POST /v1/missions/{id}/complete` `{ takeaway?: string }` → `Mission`
- `POST /v1/missions/{id}/reflections` `{ text: string, went?: "well" | "mixed" | "hard" }` → `Reflection`
- Attempts: `POST /v1/conversations { kind: "mission", mission_id, quick?, difficulty? }` → turns → `finish`.
  Locked missions return `402 subscription_required`. Free users get exactly one practice mission
  (`Course.free_mission_id`); starting it locks in that choice.

## Spar, talks, events

```
Persona { id, name, title, scenario, description, default_difficulty: Difficulty, symbol, color_hex, is_free: bool }
SparReport { conversation_id, status: "processing" | "complete" | "failed", title: string,
             outcome: { label, detail }?, momentum: [{ turn_index: int, value: number /*0–1*/, note: string? }],
             moments: [RewriteMoment], observations: [{ dimension: DimensionId, note: string }], next_step: string? }
SparSession { conversation_id, title, persona_name, difficulty: Difficulty, created_at, status: string, outcome_label: string? }
TalkSummary { id, title, speaker, source_note, year: int?, duration_label, lines_count: int,
              style: { wpm: number, avg_pause_seconds: number, avg_sentence_words: number }, tags: [string], is_free: bool }
Talk  = TalkSummary + { technique: string, breakdown: [string], lines: [TalkLine], locked: bool }
TalkLine { index: int, text: string /* with [pause] markers */, display_text: string, pause_count: int, audio_url: string? }
UpcomingEvent { id, title, kind: "interview" | "meeting" | "presentation" | "social" | "negotiation" | "other",
                date: string /*YYYY-MM-DD*/, notes: string?, prep: [PrepItem], created_at }
PrepItem { id, title, scenario, partner_role, difficulty: Difficulty }
```
- `GET /v1/spar/personas` → `{ personas: [Persona] }` · `GET /v1/spar/sessions` → `{ items: [SparSession] }`
- `GET /v1/spar/reports/{conversation_id}` → `SparReport`
- `GET /v1/talks` → `{ talks: [TalkSummary] }` · `GET /v1/talks/{id}` → `Talk`
- `GET /v1/talks/{id}/lines/{index}/audio` → `audio/mpeg` (TTS, cached). `TalkLine.audio_url` is this relative
  path (bearer auth, not signed) or `null` in demo mode / when TTS is unavailable — speak the line on-device then.
  Locked talks return only the first 2 lines and `locked: true`; other lines' audio returns `402`.
- `GET /v1/events` → `{ events: [UpcomingEvent] }` · `POST /v1/events` `{ title, kind, date, notes? }` → `UpcomingEvent`
  (AI builds 3 prep items) · `DELETE /v1/events/{id}` → `204`
- Rehearse a prep item: `POST /v1/conversations { kind: "spar", event_id, prep_id, difficulty }`.

## Progress & weekly review

```
Milestone { id, title, detail, achieved_at: ISODate }
Progress { practice: { total_sessions: int, missions_completed: int, minutes: int, weeks_active: int,
                       this_week: { sessions: int, target: int } },
           milestones: [Milestone], recent: [{ type: string, title: string, created_at: ISODate }] }
WeeklyReview { week_start: string, week_end: string,
               practice: { sessions, missions_completed, attempts, retries, real_life_attempts, minutes, target, met_target: bool },
               highlights: [string], before_after: { mission_title, before_quote, after_quote, note }?,
               skill_updates: [{ dimension: DimensionId, change: "new_estimate" | "unchanged", note: string }],
               evidence_note: string, next_focus_options: [{ module_id, title, reason }],
               milestones: [Milestone], message: string }
```
- `GET /v1/progress` → `Progress` · `GET /v1/review/weekly` → `WeeklyReview`

## Billing

- `POST /v1/billing/app-store` `{ signed_transaction: string }` → `Entitlement`
- `POST /v1/billing/dev-grant` `{ tier: "pro" | "free" }` → `Entitlement`. Dev tools are allowed when
  `ALLOW_DEV_ENTITLEMENTS=true`, or when it is unset outside production; otherwise `403 forbidden`.

## Media

- `GET /v1/media/{media_id}` → audio bytes (`audio/mp4`, `audio/mpeg`, `audio/wav`). Auth: bearer token or `exp`+`sig`.

## Feedback reports

"This looks wrong" from any result. Stored for the team to review; **never changes results**.

- `POST /v1/feedback-reports` body
  `{ target_type: "dimension_result" | "attempt_feedback" | "spar_report" | "recording", target_id: string,
     dimension: DimensionId?, reason: "inaccurate" | "misheard" | "wrong_speaker" | "unfair" | "other", note: string? }`
  → `201 { id: "fbk_…", message: "Thanks — we review every report to improve Comlogue." }`.
  Unknown enum values → `422 validation_error`. Reports are deleted with the account.

## Dev tools

Only when dev entitlements are allowed (see Billing); otherwise `404 not_found`.

- `POST /v1/dev/seed-demo` body `{ pro: bool, market?: "us" | "in" }` → `{ assessment_id: string,
  recording_needs_confirmation_id: string?, recording_complete_id: string?, mission_id: string?,
  spar_conversation_id: string?, event_id: string?, daily_date: string?, previous_daily_date: string?,
  group_conversation_id: string?, panel_id: string? }`.
  Seeds a rich, realistic state for the calling user without audio processing or AI calls: onboarding + analysis
  consent (if missing), a completed baseline with a **partial** result (5 dimensions assessed/provisional, listening
  and storytelling "Not enough evidence yet"), a recording awaiting speaker confirmation (3 speakers, one proposed;
  confirming it runs a real assessment), a completed 1:1 recording with a meeting debrief, the free mission with two
  attempts (the second compares against the first) plus a reflection, two spar sessions with reports, an upcoming
  event with three prep items, milestones and practice for this week. `pro: true` also grants dev Pro. Idempotent
  per user: later calls return the same ids. Media URLs in seeded data are `null`.
- v2 (`market`, default `us`): sets the region (`US-CA` or `IN`) and the market's timezone (a device-reported
  timezone that fits the market is kept), age confirmation, and a practice plan (08:30 on weekdays, anchored to
  "After my morning coffee" / "After my morning chai"). It also seeds the habit loop:
  - today's rep, **not** done (`daily_date`, also `GET /v1/daily`);
  - reps on 2–3 earlier days (this week, or the end of last week early in the week). `previous_daily_date` is the
    most recent of them — always yesterday — with two attempts on `explain.job_to_kid`: the first `partly` met with
    a quote and a "Try: …" change, the second `yes` with a `comparison`;
  - three earlier weeks that met the weekly target (`weeks_on_target` ≥ 4 with today's sessions) and their
    milestones;
  - a finished group session with a report (`group_conversation_id`, `panel_id`: `gd.remote_work_india` for `in`,
    a US panel interview for `us`);
  - an event tomorrow with a time (a campus-placement HR round for `in`, a final-round interview for `us`);
  - four inbox items (event prep and a recording waiting — unread; recording results and last week's reveal —
    read), never pushed.
  For `in`, names, the event, labels (`27 Oct`) and one sparring partner (Kevin, the US-client call) are Indian
  market content. The first call's market wins.

## v2 — Habit, notifications and markets (US & India)

Everything below is additive: new endpoints, new fields with defaults, and new enum values. Clients must keep
decoding unknown enum values gracefully (the app maps them to a fallback).

### New and extended enums

```
Market               = "us" | "in" | "global"
TrackId             += "interviews"
ConversationKind     = "assessment_activity" | "mission" | "spar" | "daily" | "group"
EventKind            = "interview" | "meeting" | "presentation" | "social" | "negotiation" | "other"
                       | "placement" | "group_discussion" | "client_call" | "viva" | "appraisal"
NotificationCategory = "practice" | "event_prep" | "results" | "check_in" | "nudge" | "weekly_reveal"
                       | "milestone" | "tips"
DailyKind            = "explain" | "story" | "persuade" | "answer" | "opinion" | "introduce" | "summarize" | "respond"
PanelKind            = "group_discussion" | "panel_interview"
```

### Markets

`Me.market` is derived (read-only) from `onboarding.region`: `IN` or `IN-*` → `in`; `US` or `US-*` → `us`;
anything else (or unset) → `global` (US-style content, USD pricing). Note `US-IN` is Indiana, i.e. `us`.

The market changes:
- **Content.** Daily prompts, sparring personas (order and availability), group-discussion panels, course scenario
  variants (names, places, rupees vs dollars, "12 LPA" vs "$135k"), event kinds.
- **Formats.** Server-written labels such as `context_label` use `27 Oct` for `in` and `Oct 27` for `us`/`global`.
- **Pricing.** See `Meta.pricing`.
- **Default timezone** before the device reports one: `in` → `Asia/Kolkata`, `us` → `America/New_York`,
  `global` → `UTC`.

Accent, dialect (e.g. Indian English) and code-switching (e.g. Hinglish) are never scored or "corrected". A
rewrite may offer a "global English" alternative only when the user's context calls for it (e.g. a call with US
clients), and labels it as an option.

`hinglish` conversations are transcribed without a language hint (the transcription prompt describes the
Hindi–English mix, in Latin script), and AI partners reply in natural Hinglish. Filler and hedge statistics stay
English-only (`speech_patterns.language_supported: false` for other languages).

### Meta additions

```
Meta += { pricing: Pricing /* for the caller's market */, pricing_by_market: { us: Pricing, in: Pricing, global: Pricing },
          event_kinds: [{ id: EventKind, title: string, symbol: string, markets: [Market] }],
          support: { email: string, grievance_email: string, grievance_officer: string? } }
Pricing += { currency: "USD" | "INR", monthly_price: number, yearly_price: number,
             monthly_display: string /* "$14.99", "₹399" */, yearly_display: string }
           // monthly_usd / yearly_usd stay as USD reference values.
ConsentText += { translations: { [language: string]: { title: string, body: string, bullets: [string] } } }
           // `hi` drafts for analysis, voice_reference and recording (legal review pending).
languages  += { code: "hinglish", name: "Hinglish (Hindi + English)" }
```
Defaults: `us`/`global` $14.99/month, $95.99/year; `in` ₹399/month, ₹2,499/year; 7-day trial everywhere. These
are pilot hypotheses. The App Store's localized price (StoreKit `displayPrice`) always wins in the app.

### Me additions

```
Me += { market: Market, timezone: string /* IANA, last reported by the device or the market default */,
        notification_settings: NotificationSettings }
onboarding        += { age_confirmed: bool }
practice_settings += { anchor: string? /* "After my morning chai or coffee" */,
                       paused_until: string? /* YYYY-MM-DD in the user's timezone; a planned break */ }
NotificationSettings { practice_reminders: bool, event_prep: bool, results: bool, check_ins: bool, nudges: bool,
                       weekly_reveal: bool, tips: bool, quiet_start: "HH:MM", quiet_end: "HH:MM" }
```
- Defaults: every category `true` except `tips` (`false`; product news needs explicit opt-in), quiet hours
  `22:00`–`08:00`.
- `PATCH /v1/me` accepts `notification_settings` (partial), `practice_settings.anchor`,
  `practice_settings.paused_until` (`null` ends a break) and `onboarding.age_confirmed`.
- Recording analysis consent now also needs `age_confirmed: true`, in the same PATCH or an earlier one. Without it,
  setting `analysis_consent_version` returns `422 validation_error`. Comlogue is for adults (18+), in line with
  the DPDP Act's definition of a child in India. Accounts that consented before v2 keep their consent.
- `quiet_start`/`quiet_end` must be `HH:MM` (`422` otherwise); equal values mean no quiet hours. `anchor` is
  trimmed (empty → `null`, at most 120 characters).

### Devices and push

```
DeviceRegistration { apns_token: string?, push_environment: "sandbox" | "production" | null,
                     authorization: "authorized" | "provisional" | "ephemeral" | "denied" | "not_determined",
                     timezone: string /* IANA */, locale: string /* "en-IN" */, app_version: string }
Device { id: string /* dev_… */, push_enabled: bool }
```
- `POST /v1/devices` body `DeviceRegistration` → `Device`. Upserts the caller's device (one per install). It also
  sets `Me.timezone` (an unknown IANA name → `422`). The app calls it at launch, whenever the APNs token or
  permission changes, and when the timezone changes. `apns_token` is the hex device token (32–200 hex characters,
  stored lowercase; `null` or `""` clears it); a token reported by another account moves to this one. Omitted
  fields default to `authorization: "not_determined"`, `locale: "en-US"`, `app_version: ""` and
  `push_environment: "production"` when a token is sent.
- `push_enabled` means **the server will deliver pushes to this device**: APNs is configured on the server (not
  inbox-only) **and** the device has a token **and** authorization is `authorized`, `provisional` or `ephemeral`.
  So it is `false` on a server without `APNS_*` even when the device has a token and permission. When it's
  `false`, the app schedules its own local notifications; when it's `true`, the app leaves event prep, check-ins,
  nudges and the weekly reveal to the server. A token APNs rejects (`410`, `BadDeviceToken`,
  `DeviceTokenNotForTopic`) is cleared, so the next registration returns `false` until the app sends a new one.
- `DELETE /v1/devices/{id}` → `204` (`404` for another account's device). Devices are also removed with the
  account.

The server sends pushes through APNs (token auth) when `APNS_*` is configured. Otherwise notifications go to the
in-app inbox only.

**Push rules**
- Categories follow `NotificationSettings`. With a category turned off, the server creates no inbox item for it —
  except `results`, which always reach the inbox (only the push is skipped). `milestone` follows the `results`
  toggle; `tips` has no server-generated items yet.
- Quiet hours apply in the user's timezone; a push due in quiet hours is deferred to `quiet_end`.
- At most 2 pushes per local day; further pushes that day are skipped (the inbox item stays).
- `results` is exempt from the cap and from quiet hours when the user was active in the last 30 minutes.
- Nothing during a planned break, except `results` and `event_prep`.
- Every push has an expiry (e.g. event prep expires when the event starts, results after 24 hours): a push that
  can't go out in time is dropped, never delivered late. The inbox item stays.
- The badge is the unread count. Pushes use `thread-id` = category and `apns-collapse-id` = dedupe key (hashed to
  64 bytes when longer). Passive items (milestones, the weekly reveal) use `apns-priority: 5`, others `10`.
- APNs `429`/`5xx` are retried up to 3 times, 5 minutes apart.

**Server-generated notifications**
- `results`:
  - a recording is ready or needs speaker confirmation; an assessment completes; mission or daily feedback is
    ready;
  - a recording or analysis that couldn't be finished (`needs_recovery`, `failed`) also gets one ("We couldn't
    finish …"), linking to the next step;
  - feedback is usually ready within seconds, so its push waits 90 seconds. It's dropped, and marked read, if the
    user has been back in the app since the feedback was ready. Otherwise the push brings them back to it.
- `event_prep`:
  - the evening before an event (19:00 local): "Tomorrow: {title}. A 5-minute warm-up tonight?"
  - the morning of it (08:00, or 2 hours before `time` when given): "Today: {title}…"
- `check_in`:
  - the day after an event (19:00): "How did {title} go?" — not sent when the event already has a reflection;
  - 2 days after a real-life mission was opened without a reflection.
- `nudge`:
  - after 3 quiet days and again after 8, never when no weekly target is set;
  - at most one per 72 hours;
  - after 2 unopened nudges, none until the user returns.
  - "Quiet" counts from the last practice session or tapped notification (or sign-up). Nudges go out at the user's
    `reminder_time` (18:00 if none), only after onboarding, never during a break. The first names today's rep
    ("Your 60-second rep is ready" / "Today: {title}. One minute is plenty — whenever suits you."); the second says
    "Pick up where you left off". No streak-loss language anywhere.
- `weekly_reveal`: Sunday 18:00 local when the user practised that week ("{n} sessions and {m} min of practice this
  week…").
- `milestone`: when a milestone is earned and the app is not in use (passive).
- The real-life check-in goes out between 10:00 and 20:00 local, 2–14 days after the mission was first opened, if
  there's no reflection and the mission isn't completed.

The scheduler runs inside the API process every `NOTIFICATIONS_TICK_SECONDS` (default 300). Producers are
idempotent (one item per user and dedupe key), so several instances can run it.

`practice` reminders are scheduled on the device (local notifications at the chosen time and days). The server
never sends them.

Deep links (`deep_link` in notifications and push payloads; the app also opens them from widgets and Shortcuts):
`comlogue://today`, `comlogue://daily`, `comlogue://daily/{date}`, `comlogue://mission/{id}`,
`comlogue://reflect/{mission_id}`, `comlogue://recording/{id}`, `comlogue://assessment/{id}`,
`comlogue://event/{id}`, `comlogue://review/weekly`, `comlogue://inbox`, `comlogue://practice`,
`comlogue://group/{panel_id}`, `comlogue://paywall`, `comlogue://settings/notifications`.

APNs payload: `{ "aps": { "alert": { "title", "body" }, "sound": "default", "badge": int, "thread-id": category,
"interruption-level": "active" | "passive" | "time-sensitive" }, "deep_link": string, "notification_id": string }`.

### Inbox

```
Notification { id: string /* ntf_… */, category: NotificationCategory, title: string, body: string,
               deep_link: string, created_at: ISODate, read: bool }
```
- `GET /v1/notifications?limit=50` → `{ items: [Notification] /* newest first */, unread_count: int }`
- `POST /v1/notifications/read` body `{ ids: [string] }` or `{ all: true }` → `{ unread_count: int }`
- `POST /v1/notifications/{id}/opened` → `204` (a tap on a push or inbox row; resets nudge back-off)
- `POST /v1/notifications/test` → `Notification` ("Notifications are on", category `results`, deep link
  `comlogue://settings/notifications` — pushed immediately when `push_enabled`, ignoring quiet hours and the cap)
- `limit` is 1–200 (default 50). `POST /v1/notifications/read` with neither `ids` nor `all: true` → `422`.
  `opened` on another account's notification → `404`.

### Daily rep

One short speaking prompt per day, chosen for the user's goal, focus skill and market; the core habit action.

```
DailyRep { date: string /* YYYY-MM-DD, user's timezone */, prompt_id: string, title: string, prompt: string,
           kind: DailyKind, dimension: DimensionId, target_behavior: string, tips: [string],
           suggested_seconds: int, example: string?, can_shuffle: bool, completed: bool,
           attempts: [MissionAttempt] }
DailyRepPreview { date: string, prompt_id: string, title: string, prompt: string, dimension: DimensionId }
```
- `GET /v1/daily` → today's `DailyRep`.
- `GET /v1/daily/upcoming?days=7` → `{ items: [DailyRepPreview] }`, today first, `days` ≤ 14. The assignments are
  stable, so the app can put tomorrow's actual prompt in tomorrow's reminder.
- `GET /v1/daily/{date}` → `DailyRep` (`404` outside today − 30 … today + 14 days; `422` for a malformed date).
  Past days are never assigned after the fact: a past date without an assignment is `404`.
- `POST /v1/daily/shuffle` → today's new `DailyRep`. Once per day, and only before the first attempt; otherwise
  `409 conflict`. `can_shuffle` is true only for today, before a shuffle and before any attempt.
- Attempts:
  - `POST /v1/conversations { kind: "daily", daily_date }` → `Conversation`. The coach reads the prompt as turn 0;
    the user gets one turn (`max_user_turns: 1`), then the coach's short closing line and `awaiting: "none"`.
    `daily_date` defaults to today and may be today or yesterday (a rep started just before midnight); any other
    date → `409 conflict`. Needs analysis consent (`403`).
  - `finish` → `result_ref { type: "daily_attempt", id }`. Feedback is generated asynchronously; poll
    `GET /v1/daily/{date}`. `AttemptFeedback` has the same shape as missions, with `comparison` on retries.
- Free for everyone, with unlimited retries. `completed` means at least one assessable attempt. A completed rep
  counts as one practice session (`daily_rep`) for its day, on its first assessable attempt; retries don't add
  sessions, so the weekly target stays honest.
- The "feedback ready" notification is sent only when the user has left the app (no activity for 2 minutes).
- Selection is deterministic per user and date:
  - weighted towards the course focus dimension, the goal track and the market;
  - lighter social prompts at weekends, seasonal prompts in season (Diwali, Thanksgiving, appraisal season…);
  - no repeats within 30 days.

### Habit and progress

```
Progress.practice += { reps: int, weeks_on_target: int, best_weeks_on_target: int, paused_until: string? }
Progress.practice.this_week += { days: [int] /* weekdays with a session, 1 = Mon */, met: bool }
Progress += { welcome_back: { days_away: int, message: string }? }
```
- Weeks run Monday to Sunday in the user's timezone, everywhere: this week, weekly reviews and milestones.
- `weeks_on_target`: consecutive completed weeks that met `weekly_target`, ending with last week, plus 1 if this week
  is already met. A week overlapping a planned break neither counts nor breaks the run.
- `welcome_back` is present when the user's previous session was ≥ 7 days before today. It's warm, with no guilt:
  "Welcome back — your progress is saved. Start with a 60-second rep." It disappears once they practise today.
- `this_week.met` is `sessions >= target`. A planned break is set with `practice_settings.paused_until`; ending it
  early (`null`) keeps the days already on break as break days.
- New milestones:
  - `first_rep`, `reps_10`, `reps_30`;
  - `weeks_on_target_2`, `weeks_on_target_4`, `weeks_on_target_8`, `weeks_on_target_12`;
  - `minutes_60`, `first_group`.
- Session types are now `assessment`, `recording`, `mission_attempt`, `spar_session`, `real_life`, `daily_rep` and
  `group_session`.

### Group conversations (group discussions and panel interviews)

Several AI participants and the user in one conversation, e.g. a campus-placement **group discussion** (GD) or a
three-person **panel interview**.

```
Participant { id: string, name: string, role: string, voice: string, symbol: string, color_hex: string }
Panel { id, kind: PanelKind, title, scenario, description, topic: string?, user_role: string,
        participants: [Participant] /* moderator first */, minutes: int, markets: [Market], is_free: bool,
        symbol: string, color_hex: string, default_difficulty: Difficulty }
Conversation += { participants: [Participant] /* [] unless kind == "group" */ }
Turn        += { speaker_id: string? /* participant id on group partner turns */ }
TurnResult  += { partner_turns: [Turn] /* every partner line produced after the user's turn, in order;
                                          partner_turn is the last of them (or null) */ }
```
- `GET /v1/group/panels` → `{ panels: [Panel] }` (market-relevant first).
- `POST /v1/conversations { kind: "group", panel_id, difficulty? }` → `Conversation`.
  - The moderator opens (turn 0), and up to two participants may speak before the user's first turn.
  - After each user turn, one or two participants respond in character. They build on, challenge or ignore what
    the user said, like a real GD.
  - `partner` is the moderator.
- `finish` → `result_ref { type: "spar_report", id: conversation_id }`. The report uses the `SparReport` shape
  (`GET /v1/spar/reports/{conversation_id}`) and focuses on entering the discussion, contribution quality, building
  on others, inclusiveness and summarising. `momentum` is empty for group reports. Finishing before the user's
  first turn → `result_ref: null` (nothing to review, nothing logged).
- Free users get the panels marked `is_free` (no weekly cap); locked panels return `402 subscription_required`.
  Missing `panel_id` → `422`, unknown → `404`.
- The session ends when the user's turns reach the panel's limit (the moderator closes), or earlier when the
  moderator wraps up naturally after at least two user turns. Each participant speaks with their own voice and
  delivery (`audio_url` per partner turn). Group sessions with a report also appear in `GET /v1/spar/sessions`
  (`persona_name` = the moderator).

### Events additions

```
UpcomingEvent += { time: string? /* "HH:MM" local, optional */ }
```
`POST /v1/events` accepts `time` and the new `EventKind` values (anything else → `422`; `time` must be `HH:MM`).
Prep items are tailored to the kind (each kind in `Meta.event_kinds` carries guidance for the model) and market,
e.g. a campus-placement HR round, a GD, or a late-night call with US clients.

### Event reflections

After an interview, pitch or hard conversation the user prepared for, the app asks "How did it go?". The check-in
notification the day after links to the event.

```
UpcomingEvent += { reflection: Reflection? }   // null until the user reflects
```
- `POST /v1/events/{id}/reflection` body `{ text: string (1–4000), went?: "well" | "mixed" | "hard" }` →
  `UpcomingEvent` with its `reflection`.
  - The coach's reply ties what happened to the user's current course focus. Reflections inform goals, and like
    mission reflections they are never audio evidence for skill estimates.
  - Allowed once the event's date has come (`409 conflict` before that).
  - Posting again replaces the text and `went` but keeps the same `id`.
  - The first reflection counts as a `real_life` practice session. It awards `first_real_life`, and pilot
    metrics count it as real-life application.
- `GET /v1/events` returns past events too (newest last), so the app can show "How did it go?" for recent ones.

### Data export

- `GET /v1/me/export` → `application/json` attachment (`comlogue-export.json`). It contains everything stored
  about the user:
  - settings, profile, assessment results and transcripts;
  - recording metadata, results and transcripts;
  - missions, attempts and reflections;
  - daily reps, events and notifications.

  Audio files are not included, and media links are `null`. Devices are listed without the push token
  (`push_token_registered: bool`). This covers access requests under the DPDP Act and US state privacy laws.
- Top-level keys: `export_version`, `exported_at`, `account` (the `Me` object plus locale, age confirmation time and
  planned breaks), `voice_reference`, `profile`, `assessments` (with conversation transcripts), `recordings` (with
  consent and transcript), `missions` (`completed`, `attempts` with transcripts, `reflections`), `daily_reps`,
  `spar_and_group_sessions` (transcripts and reports), `events`, `notifications` (with `opened_at` and push state),
  `devices`, `milestones`, `practice_log`, `feedback_reports`.

## Running the server

`uvicorn app.main:app --host 0.0.0.0 --port 8000` from `backend/` (the app is created lazily from environment
settings; `create_app(settings)` is the factory used by tests). See `backend/README.md`.

