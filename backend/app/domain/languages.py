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
    ("hinglish", "Hinglish (Hindi + English)"),
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
    "hinglish": "Hinglish",
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


# Codes the transcription API accepts as a language hint (ISO-639-1). "hinglish" is code-mixed speech: we send no
# language hint and describe the mix in the transcription prompt instead.
def transcription_language(code: str) -> str | None:
    return None if code == "hinglish" else code


def language_instruction(code: str) -> str:
    """How to write for this language in prompts."""
    if code == "hinglish":
        return ("Hinglish: natural Hindi–English code-mixing as people speak it in Indian cities, written in Latin "
                "script (e.g. \"Theek hai, but let's fix the export first.\")")
    return language_name(code)
