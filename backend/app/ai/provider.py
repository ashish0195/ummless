"""The AI provider interface. `OpenAIProvider` is production; `MockProvider` is the offline demo."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .llm_schemas import (
    AssessmentJudgement,
    AttemptJudgement,
    CustomScenario,
    DebriefJudgement,
    EventPrep,
    PartnerReply,
    ReflectionReply,
    SparJudgement,
    WeeklyJudgement,
)
from .types import (
    AssessmentRequest,
    AttemptRequest,
    AudioHint,
    CustomScenarioRequest,
    DebriefRequest,
    DiarizationResult,
    EventPrepRequest,
    KnownSpeaker,
    PartnerReplyRequest,
    ReflectionRequest,
    SparRequest,
    TranscriptionResult,
    WeeklyRequest,
)


class AIProvider(ABC):
    name: str = "base"
    demo: bool = False

    # --- audio ---
    @abstractmethod
    def transcribe(self, audio_path: str, *, language: str, prompt: str | None, hint: AudioHint) -> TranscriptionResult:
        """Transcribe a single-speaker turn. Raise AIUnavailableError on failure."""

    @abstractmethod
    def diarize(
        self, audio_path: str, *, language: str, known_speakers: list[KnownSpeaker], hint: AudioHint
    ) -> DiarizationResult:
        """Transcribe with speaker labels (known speakers keep their given names)."""

    @abstractmethod
    def synthesize(self, text: str, *, voice: str, instructions: str | None) -> bytes | None:
        """Return MP3 bytes, or None when speech synthesis is unavailable (the app then speaks on-device)."""

    # --- language ---
    @abstractmethod
    def partner_reply(self, req: PartnerReplyRequest) -> PartnerReply: ...

    @abstractmethod
    def assess(self, req: AssessmentRequest) -> AssessmentJudgement: ...

    @abstractmethod
    def attempt_feedback(self, req: AttemptRequest) -> AttemptJudgement: ...

    @abstractmethod
    def spar_report(self, req: SparRequest) -> SparJudgement: ...

    @abstractmethod
    def reflection_reply(self, req: ReflectionRequest) -> ReflectionReply: ...

    @abstractmethod
    def event_prep(self, req: EventPrepRequest) -> EventPrep: ...

    @abstractmethod
    def weekly(self, req: WeeklyRequest) -> WeeklyJudgement: ...

    @abstractmethod
    def debrief(self, req: DebriefRequest) -> DebriefJudgement: ...

    @abstractmethod
    def custom_scenario(self, req: CustomScenarioRequest) -> CustomScenario: ...
