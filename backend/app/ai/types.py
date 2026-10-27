"""Provider-neutral request/result types for the AI layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.evidence import Cap, OpportunityStats, Unit


@dataclass
class TranscriptionResult:
    text: str
    avg_logprob: float | None = None
    low_confidence_ratio: float | None = None  # share of tokens with logprob < -1.0
    model: str = ""


@dataclass
class DiarizedSegment:
    speaker: str
    start: float
    end: float
    text: str


@dataclass
class DiarizationResult:
    segments: list[DiarizedSegment]
    duration: float
    model: str = ""
    used_references: bool = False  # whether known-speaker references were actually applied


@dataclass
class KnownSpeaker:
    name: str
    wav_path: str  # 2–10 s reference clip


@dataclass
class AudioHint:
    """Context that only the demo provider uses (it cannot hear the audio)."""

    context_key: str = ""
    turn_index: int = 0
    mock_text: str | None = None
    wav_path: str | None = None  # decoded 16 kHz wav, for demo diarization
    known_voiceprints: dict[str, dict] = field(default_factory=dict)


@dataclass
class PartnerReplyRequest:
    kind: str  # assessment_activity | mission | spar
    language: str
    partner_name: str
    partner_role: str
    partner_character: str
    situation: str
    step_key: str
    step_instruction: str
    fallback_line: str
    is_closing: bool
    history: list[tuple[str, str]]  # (speaker label, text), chronological; last item is the user's turn
    difficulty: str | None = None
    difficulty_behaviour: str | None = None
    win_condition: str | None = None
    target_behavior: str | None = None
    want_coach_whisper: bool = False
    want_momentum: bool = False
    turns_left: int = 0


@dataclass
class AssessmentRequest:
    language: str
    context_description: str
    units: list[Unit]
    stats: OpportunityStats
    caps: dict[str, Cap]
    style_eligible: bool
    target_dimensions: list[str] = field(default_factory=list)
    activity_notes: list[str] = field(default_factory=list)


@dataclass
class AttemptRequest:
    language: str
    mission_title: str
    target_behavior: str
    context: str
    partner_name: str
    units: list[Unit]
    previous_units: list[Unit] | None = None
    previous_headline: str | None = None
    quick: bool = False


@dataclass
class SparRequest:
    language: str
    persona_name: str
    persona_title: str
    scenario: str
    difficulty: str
    win_condition: str
    units: list[Unit]
    momentum: list[tuple[int, float]]
    kind: str = "spar"  # spar | group
    evaluation_focus: list[str] = field(default_factory=list)  # group: what the report looks for
    context: str = ""  # group: the situation and what good looks like


@dataclass
class GroupMember:
    id: str
    name: str
    role: str
    stance: str  # who they are and how they behave in this discussion
    is_moderator: bool = False


@dataclass
class GroupReplyRequest:
    language: str
    panel_kind: str  # group_discussion | panel_interview
    title: str
    topic: str | None
    situation: str
    user_role: str
    members: list[GroupMember]  # moderator first
    history: list[tuple[str, str]]  # (speaker label, text), chronological; last item is the user's turn
    is_closing: bool
    turns_left: int
    fallback_lines: list[tuple[str, str]]  # (member id, line) used when the model is unavailable
    difficulty: str | None = None
    difficulty_behaviour: str | None = None


@dataclass
class ReflectionRequest:
    language: str
    mission_title: str
    target_behavior: str
    real_life_prompt: str
    text: str
    went: str | None


@dataclass
class EventPrepRequest:
    language: str
    title: str
    kind: str
    date: str
    notes: str | None
    goal_title: str
    kind_hint: str | None = None  # what good prep looks like for this kind of event
    market: str = "global"
    time: str | None = None


@dataclass
class WeeklyRequest:
    language: str
    facts: list[str]
    focus_title: str


@dataclass
class DebriefRequest:
    language: str
    title: str
    units: list[Unit]
    talk_share: list[tuple[str, float, bool]]  # (speaker name, share, is_user)


@dataclass
class CustomScenarioRequest:
    language: str
    scenario: str
    difficulty: str
