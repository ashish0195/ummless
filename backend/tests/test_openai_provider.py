"""Offline tests for the OpenAI provider's resilience logic (no network: the client is faked)."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import openai
import pytest

from app.ai.llm_schemas import ReflectionReply
from app.ai.openai_provider import OpenAIProvider
from app.ai.types import AudioHint, KnownSpeaker, ReflectionRequest
from app.config import Settings
from app.errors import AIUnavailableError


def _error(cls, status: int, message: str):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return cls(message, response=httpx.Response(status, request=request), body=None)


class FakeResponses:
    def __init__(self, failing: set[str]):
        self.failing = failing
        self.models: list[str] = []
        self.kwargs: dict = {}

    def parse(self, **kwargs):
        self.models.append(kwargs["model"])
        self.kwargs = kwargs
        if kwargs["model"] in self.failing:
            raise _error(openai.NotFoundError, 404, f"The model `{kwargs['model']}` does not exist")
        return SimpleNamespace(output_parsed=ReflectionReply(reply="Nice work."), status="completed")


def _provider(**overrides) -> OpenAIProvider:
    settings = Settings(environment="test", openai_api_key="sk-test", ai_provider="openai", **overrides)
    return OpenAIProvider(settings)


def _reflection_request() -> ReflectionRequest:
    return ReflectionRequest(language="en", mission_title="m", target_behavior="t", real_life_prompt="p", text="x",
                             went="well")


def test_model_fallback_chain_remembers_working_model():
    provider = _provider(conversation_models=["model-a", "model-b", "model-c"])
    fake = FakeResponses(failing={"model-a"})
    provider.client = SimpleNamespace(responses=fake)
    assert provider.reflection_reply(_reflection_request()).reply == "Nice work."
    assert fake.models == ["model-a", "model-b"]
    assert fake.kwargs["store"] is False and fake.kwargs["reasoning"] == {"effort": "low"}
    fake.models.clear()
    provider.reflection_reply(_reflection_request())
    assert fake.models == ["model-b"]  # remembered


def test_all_models_unavailable_raises_ai_unavailable():
    provider = _provider(conversation_models=["model-a"])
    provider.client = SimpleNamespace(responses=FakeResponses(failing={"model-a"}))
    with pytest.raises(AIUnavailableError):
        provider.reflection_reply(_reflection_request())


def test_transient_errors_surface_as_ai_unavailable():
    provider = _provider(conversation_models=["model-a", "model-b"])

    class Boom:
        def parse(self, **kwargs):
            raise _error(openai.InternalServerError, 500, "server error")

    provider.client = SimpleNamespace(responses=Boom())
    with pytest.raises(AIUnavailableError):
        provider.reflection_reply(_reflection_request())


def test_diarize_passes_known_speakers_and_degrades_gracefully(tmp_path):
    provider = _provider()
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFFfake")
    calls: list[dict] = []

    class Transcriptions:
        def create(self, **kwargs):
            calls.append({k: v for k, v in kwargs.items() if k != "file"})
            if "language" in kwargs:
                raise _error(openai.BadRequestError, 400, "Unsupported parameter: language")
            segment = SimpleNamespace(speaker="me", start=0.0, end=1.5, text="Hello there")
            return SimpleNamespace(segments=[segment], duration=1.5)

    provider.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions()))
    result = provider.diarize(str(audio), language="en", known_speakers=[KnownSpeaker("me", str(ref))],
                              hint=AudioHint())
    assert result.segments[0].speaker == "me" and result.used_references is True
    assert calls[0]["response_format"] == "diarized_json" and calls[0]["chunking_strategy"] == "auto"
    assert calls[0]["known_speaker_names"] == ["me"]
    assert calls[0]["known_speaker_references"][0].startswith("data:audio/wav;base64,")
    assert "language" not in calls[1]


def test_transcribe_requests_logprobs_and_computes_confidence(tmp_path):
    provider = _provider()
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    seen: dict = {}

    class Transcriptions:
        def create(self, **kwargs):
            seen.update({k: v for k, v in kwargs.items() if k != "file"})
            logprobs = [SimpleNamespace(logprob=-0.1), SimpleNamespace(logprob=-2.0)]
            return SimpleNamespace(text=" Hello. ", logprobs=logprobs)

    provider.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions()))
    result = provider.transcribe(str(audio), language="en", prompt="Umm", hint=AudioHint())
    assert seen["include"] == ["logprobs"] and seen["model"] == "gpt-4o-transcribe"
    assert result.text == "Hello." and result.avg_logprob == pytest.approx(-1.05)
    assert result.low_confidence_ratio == 0.5
