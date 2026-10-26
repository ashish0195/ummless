# Comlogue API v1 — contract

This is the contract between the iOS app and the backend. The backend's generated OpenAPI document
(`docs/openapi.json`) and the contract fixtures (`contract-fixtures/*.json`, decoded by the Swift tests) are
generated from the implementation and must agree with this file.

## Conventions

- Base path `/v1`. JSON bodies, **snake_case** keys. The app decodes with `convertFromSnakeCase`, so keys must
  not rely on acronym casing (`audio_url` → `audioUrl`).
- Auth: `Authorization: Bearer <token>` on every endpoint except `POST /v1/auth/device`, `GET /v1/health` and
  signed media URLs.
- Timestamps: ISO 8601 UTC **without fractional seconds**, e.g. `"2026-10-26T21:00:00Z"`. Dates: `"2026-10-30"`.
- IDs are opaque strings with prefixes: `usr_`, `asm_`, `cnv_`, `rec_`, `att_`, `med_`, `evt_`, `ref_`.
  Content IDs (activities, missions, personas, talks) are readable slugs (e.g. `business.m1.learn`).
- Nullable fields are always present (`null`), never omitted. Arrays are never null.
- Audio/media URLs are **relative** (`/v1/media/med_…?exp=…&sig=…`); the client resolves them against its base URL.
  Media endpoints accept either the signature or the bearer token.
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
                 //        speaker_uncertain, too_little_user_speech, transcription_failed
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
                         | "no_dimensions",
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
                   analysis_consented_at: ISODate? },
     practice_settings: { weekly_target: int, reminder_time: string? /*"HH:MM"*/, reminder_days: [int] /*1=Mon*/ },
     voice_reference: VoiceReference, entitlement: Entitlement,
     has_results: bool, next_step: "onboarding" | "choose_input" | "home" }
VoiceReference { status: "none" | "active", created_at: ISODate?, duration_seconds: number?, consent_version: string? }
Entitlement    { tier: "free" | "pro", expires_at: ISODate?, source: "none" | "app_store" | "dev", product_id: string? }
```
- `GET /v1/me` → `Me`
- `PATCH /v1/me` body `{ onboarding?: {…partial, analysis_consent_version?: string}, practice_settings?: {…partial} }` → `Me`.
  Setting `analysis_consent_version` records consent time server-side.
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
  `excluded`. Recording the turn again simply posts another turn.
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
  Finalizing with some activities skipped is allowed — the result is partial, never penalized.

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
- `GET /v1/recordings/{id}/transcript` → `{ segments: [{ speaker, is_user: bool, start, end, text, excluded: bool, exclusion_reason: string? }] }`
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
- Attempts: `POST /v1/conversations { kind: "mission", mission_id, quick? }` → turns → `finish`.
  Locked missions return `402 subscription_required`.

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
- `GET /v1/talks/{id}/lines/{index}/audio` → `audio/mpeg` (TTS, cached)
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
- `POST /v1/billing/dev-grant` `{ tier: "pro" | "free" }` → `Entitlement` (only when `ALLOW_DEV_ENTITLEMENTS=true`)

## Media

- `GET /v1/media/{media_id}` → audio bytes (`audio/mp4`, `audio/mpeg`, `audio/wav`). Auth: bearer token or `exp`+`sig`.
