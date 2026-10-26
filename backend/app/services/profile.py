"""Communication profile: the latest *valid* estimate per dimension, with history and sources.

Rules: sufficient evidence beats limited evidence; among equals the newest wins. Unusable new audio never
replaces an older valid estimate (it never produces an estimate in the first place). No overall score.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.archetypes import (
    TWIN_ASPECTS,
    TWIN_DISCLAIMER,
    TWIN_REFERENCES,
    format_aspect,
)
from ..domain.dimensions import DIMENSION_IDS, DIMENSIONS, level_label
from ..domain.evidence import TWIN_MIN_SECONDS
from ..models import Assessment, DimensionEstimate, Recording, User
from ..schemas import (
    AnalysisResult,
    DimensionResult,
    HistoryEntry,
    NextStep,
    Profile,
    ProfileSource,
    RewriteMoment,
    SpeechPatterns,
    StyleResult,
    TwinMatch,
    TwinResult,
)
from ..timeutil import as_utc, iso, iso_required
from . import media as media_service
from .analysis import STYLE_NOT_READY, missing_dimension, next_step_for

TWIN_NOT_READY = "Your conversational twin is not ready yet."
NEVER_HEARD = "We haven't heard a conversation that shows this yet."


def current_estimates(db: Session, user: User) -> dict[str, DimensionEstimate]:
    rows = list(db.scalars(
        select(DimensionEstimate).where(DimensionEstimate.user_id == user.id)
        .order_by(DimensionEstimate.assessed_at.desc(), DimensionEstimate.id.desc())
    ))
    chosen: dict[str, DimensionEstimate] = {}
    for row in rows:
        best = chosen.get(row.dimension)
        if best is None or (best.status == "provisional" and row.status == "assessed"):
            chosen[row.dimension] = row
    return chosen


def _results(db: Session, user: User) -> list[tuple[str, str, str, object, dict, dict | None]]:
    """(type, id, title, created_at, result, style_vector) newest first, for analyses that produced a result."""
    items = []
    for a in db.scalars(select(Assessment).where(Assessment.user_id == user.id, Assessment.result.is_not(None))):
        title = "AI conversation" if a.purpose == "baseline" else "Follow-up conversation"
        items.append(("assessment", a.id, title, a.completed_at or a.created_at, a.result, a.style_vector, a.status))
    for r in db.scalars(select(Recording).where(Recording.user_id == user.id)):
        items.append(("recording", r.id, r.title, r.completed_at or r.created_at, r.result, r.style_vector, r.status))
    items.sort(key=lambda item: as_utc(item[3]), reverse=True)
    return items  # type: ignore[return-value]


def _twin(vectors: list[dict], speech_seconds: float) -> TwinResult:
    next_step = NextStep(type="activity", activity_id="tell_a_story", title="Tell a short story", minutes=3)
    if speech_seconds < TWIN_MIN_SECONDS or not vectors:
        return TwinResult(status="not_ready", message=TWIN_NOT_READY, disclaimer=TWIN_DISCLAIMER,
                          next_step=next_step, matches=[])
    averaged = {key: sum(v[key] for v in vectors) / len(vectors) for key in vectors[0]}
    matches: list[TwinMatch] = []
    for aspect, (title, attribute, scale) in TWIN_ASPECTS.items():
        value = averaged.get(attribute)
        if value is None:
            continue
        best = max(TWIN_REFERENCES, key=lambda ref: -abs(getattr(ref, attribute) - value))
        closeness = max(0.0, 1.0 - abs(getattr(best, attribute) - value) / scale)
        matches.append(TwinMatch(
            aspect=aspect, aspect_title=title, reference_name=best.name, reference_blurb=best.blurb,
            closeness=round(closeness, 2), your_value=format_aspect(aspect, value),
            reference_value=format_aspect(aspect, getattr(best, attribute)),
        ))
    matches.sort(key=lambda m: -m.closeness)
    return TwinResult(status="ready", message="Per-aspect likeness, from your sampled conversations.",
                      disclaimer=TWIN_DISCLAIMER, next_step=None, matches=matches[:3])


def build(svc: AppServices, db: Session, user: User) -> Profile:
    chosen = current_estimates(db, user)
    results = _results(db, user)
    latest_missing: dict[str, DimensionResult] = {}
    for _, _, _, _, result, _, _ in results:
        if not result:
            continue
        for dim in result.get("dimensions", []):
            if dim["dimension"] not in latest_missing and dim["status"] == "not_enough_evidence":
                latest_missing[dim["dimension"]] = DimensionResult.model_validate(dim)

    dimensions: list[DimensionResult] = []
    for dim in DIMENSION_IDS:
        row = chosen.get(dim)
        if row is not None:
            payload = media_service.resolve_media(svc, row.payload)
            dimensions.append(DimensionResult.model_validate(payload))
        elif dim in latest_missing:
            dimensions.append(latest_missing[dim])
        else:
            dimensions.append(missing_dimension(dim, NEVER_HEARD, status="not_assessed"))

    history = [
        HistoryEntry(dimension=row.dimension, status=row.status, level=row.level, level_label=level_label(row.level),
                     assessed_at=iso_required(row.assessed_at), context_label=row.context_label,
                     source_type=row.source_type, source_id=row.source_id)
        for row in db.scalars(select(DimensionEstimate).where(DimensionEstimate.user_id == user.id)
                              .order_by(DimensionEstimate.assessed_at.desc()))
    ]
    sources = [ProfileSource(type=kind, id=id_, title=title, created_at=iso_required(created), status=status)
               for kind, id_, title, created, _, _, status in results]

    patterns: SpeechPatterns | None = None
    style = StyleResult(status="not_ready", archetype=None, description=None, traits=[], message=STYLE_NOT_READY)
    first_win: RewriteMoment | None = None
    vectors: list[dict] = []
    speech_seconds = 0.0
    for _, _, _, _, result, vector, _ in results:
        if not result:
            continue
        parsed = AnalysisResult.model_validate(media_service.resolve_media(svc, result))
        if parsed.speech_patterns and patterns is None:
            patterns = parsed.speech_patterns
        if parsed.style.status != "not_ready" and style.status == "not_ready":
            style = parsed.style
        if parsed.first_win and first_win is None:
            first_win = parsed.first_win
        if parsed.speech_patterns:
            speech_seconds += parsed.speech_patterns.user_speech_seconds
        if vector and len(vectors) < 5:
            vectors.append(vector)

    assessed = [d for d in dimensions if d.status in ("assessed", "provisional")]
    if len(assessed) == len(DIMENSION_IDS):
        basis, headline = "assessment", "Your communication profile"
        summary = "Every dimension below is backed by moments from your conversations."
    elif assessed:
        basis, headline = "partial", "Your partial communication profile"
        missing = [d.title.lower() for d in dimensions if d.status not in ("assessed", "provisional")]
        summary = (f"Assessed so far: {', '.join(d.title.lower() for d in assessed)}. "
                   f"Not enough evidence yet: {', '.join(missing)} — that's missing evidence, not a low score.")
    elif results:
        basis, headline = "goal_only", "No evidence yet"
        summary = "We haven't been able to assess a dimension yet. Your course follows your goal for now."
    else:
        basis, headline, summary = "none", "No evidence yet", None

    updated = max((row.assessed_at for row in chosen.values()), default=None, key=lambda d: as_utc(d))
    return Profile(
        basis=basis, headline=headline, summary=summary, dimensions=dimensions, speech_patterns=patterns, style=style,
        twin=_twin(vectors, speech_seconds), first_win=first_win, history=history, sources=sources,
        updated_at=iso(updated),
    )


def missing_dimensions(db: Session, user: User) -> list[str]:
    chosen = current_estimates(db, user)
    return [d for d in DIMENSION_IDS if d not in chosen]


def dimension_title(dim: str) -> str:
    return DIMENSIONS[dim].title


__all__ = ["build", "current_estimates", "missing_dimensions", "next_step_for", "dimension_title"]
