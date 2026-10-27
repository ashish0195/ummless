"""OpenAI-backed provider (SDK v3).

Resilience: the SDK retries 429/5xx/connection errors (`max_retries`); on top of that every call walks a
model-fallback chain (model not found / no access ⇒ next model) and remembers the first model that works.
Responses are not stored at OpenAI (`store=False`).
"""

from __future__ import annotations

import base64
import logging
import math
import threading
from collections.abc import Callable
from typing import TypeVar

import openai
from pydantic import BaseModel

from ..config import Settings
from ..domain.languages import transcription_language
from ..errors import AIUnavailableError
from . import prompts
from .llm_schemas import (
    AssessmentJudgement,
    AttemptJudgement,
    CustomScenario,
    DebriefJudgement,
    EventPrep,
    GroupReply,
    PartnerReply,
    ReflectionReply,
    SparJudgement,
    WeeklyJudgement,
)
from .provider import AIProvider
from .types import (
    AssessmentRequest,
    AttemptRequest,
    AudioHint,
    CustomScenarioRequest,
    DebriefRequest,
    DiarizationResult,
    DiarizedSegment,
    EventPrepRequest,
    GroupReplyRequest,
    KnownSpeaker,
    PartnerReplyRequest,
    ReflectionRequest,
    SparRequest,
    TranscriptionResult,
    WeeklyRequest,
)

log = logging.getLogger("comlogue.ai.openai")
T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)

_MODEL_ERROR_HINTS = ("model", "does not exist", "not found", "no access", "not have access", "unsupported model")


def _is_model_unavailable(exc: Exception) -> bool:
    if isinstance(exc, (openai.NotFoundError, openai.PermissionDeniedError)):
        return True
    if isinstance(exc, openai.BadRequestError):
        message = str(exc).lower()
        return "model" in message and any(hint in message for hint in _MODEL_ERROR_HINTS[1:])
    return False


class OpenAIProvider(AIProvider):
    name = "openai"
    demo = False

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url or None,
            organization=settings.openai_organization,
            project=settings.openai_project,
            timeout=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )
        self._working: dict[str, str] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ plumbing

    def _with_fallback(self, role: str, models: list[str], call: Callable[[str], T]) -> T:
        with self._lock:
            preferred = self._working.get(role)
        order = ([preferred] if preferred else []) + [m for m in models if m != preferred]
        last_error: Exception | None = None
        for model in order:
            try:
                result = call(model)
            except Exception as exc:  # noqa: BLE001 - classify below
                if _is_model_unavailable(exc):
                    log.warning("Model %s unavailable for %s: %s — trying next", model, role, exc)
                    last_error = exc
                    continue
                if isinstance(exc, (openai.APIError, openai.APIConnectionError)):
                    raise AIUnavailableError(f"{role} failed on {model}: {exc}") from exc
                raise
            with self._lock:
                self._working[role] = model
            return result
        raise AIUnavailableError(f"No configured model available for {role}: {last_error}")

    def _parse(self, role: str, models: list[str], effort: str, instructions: str, text: str,
               schema: type[M], max_output_tokens: int) -> M:
        def call(model: str) -> M:
            response = self.client.responses.parse(
                model=model,
                instructions=instructions,
                input=text,
                text_format=schema,
                reasoning={"effort": effort},
                max_output_tokens=max_output_tokens,
                store=False,
            )
            parsed = response.output_parsed
            if parsed is None:
                raise AIUnavailableError(f"{role}: model returned no parsable output (status={response.status})")
            return parsed

        return self._with_fallback(role, models, call)

    def _assessment_llm(self, role: str, instructions: str, text: str, schema: type[M], max_tokens: int = 12000) -> M:
        s = self.settings
        return self._parse(role, s.assessment_models, s.assessment_reasoning_effort, instructions, text, schema, max_tokens)

    def _conversation_llm(self, role: str, instructions: str, text: str, schema: type[M], max_tokens: int = 2000) -> M:
        s = self.settings
        return self._parse(
            role, s.conversation_models, s.conversation_reasoning_effort, instructions, text, schema, max_tokens
        )

    # ------------------------------------------------------------------ audio

    def transcribe(self, audio_path: str, *, language: str, prompt: str | None, hint: AudioHint) -> TranscriptionResult:
        hint_language = transcription_language(language)  # None for code-mixed speech such as Hinglish

        def call(model: str) -> TranscriptionResult:
            with open(audio_path, "rb") as handle:
                kwargs: dict = {"model": model, "file": handle, "response_format": "json"}
                if hint_language:
                    kwargs["language"] = hint_language
                if prompt:
                    kwargs["prompt"] = prompt
                if model in {"gpt-4o-transcribe", "gpt-4o-mini-transcribe", "gpt-4o-mini-transcribe-2025-12-15"}:
                    kwargs["include"] = ["logprobs"]
                result = self.client.audio.transcriptions.create(**kwargs)
            text = getattr(result, "text", "") or ""
            logprobs = [lp.logprob for lp in (getattr(result, "logprobs", None) or []) if lp.logprob is not None]
            avg = sum(logprobs) / len(logprobs) if logprobs else None
            low = sum(1 for lp in logprobs if lp < -1.0) / len(logprobs) if logprobs else None
            return TranscriptionResult(text=text.strip(), avg_logprob=avg, low_confidence_ratio=low, model=model)

        return self._with_fallback("transcribe", self.settings.transcription_models, call)

    def diarize(
        self, audio_path: str, *, language: str, known_speakers: list[KnownSpeaker], hint: AudioHint
    ) -> DiarizationResult:
        hint_language = transcription_language(language) if language else None
        references: list[str] = []
        names: list[str] = []
        for speaker in known_speakers[:4]:
            with open(speaker.wav_path, "rb") as handle:
                references.append("data:audio/wav;base64," + base64.b64encode(handle.read()).decode("ascii"))
            names.append(speaker.name)

        def request(model: str, with_language: bool, with_references: bool):
            with open(audio_path, "rb") as handle:
                kwargs: dict = {
                    "model": model,
                    "file": handle,
                    "response_format": "diarized_json",
                    "chunking_strategy": "auto",
                }
                if with_language and hint_language:
                    kwargs["language"] = hint_language
                if with_references and references:
                    kwargs["known_speaker_names"] = names
                    kwargs["known_speaker_references"] = references
                return self.client.audio.transcriptions.create(**kwargs)

        def call(model: str) -> DiarizationResult:
            # Degrade gracefully if an optional parameter is rejected: first drop the language hint, then the
            # known-speaker references (attribution then falls back to user confirmation).
            used_references = bool(references)
            try:
                result = request(model, True, True)
            except openai.BadRequestError as exc:
                if _is_model_unavailable(exc):
                    raise
                log.warning("Diarization rejected optional params (%s); retrying without language", exc)
                try:
                    result = request(model, False, True)
                except openai.BadRequestError as exc2:
                    if _is_model_unavailable(exc2) or not references:
                        raise
                    log.warning("Diarization rejected speaker references (%s); retrying without them", exc2)
                    used_references = False
                    result = request(model, False, False)
            segments = [
                DiarizedSegment(speaker=str(seg.speaker), start=float(seg.start), end=float(seg.end),
                                text=(seg.text or "").strip())
                for seg in getattr(result, "segments", []) or []
            ]
            duration = float(getattr(result, "duration", 0.0) or (segments[-1].end if segments else 0.0))
            return DiarizationResult(segments=segments, duration=duration, model=model,
                                     used_references=used_references)

        return self._with_fallback("diarize", self.settings.diarization_models, call)

    def synthesize(self, text: str, *, voice: str, instructions: str | None) -> bytes | None:
        if not self.settings.tts_enabled or not text.strip():
            return None

        def call(model: str) -> bytes:
            kwargs: dict = {"model": model, "voice": voice, "input": text[:4000], "response_format": "mp3"}
            if instructions and model != "tts-1" and model != "tts-1-hd":
                kwargs["instructions"] = instructions
            response = self.client.audio.speech.create(**kwargs)
            return response.content

        try:
            return self._with_fallback("tts", self.settings.tts_models, call)
        except AIUnavailableError as exc:
            log.warning("TTS unavailable, app will use on-device speech: %s", exc)
            return None

    # ------------------------------------------------------------------ language

    def partner_reply(self, req: PartnerReplyRequest) -> PartnerReply:
        instructions, text = prompts.partner_reply(req)
        reply = self._conversation_llm("partner_reply", instructions, text, PartnerReply)
        if reply.momentum is not None:
            reply.momentum = max(0.0, min(1.0, reply.momentum)) if not math.isnan(reply.momentum) else None
        return reply

    def group_reply(self, req: GroupReplyRequest) -> GroupReply:
        instructions, text = prompts.group_reply(req)
        return self._conversation_llm("group_reply", instructions, text, GroupReply)

    def assess(self, req: AssessmentRequest) -> AssessmentJudgement:
        instructions, text = prompts.assessment(req)
        return self._assessment_llm("assess", instructions, text, AssessmentJudgement, max_tokens=16000)

    def attempt_feedback(self, req: AttemptRequest) -> AttemptJudgement:
        instructions, text = prompts.attempt_feedback(req)
        return self._assessment_llm("attempt_feedback", instructions, text, AttemptJudgement)

    def spar_report(self, req: SparRequest) -> SparJudgement:
        instructions, text = prompts.spar_report(req)
        return self._assessment_llm("spar_report", instructions, text, SparJudgement)

    def reflection_reply(self, req: ReflectionRequest) -> ReflectionReply:
        instructions, text = prompts.reflection_reply(req)
        return self._conversation_llm("reflection", instructions, text, ReflectionReply)

    def event_prep(self, req: EventPrepRequest) -> EventPrep:
        instructions, text = prompts.event_prep(req)
        return self._conversation_llm("event_prep", instructions, text, EventPrep, max_tokens=3000)

    def weekly(self, req: WeeklyRequest) -> WeeklyJudgement:
        instructions, text = prompts.weekly(req)
        return self._conversation_llm("weekly", instructions, text, WeeklyJudgement)

    def debrief(self, req: DebriefRequest) -> DebriefJudgement:
        instructions, text = prompts.debrief(req)
        return self._assessment_llm("debrief", instructions, text, DebriefJudgement)

    def custom_scenario(self, req: CustomScenarioRequest) -> CustomScenario:
        instructions, text = prompts.custom_scenario(req)
        return self._conversation_llm("custom_scenario", instructions, text, CustomScenario)
