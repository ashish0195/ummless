"""Conversation/feedback languages. UI localization is separate (handled in the app)."""

from __future__ import annotations

LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("pt", "Português"),
    ("it", "Italiano"),
    ("nl", "Nederlands"),
    ("hi", "हिन्दी"),
    ("ja", "日本語"),
    ("ko", "한국어"),
    ("zh", "中文"),
    ("ar", "العربية"),
]

LANGUAGE_CODES = {code for code, _ in LANGUAGES}
LANGUAGE_NAMES_EN = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
}

# Filler/hedge statistics are only computed where we have validated word lists.
FILLER_STATS_LANGUAGES = {"en"}


def normalize_language(code: str | None) -> str:
    if not code:
        return "en"
    short = code.split("-")[0].split("_")[0].lower()
    return short if short in LANGUAGE_CODES else "en"


def language_name(code: str) -> str:
    return LANGUAGE_NAMES_EN.get(code, "English")
