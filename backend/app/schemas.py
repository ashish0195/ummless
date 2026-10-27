"""API request/response models. These mirror docs/API.md exactly (snake_case, nullable-not-omitted).

Timestamps are plain strings produced by `timeutil.iso` (no fractional seconds), so the contract is
enforced in one place instead of relying on the JSON encoder.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DimensionId = Literal["clarity", "structure", "listening", "warmth", "persuasion", "concision", "storytelling"]
DimensionStatus = Literal["assessed", "provisional", "not_enough_evidence", "not_assessed"]
Confidence = Literal["low", "moderate", "high"]
Usable = Literal["yes", "partly", "no"]
ActivityId = Literal["meet_someone_new", "explain_interest", "respond_to_someone", "make_a_case", "tell_a_story"]
TrackId = Literal["negotiation", "business", "conversational", "storytelling", "public_speaking", "interviews"]
ContextId = Literal["social", "networking", "meetings", "interviews"]
EaseId = Literal["explaining", "contributing", "connecting", "persuading", "concise"]
Difficulty = Literal["kind", "real", "brutal"]
MissionType = Literal["learn_and_try", "remix", "real_life", "weekly_reveal"]
SourceType = Literal["conversation", "recording"]
EventKind = Literal[
    "interview", "meeting", "presentation", "social", "negotiation", "other", "placement", "group_discussion",
    "client_call", "viva", "appraisal",
]
Market = Literal["us", "in", "global"]
ConversationKind = Literal["assessment_activity", "mission", "spar", "daily", "group"]
NotificationCategory = Literal[
    "practice", "event_prep", "results", "check_in", "nudge", "weekly_reveal", "milestone", "tips"
]
DailyKind = Literal["explain", "story", "persuade", "answer", "opinion", "introduce", "summarize", "respond"]
PanelKind = Literal["group_discussion", "panel_interview"]
PushAuthorization = Literal["authorized", "provisional", "ephemeral", "denied", "not_determined"]
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_hhmm(value: str | None, field: str) -> str | None:
    if value is not None and not _TIME_RE.match(value):
        raise ValueError(f"{field} must be HH:MM (24h)")
    return value


def _check_date(value: str | None) -> str | None:
    if value is not None:
        from datetime import date as _date

        _date.fromisoformat(value)
    return value


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------- shared objects


class Issue(APIModel):
    code: str
    title: str
    detail: str
    severity: Literal["blocking", "warning"]


class Partner(APIModel):
    name: str
    role: str
    voice: str
    symbol: str
    color_hex: str


class TurnQuality(APIModel):
    usable: Usable
    issues: list[Issue]
    speech_seconds: float
    duration_seconds: float


class Turn(APIModel):
    index: int
    speaker: Literal["partner", "user"]
    text: str
    audio_url: str | None
    created_at: str
    quality: TurnQuality | None
    coach_whisper: str | None
    excluded: bool
    speaker_id: str | None = None  # participant id on group-conversation partner turns


class Participant(APIModel):
    id: str
    name: str
    role: str
    voice: str
    symbol: str
    color_hex: str


class EvidenceMoment(APIModel):
    quote: str
    note: str | None
    source_type: SourceType
    source_id: str
    turn_index: int | None
    start_seconds: float | None
    end_seconds: float | None
    audio_url: str | None


class NextStep(APIModel):
    type: Literal["activity"] = "activity"
    activity_id: ActivityId
    title: str
    minutes: int


class DimensionResult(APIModel):
    dimension: DimensionId
    title: str
    status: DimensionStatus
    level: int | None
    level_label: str | None
    confidence: Confidence | None
    summary: str | None
    strengths: list[str]
    one_change: str | None
    evidence: list[EvidenceMoment]
    missing_reason: str | None
    next_step: NextStep | None
    assessed_at: str | None
    context_label: str | None


class SpeechPatterns(APIModel):
    words_per_minute: float | None
    filler_per_minute: float | None
    top_fillers: list[str]
    hedges_per_minute: float | None
    avg_pause_seconds: float | None
    longest_turn_seconds: float | None
    talk_share: float | None
    user_speech_seconds: float
    language_supported: bool


class RewriteMoment(APIModel):
    dimension: DimensionId | None
    you_said: str
    try_instead: str
    why: str
    source_type: SourceType
    source_id: str
    turn_index: int | None
    start_seconds: float | None
    end_seconds: float | None
    audio_url: str | None


class StyleResult(APIModel):
    status: Literal["ready", "provisional", "not_ready"]
    archetype: str | None
    description: str | None
    traits: list[str]
    message: str | None


RecoveryActionType = Literal[
    "retry", "record_again", "upload_another", "ai_practice", "identify_speaker", "gap_fill", "starter_course",
    "continue",
]
RecoveryProblem = Literal[
    "file_unreadable", "audio_unclear", "speaker_uncertain", "too_little_evidence", "no_dimensions",
    "processing_failed",
]


class RecoveryAction(APIModel):
    type: RecoveryActionType
    title: str
    activity_id: ActivityId | None


class Recovery(APIModel):
    problem: RecoveryProblem
    title: str
    message: str
    actions: list[RecoveryAction]
    extra_minutes: int | None


class AnalysisResult(APIModel):
    status: Literal["complete", "partial", "none"]
    headline: str
    summary: str
    dimensions: list[DimensionResult]
    speech_patterns: SpeechPatterns | None
    first_win: RewriteMoment | None
    style: StyleResult
    recovery: Recovery | None
    context_label: str
    created_at: str


# ---------------------------------------------------------------- auth, meta, me


class DeviceAuthRequest(APIModel):
    device_id: str = Field(min_length=8, max_length=160)
    platform: str = "ios"
    app_version: str | None = None


class DeviceAuthResponse(APIModel):
    token: str
    user_id: str
    is_new: bool


class Health(APIModel):
    status: Literal["ok"]
    demo_mode: bool
    version: str


class CodeName(APIModel):
    code: str
    name: str


class TrackInfo(APIModel):
    id: TrackId
    title: str
    subtitle: str
    symbol: str


class IdTitle(APIModel):
    id: str
    title: str


class DimensionInfo(APIModel):
    id: DimensionId
    title: str
    description: str
    symbol: str
    color_hex: str


class ActivityInfo(APIModel):
    id: ActivityId
    title: str
    prompt: str
    duration_label: str
    suggested_seconds: int
    dimensions: list[DimensionId]


class Pricing(APIModel):
    monthly_usd: float  # USD reference values (unchanged from v1)
    yearly_usd: float
    trial_days: int
    monthly_product_id: str
    yearly_product_id: str
    note: str
    currency: Literal["USD", "INR"]
    monthly_price: float
    yearly_price: float
    monthly_display: str
    yearly_display: str


class ConsentTranslation(APIModel):
    title: str
    body: str
    bullets: list[str]


class ConsentText(APIModel):
    version: str
    title: str
    body: str
    bullets: list[str]
    translations: dict[str, ConsentTranslation] = Field(default_factory=dict)


class EventKindInfo(APIModel):
    id: EventKind
    title: str
    symbol: str
    markets: list[Market]


class SupportInfo(APIModel):
    email: str
    grievance_email: str
    grievance_officer: str | None


class Consents(APIModel):
    analysis: ConsentText
    voice_reference: ConsentText
    recording: ConsentText


class Limits(APIModel):
    free_spar_per_week: int
    free_talks: int
    max_upload_mb: int
    max_recording_minutes: int


class Meta(APIModel):
    demo_mode: bool
    api_version: str
    languages: list[CodeName]
    tracks: list[TrackInfo]
    contexts: list[IdTitle]
    ease_targets: list[IdTitle]
    dimensions: list[DimensionInfo]
    activities: list[ActivityInfo]
    assessment_estimate_minutes: list[int]
    voice_setup_estimate_minutes: int
    pricing: Pricing
    pricing_by_market: dict[str, Pricing]
    consents: Consents
    limits: Limits
    event_kinds: list[EventKindInfo]
    support: SupportInfo


class RecordingRules(APIModel):
    region: str
    region_name: str
    rule: Literal["all_party", "one_party", "mixed", "unknown"]
    headline: str
    detail: str
    policy: str
    how_to_ask: str
    disclaimer: str
    regions: list[CodeName]


class Onboarding(APIModel):
    completed: bool
    contexts_ranked: list[ContextId]
    ease_targets: list[EaseId]
    goal_track: TrackId | None
    language: str
    region: str | None
    analysis_consent_version: str | None
    analysis_consented_at: str | None
    course_started: bool
    age_confirmed: bool = False


class PracticeSettings(APIModel):
    weekly_target: int
    reminder_time: str | None
    reminder_days: list[int]
    anchor: str | None = None
    paused_until: str | None = None


class NotificationSettings(APIModel):
    practice_reminders: bool
    event_prep: bool
    results: bool
    check_ins: bool
    nudges: bool
    weekly_reveal: bool
    tips: bool
    quiet_start: str
    quiet_end: str


class VoiceReferenceStatus(APIModel):
    status: Literal["none", "active"]
    created_at: str | None
    duration_seconds: float | None
    consent_version: str | None


class Entitlement(APIModel):
    tier: Literal["free", "pro"]
    expires_at: str | None
    source: Literal["none", "app_store", "dev"]
    product_id: str | None


class Me(APIModel):
    user_id: str
    created_at: str
    demo_mode: bool
    onboarding: Onboarding
    practice_settings: PracticeSettings
    voice_reference: VoiceReferenceStatus
    entitlement: Entitlement
    has_results: bool
    next_step: Literal["onboarding", "choose_input", "home"]
    market: Market
    timezone: str
    notification_settings: NotificationSettings


class OnboardingPatch(APIModel):
    completed: bool | None = None
    contexts_ranked: list[ContextId] | None = None
    ease_targets: list[EaseId] | None = None
    goal_track: TrackId | None = None
    language: str | None = Field(default=None, max_length=10)
    region: str | None = Field(default=None, max_length=12)
    analysis_consent_version: str | None = Field(default=None, max_length=40)
    course_started: bool | None = None
    age_confirmed: bool | None = None


class PracticeSettingsPatch(APIModel):
    weekly_target: int | None = Field(default=None, ge=1, le=14)
    reminder_time: str | None = None
    reminder_days: list[int] | None = None
    anchor: str | None = Field(default=None, max_length=120)
    paused_until: str | None = None

    @field_validator("reminder_time")
    @classmethod
    def _time(cls, value: str | None) -> str | None:
        return _check_hhmm(value, "reminder_time")

    @field_validator("paused_until")
    @classmethod
    def _paused(cls, value: str | None) -> str | None:
        return _check_date(value)

    @field_validator("reminder_days")
    @classmethod
    def _days(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(day < 1 or day > 7 for day in value):
            raise ValueError("reminder_days must be 1 (Mon) … 7 (Sun)")
        return sorted(set(value)) if value is not None else None


class NotificationSettingsPatch(APIModel):
    practice_reminders: bool | None = None
    event_prep: bool | None = None
    results: bool | None = None
    check_ins: bool | None = None
    nudges: bool | None = None
    weekly_reveal: bool | None = None
    tips: bool | None = None
    quiet_start: str | None = None
    quiet_end: str | None = None

    @field_validator("quiet_start", "quiet_end")
    @classmethod
    def _quiet(cls, value: str | None) -> str | None:
        return _check_hhmm(value, "quiet hours")


class MePatch(APIModel):
    onboarding: OnboardingPatch | None = None
    practice_settings: PracticeSettingsPatch | None = None
    notification_settings: NotificationSettingsPatch | None = None


# ---------------------------------------------------------------- devices & notifications


class DeviceRegistration(APIModel):
    apns_token: str | None = Field(default=None, max_length=200)
    push_environment: Literal["sandbox", "production"] | None = None
    authorization: PushAuthorization = "not_determined"
    timezone: str = Field(min_length=1, max_length=64)
    locale: str = Field(default="en-US", max_length=20)
    app_version: str = Field(default="", max_length=40)

    @field_validator("apns_token")
    @classmethod
    def _token(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if not re.fullmatch(r"[0-9a-fA-F]{32,200}", value):
            raise ValueError("apns_token must be the hex device token")
        return value.lower()


class DeviceOut(APIModel):
    id: str
    push_enabled: bool


class NotificationOut(APIModel):
    id: str
    category: NotificationCategory
    title: str
    body: str
    deep_link: str
    created_at: str
    read: bool


class NotificationList(APIModel):
    items: list[NotificationOut]
    unread_count: int


class NotificationRead(APIModel):
    ids: list[str] | None = None
    all: bool = False


class UnreadCount(APIModel):
    unread_count: int


# ---------------------------------------------------------------- daily rep


class DailyRepPreview(APIModel):
    date: str
    prompt_id: str
    title: str
    prompt: str
    dimension: DimensionId


class DailyUpcoming(APIModel):
    items: list[DailyRepPreview]


class VoiceEnrollmentResult(APIModel):
    status: Literal["active", "rejected"]
    issues: list[Issue]
    message: str
    reference: VoiceReferenceStatus


# ---------------------------------------------------------------- conversations


class ConversationSetup(APIModel):
    title: str
    context: str
    target_behavior: str | None
    suggested_seconds: int
    tips: list[str]
    activity_id: ActivityId | None
    mission_id: str | None
    persona_id: str | None
    difficulty: Difficulty | None
    quick: bool


class ConversationOut(APIModel):
    id: str
    kind: ConversationKind
    status: Literal["active", "finished"]
    partner: Partner
    setup: ConversationSetup
    turns: list[Turn]
    awaiting: Literal["user", "none"]
    user_turns: int
    max_user_turns: int
    assessment_id: str | None
    mission_id: str | None
    demo_mode: bool
    created_at: str
    participants: list[Participant] = Field(default_factory=list)


class ConversationCreate(APIModel):
    kind: Literal["mission", "spar", "daily", "group"]
    mission_id: str | None = None
    daily_date: str | None = None
    panel_id: str | None = Field(default=None, max_length=80)
    quick: bool = False
    persona_id: str | None = None
    custom_scenario: str | None = Field(default=None, max_length=600)
    difficulty: Difficulty | None = None
    event_id: str | None = None
    prep_id: str | None = None


class TurnResult(APIModel):
    conversation: ConversationOut
    user_turn: Turn
    partner_turn: Turn | None
    retry_suggested: bool
    done: bool
    partner_turns: list[Turn] = Field(default_factory=list)


class ResultRef(APIModel):
    type: Literal["assessment", "mission_attempt", "spar_report", "daily_attempt"]
    id: str


class FinishResult(APIModel):
    conversation: ConversationOut
    result_ref: ResultRef | None


# ---------------------------------------------------------------- assessments


class AssessmentActivity(APIModel):
    id: ActivityId
    title: str
    prompt: str
    duration_label: str
    suggested_seconds: int
    dimensions: list[DimensionId]
    status: Literal["pending", "in_progress", "done", "skipped"]
    conversation_id: str | None


class AssessmentOut(APIModel):
    id: str
    route: Literal["roleplay"]
    purpose: Literal["baseline", "gap_fill"]
    status: Literal["in_progress", "processing", "complete", "needs_recovery"]
    stage: str | None
    activities: list[AssessmentActivity]
    estimate_minutes: list[int]
    target_dimensions: list[DimensionId]
    result: AnalysisResult | None
    created_at: str
    completed_at: str | None


class AssessmentCreate(APIModel):
    purpose: Literal["baseline", "gap_fill"] = "baseline"
    activity_ids: list[ActivityId] | None = None
    target_dimensions: list[DimensionId] | None = None


class AssessmentList(APIModel):
    items: list[AssessmentOut]


# ---------------------------------------------------------------- recordings


class RecordingQuality(APIModel):
    usable: Usable
    issues: list[Issue]
    usable_seconds: float
    total_seconds: float


class SpeakerCandidate(APIModel):
    label: str
    display_name: str
    speech_seconds: float
    turns: int
    sample_url: str | None
    sample_text: str | None
    is_proposed_user: bool
    match: Literal["reference", "acoustic", "loudest", "none"]
    match_strength: Literal["strong", "weak", "conflict"] | None


class Attribution(APIModel):
    status: Literal["pending", "confirmed", "auto", "not_present"]
    user_speaker_label: str | None
    requires_confirmation: bool
    reason: Literal["first_conversation", "uncertain_match", "no_reference", "conflict"] | None
    message: str | None


class TalkShare(APIModel):
    label: str
    display_name: str
    is_user: bool
    share: float


class MeetingDebrief(APIModel):
    talk_share: list[TalkShare]
    best_moment: EvidenceMoment | None
    decisions: list[str]
    follow_up_summary: str | None
    one_thing_to_try: str | None


class RecordingOut(APIModel):
    id: str
    title: str
    source: Literal["upload", "live"]
    status: Literal[
        "processing", "needs_speaker_confirmation", "assessing", "complete", "needs_recovery", "failed", "no_user"
    ]
    stage: Literal["decoding", "checking_audio", "identifying_speakers", "assessing"] | None
    duration_seconds: float | None
    created_at: str
    quality: RecordingQuality | None
    speakers: list[SpeakerCandidate]
    attribution: Attribution
    result: AnalysisResult | None
    debrief: MeetingDebrief | None
    recovery: Recovery | None


class RecordingList(APIModel):
    items: list[RecordingOut]


class RecordingConsent(APIModel):
    attested: bool
    region: str | None = None
    rule: str | None = None
    consent_version: str = Field(max_length=40)


class SpeakerConfirmation(APIModel):
    decision: Literal["confirm", "choose", "not_present"]
    speaker_label: str | None = None


class TranscriptSegment(APIModel):
    speaker: str
    is_user: bool
    start: float
    end: float
    text: str
    excluded: bool
    exclusion_reason: str | None


class Transcript(APIModel):
    segments: list[TranscriptSegment]


# ---------------------------------------------------------------- profile


class HistoryEntry(APIModel):
    dimension: DimensionId
    status: DimensionStatus
    level: int | None
    level_label: str | None
    assessed_at: str
    context_label: str
    source_type: Literal["assessment", "recording"]
    source_id: str


class ProfileSource(APIModel):
    type: Literal["assessment", "recording"]
    id: str
    title: str
    created_at: str
    status: str


class TwinMatch(APIModel):
    aspect: str
    aspect_title: str
    reference_name: str
    reference_blurb: str
    closeness: float
    your_value: str
    reference_value: str


class TwinResult(APIModel):
    status: Literal["not_ready", "ready"]
    message: str
    disclaimer: str
    next_step: NextStep | None
    matches: list[TwinMatch]


class Profile(APIModel):
    basis: Literal["assessment", "partial", "goal_only", "none"]
    headline: str
    summary: str | None
    dimensions: list[DimensionResult]
    speech_patterns: SpeechPatterns | None
    style: StyleResult
    twin: TwinResult
    first_win: RewriteMoment | None
    history: list[HistoryEntry]
    sources: list[ProfileSource]
    updated_at: str | None


# ---------------------------------------------------------------- course & missions


class MissionSummary(APIModel):
    id: str
    type: MissionType
    title: str
    minutes: int
    status: Literal["available", "completed", "locked"]
    locked_reason: Literal["subscribe"] | None


class CourseModule(APIModel):
    id: str
    index: int
    title: str
    dimension: DimensionId
    target_behavior: str
    summary: str
    status: Literal["current", "available", "completed"]
    completed_missions: int
    missions: list[MissionSummary]


class GapTask(APIModel):
    dimension: DimensionId
    activity_id: ActivityId
    title: str
    minutes: int
    reason: str


class QuickOption(APIModel):
    mission_id: str
    title: str
    minutes: int


class TodayPlan(APIModel):
    mission: MissionSummary
    module_title: str
    quick: QuickOption | None


class Course(APIModel):
    track: TrackInfo
    basis: Literal["profile", "goal"]
    basis_label: str
    basis_explainer: str
    focus_module_id: str
    modules: list[CourseModule]
    gap_tasks: list[GapTask]
    today: TodayPlan | None
    is_pro: bool
    free_mission_id: str | None


class TrackChange(APIModel):
    track: TrackId


class FocusChange(APIModel):
    module_id: str


class MissionExample(APIModel):
    text: str
    audio_url: str | None
    explanation: str


class RealLife(APIModel):
    prompt: str
    ai_alternative_title: str
    reflection_questions: list[str]


class Comparison(APIModel):
    previous_attempt_id: str
    summary: str
    changes: list[str]
    note: str


class AttemptFeedback(APIModel):
    assessable: Usable
    target_met: Literal["yes", "partly", "no", "unclear"]
    headline: str
    where: EvidenceMoment | None
    what_worked: list[str]
    one_change: str | None
    missing_evidence: str | None
    comparison: Comparison | None
    issues: list[Issue]


class MissionAttemptOut(APIModel):
    id: str
    conversation_id: str
    attempt_number: int
    quick: bool
    status: Literal["processing", "complete", "failed"]
    feedback: AttemptFeedback | None
    created_at: str


class ReflectionOut(APIModel):
    id: str
    text: str
    went: Literal["well", "mixed", "hard"] | None
    coach_reply: str | None
    created_at: str


class MissionOut(APIModel):
    id: str
    module_id: str
    track_id: TrackId
    type: MissionType
    title: str
    dimension: DimensionId
    minutes: int
    context: str
    target_behavior: str
    why_it_matters: str
    example: MissionExample
    steps: list[str]
    suggested_seconds: int
    real_life: RealLife | None
    attempts: list[MissionAttemptOut]
    reflections: list[ReflectionOut]
    status: Literal["available", "completed", "locked"]
    locked_reason: Literal["subscribe"] | None
    takeaway: str | None


class MissionComplete(APIModel):
    takeaway: str | None = Field(default=None, max_length=2000)


class ReflectionCreate(APIModel):
    text: str = Field(min_length=1, max_length=4000)
    went: Literal["well", "mixed", "hard"] | None = None


class DailyRep(APIModel):
    date: str
    prompt_id: str
    title: str
    prompt: str
    kind: DailyKind
    dimension: DimensionId
    target_behavior: str
    tips: list[str]
    suggested_seconds: int
    example: str | None
    can_shuffle: bool
    completed: bool
    attempts: list[MissionAttemptOut]


# ---------------------------------------------------------------- spar, talks, events


class Persona(APIModel):
    id: str
    name: str
    title: str
    scenario: str
    description: str
    default_difficulty: Difficulty
    symbol: str
    color_hex: str
    is_free: bool


class PersonaList(APIModel):
    personas: list[Persona]


class SparOutcome(APIModel):
    label: str
    detail: str


class MomentumPoint(APIModel):
    turn_index: int
    value: float
    note: str | None


class Observation(APIModel):
    dimension: DimensionId
    note: str


class SparReportOut(APIModel):
    conversation_id: str
    status: Literal["processing", "complete", "failed"]
    title: str
    outcome: SparOutcome | None
    momentum: list[MomentumPoint]
    moments: list[RewriteMoment]
    observations: list[Observation]
    next_step: str | None


class SparSession(APIModel):
    conversation_id: str
    title: str
    persona_name: str
    difficulty: Difficulty
    created_at: str
    status: str
    outcome_label: str | None


class SparSessionList(APIModel):
    items: list[SparSession]


class TalkStyle(APIModel):
    wpm: float
    avg_pause_seconds: float
    avg_sentence_words: float


class TalkSummary(APIModel):
    id: str
    title: str
    speaker: str
    source_note: str
    year: int | None
    duration_label: str
    lines_count: int
    style: TalkStyle
    tags: list[str]
    is_free: bool


class TalkList(APIModel):
    talks: list[TalkSummary]


class TalkLine(APIModel):
    index: int
    text: str
    display_text: str
    pause_count: int
    audio_url: str | None


class Talk(TalkSummary):
    technique: str
    breakdown: list[str]
    lines: list[TalkLine]
    locked: bool


class PrepItem(APIModel):
    id: str
    title: str
    scenario: str
    partner_role: str
    difficulty: Difficulty


class UpcomingEventOut(APIModel):
    id: str
    title: str
    kind: EventKind
    date: str
    notes: str | None
    prep: list[PrepItem]
    created_at: str
    time: str | None = None
    reflection: ReflectionOut | None = None


class EventList(APIModel):
    events: list[UpcomingEventOut]


class EventCreate(APIModel):
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = "other"
    date: str
    notes: str | None = Field(default=None, max_length=2000)
    time: str | None = None

    @field_validator("date")
    @classmethod
    def _date(cls, value: str) -> str:
        from datetime import date as _date

        _date.fromisoformat(value)
        return value

    @field_validator("time")
    @classmethod
    def _time(cls, value: str | None) -> str | None:
        return _check_hhmm(value, "time")


# ---------------------------------------------------------------- progress & review


class MilestoneOut(APIModel):
    id: str
    title: str
    detail: str
    achieved_at: str


class ThisWeek(APIModel):
    sessions: int
    target: int
    days: list[int] = Field(default_factory=list)  # weekdays with a session, 1 = Monday
    met: bool = False


class PracticeTotals(APIModel):
    total_sessions: int
    missions_completed: int
    minutes: int
    weeks_active: int
    this_week: ThisWeek
    reps: int = 0
    weeks_on_target: int = 0
    best_weeks_on_target: int = 0
    paused_until: str | None = None


class WelcomeBack(APIModel):
    days_away: int
    message: str


class RecentItem(APIModel):
    type: str
    title: str
    created_at: str


class Progress(APIModel):
    practice: PracticeTotals
    milestones: list[MilestoneOut]
    recent: list[RecentItem]
    welcome_back: WelcomeBack | None = None


class WeekPractice(APIModel):
    sessions: int
    days: int  # days practised: the unit of `target`
    missions_completed: int
    attempts: int
    retries: int
    real_life_attempts: int
    minutes: int
    target: int
    met_target: bool


class BeforeAfter(APIModel):
    mission_title: str
    before_quote: str
    after_quote: str
    note: str


class SkillUpdate(APIModel):
    dimension: DimensionId
    change: Literal["new_estimate", "unchanged"]
    note: str


class FocusOption(APIModel):
    module_id: str
    title: str
    reason: str


class WeeklyReview(APIModel):
    week_start: str
    week_end: str
    practice: WeekPractice
    highlights: list[str]
    before_after: BeforeAfter | None
    skill_updates: list[SkillUpdate]
    evidence_note: str
    next_focus_options: list[FocusOption]
    milestones: list[MilestoneOut]
    message: str


# ---------------------------------------------------------------- billing


class AppStoreTransaction(APIModel):
    signed_transaction: str = Field(min_length=10)


class DevGrant(APIModel):
    tier: Literal["pro", "free"]


# ---------------------------------------------------------------- feedback reports & dev tools


class FeedbackReportCreate(APIModel):
    target_type: Literal["dimension_result", "attempt_feedback", "spar_report", "recording"]
    target_id: str = Field(min_length=1, max_length=80)
    dimension: DimensionId | None = None
    reason: Literal["inaccurate", "misheard", "wrong_speaker", "unfair", "other"]
    note: str | None = Field(default=None, max_length=2000)


class FeedbackReportOut(APIModel):
    id: str
    message: str


class DemoSeedRequest(APIModel):
    pro: bool = False
    market: Literal["us", "in"] = "us"


class DemoSeedResult(APIModel):
    assessment_id: str
    recording_needs_confirmation_id: str | None
    recording_complete_id: str | None
    mission_id: str | None
    spar_conversation_id: str | None
    event_id: str | None
    daily_date: str | None = None
    previous_daily_date: str | None = None
    group_conversation_id: str | None = None
    panel_id: str | None = None


# ---------------------------------------------------------------- group conversations


class Panel(APIModel):
    id: str
    kind: PanelKind
    title: str
    scenario: str
    description: str
    topic: str | None
    user_role: str
    participants: list[Participant]
    minutes: int
    markets: list[Market]
    is_free: bool
    symbol: str
    color_hex: str
    default_difficulty: Difficulty


class PanelList(APIModel):
    panels: list[Panel]
