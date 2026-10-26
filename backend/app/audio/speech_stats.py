"""Descriptive speech statistics. These are observations about a sample, never scores.

Filler and hedge counts are only computed for languages with validated word lists (English for now).
Transcription models tend to drop disfluencies, so filler counts are a lower bound.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from ..domain.evidence import count_words
from ..domain.languages import FILLER_STATS_LANGUAGES
from ..schemas import SpeechPatterns

_EN_FILLER_WORDS = ("um", "umm", "uh", "uhh", "uhm", "erm", "er", "hmm")
_EN_FILLER_PHRASES = ("you know", "i mean")
_LIKE_RE = re.compile(r"(?:(?<=[,.!?]\s)|^)like\b|\blike(?=,)", re.IGNORECASE | re.MULTILINE)
_EN_HEDGES = (
    "i think", "i guess", "maybe", "kind of", "sort of", "probably", "i feel like", "a little bit",
    "somewhat", "perhaps", "i'm not sure", "i suppose", "kinda", "sorta",
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s+")


def filler_counts(text: str, language: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    if language not in FILLER_STATS_LANGUAGES:
        return counts
    lowered = text.lower()
    for word in _EN_FILLER_WORDS:
        n = len(re.findall(rf"\b{word}\b", lowered))
        if n:
            counts[word] += n
    for phrase in _EN_FILLER_PHRASES:
        n = len(re.findall(rf"\b{phrase}\b", lowered))
        if n:
            counts[phrase] += n
    n_like = len(_LIKE_RE.findall(text))
    if n_like:
        counts["like"] += n_like
    return counts


def hedge_count(text: str, language: str) -> int:
    if language not in FILLER_STATS_LANGUAGES:
        return 0
    lowered = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(h)}\b", lowered)) for h in _EN_HEDGES)


def question_count(text: str) -> int:
    return text.count("?") + text.count("？")


def sentence_word_counts(text: str) -> list[int]:
    sentences = [s for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]
    return [count_words(s) for s in sentences if count_words(s) > 0]


def turn_metrics(text: str, duration: float, pauses: list[float], language: str) -> dict:
    words = count_words(text)
    fillers = filler_counts(text, language)
    minutes = max(duration, 1e-6) / 60.0
    return {
        "words": words,
        "duration": round(duration, 2),
        "wpm": round(words / minutes, 1) if duration >= 3 else None,
        "fillers": dict(fillers),
        "filler_count": sum(fillers.values()),
        "hedges": hedge_count(text, language),
        "questions": question_count(text),
        "pauses": pauses,
    }


def aggregate_patterns(
    user_texts: Iterable[tuple[str, float]],
    pauses: list[float],
    language: str,
    talk_share: float | None = None,
) -> SpeechPatterns:
    """`user_texts` is (text, speaking_seconds) for each usable user unit."""
    items = [(t, d) for t, d in user_texts if t.strip()]
    total_seconds = sum(d for _, d in items)
    total_words = sum(count_words(t) for t, _ in items)
    minutes = total_seconds / 60.0
    supported = language in FILLER_STATS_LANGUAGES
    fillers: Counter[str] = Counter()
    hedges = 0
    for text, _ in items:
        fillers.update(filler_counts(text, language))
        hedges += hedge_count(text, language)
    has_rate = minutes >= 0.25
    return SpeechPatterns(
        words_per_minute=round(total_words / minutes, 0) if has_rate else None,
        filler_per_minute=round(sum(fillers.values()) / minutes, 1) if (has_rate and supported) else None,
        top_fillers=[word for word, _ in fillers.most_common(3)] if supported else [],
        hedges_per_minute=round(hedges / minutes, 1) if (has_rate and supported) else None,
        avg_pause_seconds=round(sum(pauses) / len(pauses), 2) if pauses else None,
        longest_turn_seconds=round(max(d for _, d in items), 1) if items else None,
        talk_share=round(talk_share, 2) if talk_share is not None else None,
        user_speech_seconds=round(total_seconds, 1),
        language_supported=supported,
    )


def style_vector(user_texts: list[tuple[str, float]], pauses: list[float]) -> dict[str, float] | None:
    """Measurable habits used for the conversational-twin comparison."""
    total_seconds = sum(d for _, d in user_texts)
    if total_seconds < 30:
        return None
    text = " ".join(t for t, _ in user_texts)
    minutes = total_seconds / 60
    sentences = sentence_word_counts(text)
    return {
        "wpm": count_words(text) / minutes,
        "avg_pause_seconds": (sum(pauses) / len(pauses)) if pauses else 0.6,
        "sentence_words": (sum(sentences) / len(sentences)) if sentences else 12.0,
        "questions_per_min": question_count(text) / minutes,
        "hedges_per_min": hedge_count(text, "en") / minutes,
    }
