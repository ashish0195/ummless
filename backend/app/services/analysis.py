"""Evidence-based analysis shared by AI-roleplay assessments and recordings.

Flow: opportunity stats → evidence caps → model judgement → server-side guards → evidence clips →
partial/complete/none result with the smallest useful follow-up. The guards always win: the model can
lower what we claim, never raise it; no cited moment means no claim; missing evidence is never a low level.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from ..ai.llm_schemas import AssessmentJudgement, DimensionJudgement
from ..ai.types import AssessmentRequest
from ..audio.speech_stats import aggregate_patterns, style_vector
from ..core import AppServices
from ..domain.activities import ACTIVITIES, GAP_ACTIVITY, GAP_TITLES
from ..domain.dimensions import DIMENSION_IDS, DIMENSIONS, level_label
from ..domain.evidence import (
    STRENGTH_ORDER,
    STYLE_MIN_SECONDS,
    STYLE_MIN_SOURCES,
    STYLE_READY_SECONDS,
    STYLE_READY_SOURCES,
    TOO_LITTLE_SPEECH,
    Unit,
    compute_stats,
    evidence_caps,
    min_strength,
)
from ..schemas import (
    AnalysisResult,
    DimensionResult,
    EvidenceMoment,
    NextStep,
    Recovery,
    RecoveryAction,
    RewriteMoment,
    StyleResult,
)
from ..timeutil import iso_required, utcnow
from . import media as media_service

log = logging.getLogger("comlogue.analysis")

STYLE_NOT_READY = "We need more conversation to describe your style."
# The recovery card stays short; the full explanation is the result summary, one tap away in the app.
GAP_MESSAGE = "Some skills need a little more to go on. A few minutes fills the gaps, or keep what you have."


@dataclass
class AnalysisInput:
    user_id: str
    language: str
    source_type: Literal["assessment", "recording"]
    source_id: str
    context_label: str
    context_description: str
    units: list[Unit]
    pauses: list[float] = field(default_factory=list)
    talk_share: float | None = None
    activity_notes: list[str] = field(default_factory=list)
    target_dimensions: list[str] = field(default_factory=list)
    audio_problem: bool = False  # user speech was mostly lost to audio problems
    route: Literal["roleplay", "recording"] = "roleplay"


@dataclass
class AnalysisOutput:
    result: AnalysisResult
    estimates: list[dict]
    style_vector: dict | None


def _join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def next_step_for(dimension: str) -> NextStep:
    activity_id = GAP_ACTIVITY[dimension]
    return NextStep(type="activity", activity_id=activity_id, title=GAP_TITLES[dimension],
                    minutes=ACTIVITIES[activity_id].minutes)


def missing_dimension(dimension: str, reason: str | None, status: str = "not_enough_evidence") -> DimensionResult:
    return DimensionResult(
        dimension=dimension, title=DIMENSIONS[dimension].title, status=status, level=None, level_label=None,
        confidence=None, summary=None, strengths=[], one_change=None, evidence=[],
        missing_reason=reason, next_step=next_step_for(dimension), assessed_at=None, context_label=None,
    )


def _normalize(text: str) -> str:
    return re.sub(r"[^\w\s']", "", text.lower()).strip()


def find_unit(units_by_id: dict[str, Unit], user_units: list[Unit], segment_id: str, quote: str) -> Unit | None:
    unit = units_by_id.get(segment_id.strip("[] "))
    if unit is not None and unit.usable_user:
        return unit
    probe = _normalize(quote).split()[:8]
    if not probe:
        return None
    needle = " ".join(probe)
    for candidate in user_units:
        if needle and needle in _normalize(candidate.text):
            return candidate
    return None


def _verified_quote(unit: Unit, quote: str) -> str:
    """Keep the model's quote only if it really comes from the unit; otherwise use the unit's own words."""
    words = _normalize(quote).split()
    text = _normalize(unit.text)
    if words and sum(1 for w in words if w in text) / len(words) >= 0.6:
        return quote.strip().strip('"')
    first = re.split(r"(?<=[.!?])\s+", unit.text.strip())[0]
    return " ".join(first.split()[:25])


def _quote_window(unit: Unit, quote: str) -> tuple[float | None, float | None]:
    if unit.start is None or unit.end is None:
        return None, None
    span = max(0.0, unit.end - unit.start)
    if span <= 14.0:
        return unit.start, unit.end
    index = _normalize(unit.text).find(_normalize(quote)[:40])
    fraction = index / max(1, len(_normalize(unit.text))) if index >= 0 else 0.0
    start = unit.start + max(0.0, fraction * span - 1.0)
    return round(start, 2), round(min(unit.end, start + 12.0), 2)


def _moment(svc: AppServices, db: Session, user_id: str, unit: Unit, quote: str, note: str | None) -> EvidenceMoment:
    verified = _verified_quote(unit, quote)
    start, end = _quote_window(unit, verified)
    clip_id = media_service.clip(svc, db, user_id=user_id, source_media_id=unit.media_id, start=start, end=end)
    return EvidenceMoment(
        quote=verified,
        note=note,
        source_type=unit.source_type,
        source_id=unit.source_id,
        turn_index=unit.turn_index,
        start_seconds=start,
        end_seconds=end,
        audio_url=media_service.media_ref(clip_id),
    )


def _merge_dimension(svc: AppServices, db: Session, inp: AnalysisInput, judgement: DimensionJudgement | None,
                     cap_strength: str, cap_reason: str | None, needs_opportunity: bool,
                     units_by_id: dict[str, Unit], user_units: list[Unit], now_iso: str) -> tuple[DimensionResult, str]:
    dim = judgement.dimension if judgement else None
    assert dim is not None
    if cap_strength == "none":
        return missing_dimension(dim, cap_reason), "none"
    if judgement is None or not judgement.opportunity_found:
        reason = (judgement.missing_reason if judgement else None) or cap_reason or TOO_LITTLE_SPEECH
        return missing_dimension(dim, reason), "none"
    strength = min_strength(judgement.evidence_strength, cap_strength)  # type: ignore[arg-type]
    level = judgement.level
    if strength == "none" or level is None or not 1 <= level <= 5:
        reason = judgement.missing_reason or cap_reason or TOO_LITTLE_SPEECH
        return missing_dimension(dim, reason), "none"
    moments: list[EvidenceMoment] = []
    for ref in judgement.evidence[:3]:
        unit = find_unit(units_by_id, user_units, ref.segment_id, ref.quote)
        if unit is None:
            continue
        moments.append(_moment(svc, db, inp.user_id, unit, ref.quote, ref.note))
    if not moments:
        # No verifiable moment ⇒ no claim.
        return missing_dimension(dim, "We couldn't link this to a clear moment in the conversation yet."), "none"
    if strength == "limited":
        confidence = "low"
        status = "provisional"
    else:
        confidence = judgement.confidence if judgement.confidence in ("moderate", "high") else "moderate"
        status = "assessed"
    result = DimensionResult(
        dimension=dim, title=DIMENSIONS[dim].title, status=status, level=level, level_label=level_label(level),
        confidence=confidence, summary=judgement.summary, strengths=judgement.strengths[:2],
        one_change=judgement.one_change, evidence=moments, missing_reason=None, next_step=None,
        assessed_at=now_iso, context_label=inp.context_label,
    )
    return result, strength


def _style(judgement: AssessmentJudgement | None, speech_seconds: float, sources: int) -> StyleResult:
    eligible = speech_seconds >= STYLE_MIN_SECONDS and sources >= STYLE_MIN_SOURCES
    if not eligible or judgement is None or not judgement.style.eligible or not judgement.style.archetype:
        return StyleResult(status="not_ready", archetype=None, description=None, traits=[], message=STYLE_NOT_READY)
    ready = speech_seconds >= STYLE_READY_SECONDS and sources >= STYLE_READY_SOURCES
    return StyleResult(
        status="ready" if ready else "provisional",
        archetype=judgement.style.archetype,
        description=judgement.style.description,
        traits=judgement.style.traits[:3],
        message=None if ready else "An early read from a few conversations — it may change as we hear more.",
    )


def _recovery_none(inp: AnalysisInput) -> Recovery:
    if inp.audio_problem:
        actions = [
            RecoveryAction(type="retry" if inp.route == "roleplay" else "record_again",
                           title="Try again somewhere quieter", activity_id=None),
            RecoveryAction(type="upload_another", title="Upload another conversation", activity_id=None),
            RecoveryAction(type="ai_practice", title="Practice with AI instead", activity_id=None),
            RecoveryAction(type="starter_course", title="Start a course based on your goal", activity_id=None),
        ]
        return Recovery(problem="audio_unclear", title="We couldn't hear enough of your speech clearly",
                        message="This was about the audio, not how you communicate. Nothing was scored.",
                        actions=actions, extra_minutes=None)
    actions = [
        RecoveryAction(type="ai_practice" if inp.route == "recording" else "retry",
                       title="Have a short AI conversation" if inp.route == "recording" else "Try again",
                       activity_id=None),
        RecoveryAction(type="upload_another", title="Upload another conversation", activity_id=None),
        RecoveryAction(type="starter_course", title="Start a course based on your goal", activity_id=None),
    ]
    return Recovery(problem="no_dimensions",
                    title="We don't have enough information for your communication profile yet.",
                    message="We need a bit more of you talking with someone. You can also start a course based on "
                    "your goal now — it isn't personalized yet, and it will adapt once we have evidence.",
                    actions=actions, extra_minutes=None)


def partial_message(assessed: list[str], missing: list[str]) -> str:
    assessed_titles = [DIMENSIONS[d].title.lower() for d in assessed]
    clauses: list[str] = []
    if "listening" in missing:
        clauses.append("there wasn't enough clear back-and-forth to assess listening")
    others = [DIMENSIONS[d].title.lower() for d in missing if d != "listening"]
    if others:
        clauses.append(f"we need more evidence for {_join(others)}")
    first_gap = "listening" if "listening" in missing else missing[0]
    return (
        f"We could assess your {_join(assessed_titles)}, but {' — and '.join(clauses)}. "
        f"{GAP_TITLES[first_gap]}, upload another conversation, or continue with your current results."
    )


def _gap_priority(missing: list[str]) -> list[str]:
    order = ("listening", "persuasion", "storytelling", "warmth", "structure", "clarity", "concision")
    return sorted(missing, key=order.index)


def run_analysis(svc: AppServices, db: Session, inp: AnalysisInput) -> AnalysisOutput:
    now = utcnow()
    now_iso = iso_required(now)
    stats = compute_stats(inp.units)
    caps = evidence_caps(stats)
    user_units = [u for u in inp.units if u.usable_user]
    sources = len(stats.activities) if inp.route == "roleplay" else len(stats.sources)
    style_eligible = stats.user_speech_seconds >= STYLE_MIN_SECONDS and sources >= STYLE_MIN_SOURCES
    patterns = aggregate_patterns(((u.text, u.duration) for u in user_units), inp.pauses, inp.language,
                                  inp.talk_share) if user_units else None
    vector = style_vector([(u.text, u.duration) for u in user_units], inp.pauses) if user_units else None

    if all(cap.max_strength == "none" for cap in caps.values()):
        reason = TOO_LITTLE_SPEECH
        result = AnalysisResult(
            status="none",
            headline="We don't have enough information for your communication profile yet.",
            summary="We didn't get enough clear speech from you to assess any dimension. Missing evidence is not a "
            "low score — nothing was scored.",
            dimensions=[missing_dimension(d, reason) for d in DIMENSION_IDS],
            speech_patterns=patterns if patterns and patterns.user_speech_seconds > 0 else None,
            first_win=None,
            style=StyleResult(status="not_ready", archetype=None, description=None, traits=[],
                              message=STYLE_NOT_READY),
            recovery=_recovery_none(inp),
            context_label=inp.context_label,
            created_at=now_iso,
        )
        return AnalysisOutput(result=result, estimates=[], style_vector=None)

    judgement = svc.ai.assess(
        AssessmentRequest(
            language=inp.language,
            context_description=inp.context_description,
            units=inp.units,
            stats=stats,
            caps=caps,
            style_eligible=style_eligible,
            target_dimensions=inp.target_dimensions,
            activity_notes=inp.activity_notes,
        )
    )
    by_dim = {j.dimension: j for j in judgement.dimensions}
    units_by_id = {u.uid: u for u in inp.units}

    dimensions: list[DimensionResult] = []
    strengths: dict[str, str] = {}
    for dim in DIMENSION_IDS:
        cap = caps[dim]
        judged = by_dim.get(dim)
        if judged is None:
            dimensions.append(missing_dimension(dim, cap.reason or TOO_LITTLE_SPEECH))
            strengths[dim] = "none"
            continue
        merged, strength = _merge_dimension(svc, db, inp, judged, cap.max_strength, cap.reason,
                                            cap.needs_model_opportunity, units_by_id, user_units, now_iso)
        dimensions.append(merged)
        strengths[dim] = strength

    assessed = [d.dimension for d in dimensions if d.status in ("assessed", "provisional")]
    missing = [d.dimension for d in dimensions if d.status not in ("assessed", "provisional")]

    first_win = None
    if judgement.first_win and assessed:
        unit = find_unit(units_by_id, user_units, judgement.first_win.segment_id, judgement.first_win.you_said)
        if unit is not None:
            quote = _verified_quote(unit, judgement.first_win.you_said)
            start, end = _quote_window(unit, quote)
            clip_id = media_service.clip(svc, db, user_id=inp.user_id, source_media_id=unit.media_id,
                                         start=start, end=end)
            dim = judgement.first_win.dimension if judgement.first_win.dimension in assessed else None
            first_win = RewriteMoment(
                dimension=dim, you_said=quote, try_instead=judgement.first_win.try_instead,
                why=judgement.first_win.why, source_type=unit.source_type, source_id=unit.source_id,
                turn_index=unit.turn_index, start_seconds=start, end_seconds=end,
                audio_url=media_service.media_ref(clip_id),
            )

    style = _style(judgement, stats.user_speech_seconds, sources)

    if not assessed:
        status: Literal["complete", "partial", "none"] = "none"
        headline = "We don't have enough information for your communication profile yet."
        summary = "We couldn't link any dimension to clear moments in this sample. Nothing was scored."
        recovery: Recovery | None = _recovery_none(inp)
    elif missing:
        status = "partial"
        headline = judgement.headline or "Your partial communication profile"
        summary = partial_message(assessed, missing)
        gaps = _gap_priority(missing)
        seen: set[str] = set()
        actions: list[RecoveryAction] = []
        extra = 0
        for dim in gaps:
            activity = GAP_ACTIVITY[dim]
            if activity in seen or len(actions) >= 2:
                continue
            seen.add(activity)
            extra += ACTIVITIES[activity].minutes
            actions.append(RecoveryAction(type="gap_fill", title=GAP_TITLES[dim], activity_id=activity))
        actions.append(RecoveryAction(type="upload_another", title="Upload another conversation", activity_id=None))
        actions.append(RecoveryAction(type="continue", title="Continue with my current results", activity_id=None))
        recovery = Recovery(problem="too_little_evidence", title="Fill the gaps when you're ready",
                            message=GAP_MESSAGE, actions=actions, extra_minutes=extra or None)
    else:
        status = "complete"
        headline = judgement.headline or "Your initial communication profile"
        summary = judgement.summary
        recovery = None

    result = AnalysisResult(
        status=status,
        headline=headline,
        summary=summary,
        dimensions=dimensions,
        speech_patterns=patterns,
        first_win=first_win,
        style=style,
        recovery=recovery,
        context_label=inp.context_label,
        created_at=now_iso,
    )
    estimates = [
        {
            "dimension": d.dimension,
            "status": d.status,
            "level": d.level,
            "confidence": d.confidence,
            "strength": strengths[d.dimension],
            "payload": d.model_dump(mode="json"),
        }
        for d in dimensions
        if d.status in ("assessed", "provisional") and d.level is not None
    ]
    # Never let a weaker sample overwrite a target-less dimension in gap-fill mode: keep only targets + new ones.
    if inp.target_dimensions:
        estimates = [e for e in estimates if e["dimension"] in inp.target_dimensions or
                     STRENGTH_ORDER.get(e["strength"], 0) >= STRENGTH_ORDER["sufficient"]]
    return AnalysisOutput(result=result, estimates=estimates, style_vector=vector)
