"""Shapes for market-aware content. Data modules in this package only build these (or existing domain types)."""

from __future__ import annotations

from dataclasses import dataclass

MARKETS = ("us", "in", "global")
ALL_MARKETS: tuple[str, ...] = MARKETS
DAILY_KINDS = ("explain", "story", "persuade", "answer", "opinion", "introduce", "summarize", "respond")
CONTEXTS = ("work", "career", "social", "life")
PANEL_KINDS = ("group_discussion", "panel_interview")


@dataclass(frozen=True)
class DailyPromptDef:
    """One 30–90 second speaking rep. The coach reads `prompt` aloud; feedback checks `target_behavior`."""

    id: str  # stable slug, e.g. "explain.job_to_kid" — never reuse an id for different content
    title: str  # ≤ 48 chars; shown in reminders and widgets ("Explain your job to a 10-year-old")
    prompt: str  # what the coach says, 1–3 short spoken sentences, second person
    kind: str  # one of DAILY_KINDS
    dimension: str  # DimensionId this rep trains
    target_behavior: str  # ONE observable behaviour the feedback checks
    tips: tuple[str, ...]  # exactly 2 short tips
    suggested_seconds: int  # 30–90; a suggestion, recording never stops on its own
    context: str = "work"  # one of CONTEXTS; weekends favour social/life
    markets: tuple[str, ...] = ALL_MARKETS
    tracks: tuple[str, ...] = ()  # goal tracks it suits; empty = any
    level: int = 1  # 1 easy, 2 standard, 3 stretch
    months: tuple[int, ...] = ()  # seasonal window (1–12); empty = any time of year
    example: str | None = None  # optional model answer, ≤ 60 words


@dataclass(frozen=True)
class ParticipantDef:
    id: str  # unique within its panel, e.g. "mod", "p1"
    name: str
    role: str  # shown under the name: "Moderator", "Engineering manager"
    voice: str  # gpt-4o-mini-tts voice: alloy, ash, ballad, cedar, coral, echo, fable, marin, nova, onyx, sage, shimmer, verse
    symbol: str  # SF Symbol
    color_hex: str
    stance: str  # who they are, what they believe, how they behave in this discussion (for the model)
    tts_instructions: str  # delivery notes, e.g. "Neutral Indian English accent, measured pace"


@dataclass(frozen=True)
class PanelDef:
    """A multi-party conversation: a campus-placement group discussion (GD) or a panel interview."""

    id: str
    kind: str  # one of PANEL_KINDS
    title: str
    scenario: str  # one line for cards
    description: str  # 1–2 sentences: the situation and what good looks like
    topic: str | None  # GD topic, or the role being interviewed for
    user_role: str  # "Candidate", "Participant"
    moderator: ParticipantDef
    participants: tuple[ParticipantDef, ...]  # 2–3, excluding the moderator
    opening: str  # the moderator's opening line (turn 0)
    pre_user_lines: tuple[tuple[str, str], ...]  # (participant id, line) spoken before the user's first turn; 0–2
    evaluation_focus: tuple[str, ...]  # what the report looks for, 3–5 items
    max_user_turns: int  # 3–6
    minutes: int
    markets: tuple[str, ...]
    is_free: bool
    symbol: str
    color_hex: str
    default_difficulty: str = "real"  # kind | real | brutal


@dataclass(frozen=True)
class EventKindDef:
    id: str  # EventKind
    title: str
    symbol: str
    markets: tuple[str, ...]
    prep_hint: str  # guidance for the model that builds 3 prep items for this kind of event
