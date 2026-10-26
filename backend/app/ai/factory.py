"""Choose the AI provider from settings."""

from __future__ import annotations

import logging

from ..config import Settings
from .mock_provider import MockProvider
from .provider import AIProvider

log = logging.getLogger("comlogue.ai")


def build_provider(settings: Settings) -> AIProvider:
    if settings.resolved_ai_provider == "openai":
        from .openai_provider import OpenAIProvider

        log.info("AI provider: OpenAI (assessment=%s, conversation=%s)", settings.assessment_models,
                 settings.conversation_models)
        return OpenAIProvider(settings)
    log.warning("AI provider: offline DEMO mode (set OPENAI_API_KEY to use real AI). Results are simulated.")
    return MockProvider()
