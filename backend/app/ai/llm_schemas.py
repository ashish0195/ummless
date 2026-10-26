"""Structured-output schemas for the language model.

Strict-schema safe: no dicts, no defaults the model can skip (every field required, nullable where it
may be absent), Literal enums, nested models only. The mock provider returns the same types.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Dim = Literal["clarity", "structure", "listening", "warmth", "persuasion", "concision", "storytelling"]
StrengthLit = Literal["none", "limited", "sufficient"]
ConfidenceLit = Literal["low", "moderate", "high"]
ArchetypeLit = Literal[
    "The Explainer", "The Connector", "The Storyteller", "The Strategist", "The Diplomat", "The Spark",
    "The Straight Shooter",
]


class PartnerReply(BaseModel):
    reply: str = Field(description="What the partner says next, spoken aloud. 1–2 short sentences.")
    end_conversation: bool = Field(description="True only if this line closes the conversation.")
    coach_whisper: str | None = Field(
        description="Spar only: one short, specific coaching hint about the user's LAST turn (max 18 words), "
        "or null."
    )
    momentum: float | None = Field(
        description="Spar only: 0–1, how persuaded/comfortable the partner currently feels. Null otherwise."
    )
    outcome_label: str | None = Field(
        description="Spar only, when the scenario resolves: e.g. 'Budget approved'. Null otherwise."
    )


class EvidenceRef(BaseModel):
    segment_id: str = Field(description="ID of a USER segment, exactly as shown, e.g. 'A2.T3' or 'R.S14'.")
    quote: str = Field(description="Verbatim excerpt from that segment, at most 25 words.")
    note: str | None = Field(description="What this moment shows, in under 15 words.")


class DimensionJudgement(BaseModel):
    dimension: Dim
    opportunity_found: bool = Field(description="Did the sample contain a real opportunity to show this?")
    opportunity_note: str = Field(description="Which moment created the opportunity, or what was missing.")
    evidence_strength: StrengthLit
    level: int | None = Field(description="1–5 per the rubric, ONLY when evidence is limited or sufficient.")
    confidence: ConfidenceLit | None
    summary: str | None = Field(description="1–2 sentences scoped to this sample. Null if no evidence.")
    strengths: list[str] = Field(description="0–2 specific things that worked, scoped to this sample.")
    one_change: str | None = Field(description="One concrete, doable change. Null if no evidence.")
    evidence: list[EvidenceRef] = Field(description="1–3 moments for assessed dimensions; empty otherwise.")
    missing_reason: str | None = Field(description="When evidence is none: what was missing, kindly worded.")


class Rewrite(BaseModel):
    segment_id: str
    dimension: Dim | None
    you_said: str = Field(description="Verbatim excerpt of what the user said (≤ 30 words).")
    try_instead: str = Field(description="A better version in the user's own voice (≤ 30 words).")
    why: str = Field(description="Why it's better, one sentence.")


class StyleJudgement(BaseModel):
    eligible: bool = Field(description="False if there isn't enough varied speech to describe a style.")
    archetype: ArchetypeLit | None
    description: str | None = Field(description="2 sentences, observational, scoped to these conversations.")
    traits: list[str] = Field(description="2–3 short observable traits.")


class AssessmentJudgement(BaseModel):
    dimensions: list[DimensionJudgement]
    headline: str = Field(description="Short, warm, specific headline (≤ 10 words). No scores.")
    summary: str = Field(description="2–3 sentences: what stood out in this sample, scoped to it.")
    first_win: Rewrite | None = Field(description="The single most useful 'rewrite this moment', or null.")
    style: StyleJudgement


class AttemptJudgement(BaseModel):
    assessable: Literal["yes", "partly", "no"]
    target_met: Literal["yes", "partly", "no", "unclear"]
    headline: str = Field(description="One encouraging, specific sentence about the attempt.")
    where_segment_id: str | None = Field(description="USER segment where the target behavior appeared (or best try).")
    where_quote: str | None
    where_note: str | None
    what_worked: list[str] = Field(description="0–2 specific things that worked.")
    one_change: str | None
    missing_evidence: str | None = Field(description="If partly/not assessable: what we couldn't see.")
    comparison_summary: str | None = Field(
        description="If a previous attempt is given: how this attempt compares against the SAME target."
    )
    comparison_changes: list[str]


class MomentumNote(BaseModel):
    turn_index: int
    note: str


class SparObservation(BaseModel):
    dimension: Dim
    note: str
    segment_id: str


class SparJudgement(BaseModel):
    outcome_label: str = Field(description="2–4 words, e.g. 'Budget approved' or 'Not convinced yet'.")
    outcome_detail: str = Field(description="One sentence on what moved (or didn't move) the partner.")
    momentum_notes: list[MomentumNote]
    moments: list[Rewrite] = Field(description="1–3 'rewrite this moment' suggestions.")
    observations: list[SparObservation] = Field(
        description="Only for dimensions this spar gave a real opportunity to show; cite the segment."
    )
    next_step: str


class ReflectionReply(BaseModel):
    reply: str = Field(description="2–3 sentences: acknowledge, one insight, one tiny next step.")


class PrepItemJudgement(BaseModel):
    title: str
    scenario: str = Field(description="Second-person scenario description for a rehearsal (1–2 sentences).")
    partner_role: str
    difficulty: Literal["kind", "real", "brutal"]


class EventPrep(BaseModel):
    items: list[PrepItemJudgement] = Field(description="Exactly 3 rehearsal scenarios, easiest first.")


class WeeklyJudgement(BaseModel):
    highlights: list[str] = Field(description="2–3 specific highlights from the facts given.")
    message: str = Field(description="2 sentences, warm and honest, no guilt about missed days.")


class DebriefJudgement(BaseModel):
    best_moment_segment_id: str | None
    best_moment_note: str | None
    decisions: list[str]
    follow_up_summary: str | None = Field(description="A short follow-up message the user could send.")
    one_thing_to_try: str | None


class CustomScenario(BaseModel):
    partner_name: str
    partner_role: str
    opening_line: str
    context: str = Field(description="One sentence framing shown to the user (second person).")
    character: str = Field(description="Who the partner is and what they care about.")
    win_condition: str
