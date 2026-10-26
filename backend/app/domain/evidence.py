"""Deterministic evidence rules. These guard every AI judgement.

The model may *lower* what we claim, never raise it past these caps: if a sample contains no real
opportunity for a dimension, or too little attributed user speech, the dimension is
"Not enough evidence yet" — regardless of what the model says. Missing evidence is never a low level.

All thresholds below are starting points: **pilot calibration required** (noise, overlap, short turns,
different microphones, languages and accents). Total duration alone is never a pass criterion.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

Strength = Literal["none", "limited", "sufficient"]
STRENGTH_ORDER: dict[str, int] = {"none": 0, "limited": 1, "sufficient": 2}

# --- thresholds (pilot calibration required) ---
MIN_USER_SPEECH_SECONDS = 20.0  # below this, nothing is assessable
MIN_TURN_WORDS = 5  # a user reply shorter than this doesn't count as a turn
EXTENDED_TURN_WORDS = 60
EXTENDED_TURN_SECONDS = 25.0
NARRATIVE_TURN_WORDS = 70
NARRATIVE_TURN_SECONDS = 30.0
SUBSTANTIVE_OTHER_WORDS = 12  # another speaker's turn worth "listening" to
EXCHANGE_OTHER_WORDS = 8
STYLE_MIN_SECONDS = 120.0  # style description needs ≥ 2 min of attributed speech …
STYLE_MIN_SOURCES = 2  # … from ≥ 2 activities or recordings
STYLE_READY_SECONDS = 300.0
STYLE_READY_SOURCES = 3
TWIN_MIN_SECONDS = 120.0

_WORD_RE = re.compile(r"[\w']+", re.UNICODE)
_CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿가-힯]")


def count_words(text: str) -> int:
    """Word count that degrades gracefully for languages without spaces (CJK: ~1.5 chars per word)."""
    cjk = len(_CJK_RE.findall(text))
    if cjk > len(text) * 0.3:
        return max(1, int(cjk / 1.5))
    return len(_WORD_RE.findall(text))


@dataclass
class Unit:
    """One stretch of speech that can be cited as evidence (a turn, or a diarized segment)."""

    uid: str
    role: Literal["user", "partner", "other"]
    speaker_name: str
    text: str
    source_type: Literal["conversation", "recording"]
    source_id: str
    turn_index: int | None = None
    start: float | None = None  # seconds within `media_id`
    end: float | None = None
    media_id: str | None = None
    activity_id: str | None = None
    context: str | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    duration: float = 0.0
    words: int = field(init=False)

    def __post_init__(self) -> None:
        self.words = count_words(self.text)
        if not self.duration and self.start is not None and self.end is not None:
            self.duration = max(0.0, self.end - self.start)

    @property
    def usable_user(self) -> bool:
        return self.role == "user" and not self.excluded and self.words > 0


@dataclass
class OpportunityStats:
    user_speech_seconds: float
    user_words: int
    user_turns: int
    extended_turns: int
    narrative_turns: int
    exchanges: int
    substantive_exchanges: int
    activities: set[str]
    sources: set[str]
    excluded_user_units: int
    excluded_reasons: Counter[str]
    activity_exchanges: Counter[str]


def compute_stats(units: list[Unit]) -> OpportunityStats:
    user_units = [u for u in units if u.usable_user]
    excluded = [u for u in units if u.role == "user" and u.excluded]
    exchanges = 0
    substantive = 0
    activity_exchanges: Counter[str] = Counter()
    # An exchange is another speaker saying something followed by a usable user reply in the same source.
    for prev, cur in zip(units, units[1:], strict=False):
        if prev.source_id != cur.source_id:
            continue
        if prev.role != "user" and not prev.excluded and cur.usable_user and cur.words >= MIN_TURN_WORDS:
            if prev.words >= EXCHANGE_OTHER_WORDS:
                exchanges += 1
                activity_exchanges[cur.activity_id or cur.source_id] += 1
            if prev.words >= SUBSTANTIVE_OTHER_WORDS:
                substantive += 1
    return OpportunityStats(
        user_speech_seconds=round(sum(u.duration for u in user_units), 2),
        user_words=sum(u.words for u in user_units),
        user_turns=sum(1 for u in user_units if u.words >= MIN_TURN_WORDS),
        extended_turns=sum(
            1 for u in user_units if u.words >= EXTENDED_TURN_WORDS or u.duration >= EXTENDED_TURN_SECONDS
        ),
        narrative_turns=sum(
            1 for u in user_units if u.words >= NARRATIVE_TURN_WORDS or u.duration >= NARRATIVE_TURN_SECONDS
        ),
        exchanges=exchanges,
        substantive_exchanges=substantive,
        activities={u.activity_id for u in user_units if u.activity_id},
        sources={u.source_id for u in user_units},
        excluded_user_units=len(excluded),
        excluded_reasons=Counter(u.exclusion_reason or "excluded" for u in excluded),
        activity_exchanges=activity_exchanges,
    )


@dataclass(frozen=True)
class Cap:
    max_strength: Strength
    reason: str | None  # shown as missing_reason when the cap is "none"
    needs_model_opportunity: bool = False  # the model must confirm an opportunity existed


MISSING_REASONS: dict[str, str] = {
    "clarity": "We need a longer explanation from you to see how clearly you make a point.",
    "structure": "We need at least one longer answer to see how you organize your ideas.",
    "concision": "We need a few more answers to questions to see how directly you get to the point.",
    "listening": "There wasn't enough clear back-and-forth to assess listening.",
    "warmth": "We need more back-and-forth with another person to see how you connect.",
    "persuasion": "There wasn't a moment where you made a case or responded to an objection.",
    "storytelling": "We didn't hear a story in this sample.",
}

TOO_LITTLE_SPEECH = "We didn't have enough clear speech from you to assess this yet."


def evidence_caps(stats: OpportunityStats) -> dict[str, Cap]:
    """Maximum evidence strength each dimension can reach given the sample's structure."""
    if stats.user_speech_seconds < MIN_USER_SPEECH_SECONDS or stats.user_turns == 0:
        return {dim: Cap("none", TOO_LITTLE_SPEECH) for dim in MISSING_REASONS}

    caps: dict[str, Cap] = {}
    ext, turns, exch, subst = stats.extended_turns, stats.user_turns, stats.exchanges, stats.substantive_exchanges

    if ext >= 2 or (ext >= 1 and turns >= 4):
        caps["clarity"] = Cap("sufficient", None)
    elif ext >= 1 or (turns >= 3 and stats.user_speech_seconds >= 45):
        caps["clarity"] = Cap("limited", None)
    else:
        caps["clarity"] = Cap("none", MISSING_REASONS["clarity"])

    if ext >= 2:
        caps["structure"] = Cap("sufficient", None)
    elif ext >= 1:
        caps["structure"] = Cap("limited", None)
    else:
        caps["structure"] = Cap("none", MISSING_REASONS["structure"])

    if exch >= 3 and turns >= 4:
        caps["concision"] = Cap("sufficient", None)
    elif exch >= 2 or (ext >= 1 and turns >= 2):
        caps["concision"] = Cap("limited", None)
    else:
        caps["concision"] = Cap("none", MISSING_REASONS["concision"])

    if subst >= 3:
        caps["listening"] = Cap("sufficient", None)
    elif subst >= 2:
        caps["listening"] = Cap("limited", None)
    else:
        caps["listening"] = Cap("none", MISSING_REASONS["listening"])

    if exch >= 3:
        caps["warmth"] = Cap("sufficient", None)
    elif exch >= 2:
        caps["warmth"] = Cap("limited", None)
    else:
        caps["warmth"] = Cap("none", MISSING_REASONS["warmth"])

    # Persuasion and storytelling need the opportunity to exist; the model must confirm it.
    case_exchanges = stats.activity_exchanges.get("make_a_case", 0)
    if "make_a_case" in stats.activities and case_exchanges >= 1:
        caps["persuasion"] = Cap("sufficient", None, needs_model_opportunity=True)
    elif exch >= 1:
        caps["persuasion"] = Cap("limited", None, needs_model_opportunity=True)
    else:
        caps["persuasion"] = Cap("none", MISSING_REASONS["persuasion"])

    if "tell_a_story" in stats.activities and stats.narrative_turns >= 1:
        caps["storytelling"] = Cap("sufficient", None, needs_model_opportunity=True)
    elif stats.narrative_turns >= 1:
        caps["storytelling"] = Cap("limited", None, needs_model_opportunity=True)
    else:
        caps["storytelling"] = Cap("none", MISSING_REASONS["storytelling"])

    return caps


def min_strength(a: Strength, b: Strength) -> Strength:
    return a if STRENGTH_ORDER[a] <= STRENGTH_ORDER[b] else b
