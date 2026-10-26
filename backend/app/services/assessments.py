"""Guided AI-roleplay assessments (baseline: the five activities; gap-fill: one targeted activity)."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.activities import ACTIVITIES, ACTIVITY_ORDER, assessment_estimate_minutes
from ..domain.evidence import MIN_USER_SPEECH_SECONDS
from ..errors import AIUnavailableError, conflict, not_found, validation
from ..ids import new_id
from ..models import Assessment, Conversation, DimensionEstimate, Turn, User
from ..schemas import (
    AnalysisResult,
    AssessmentActivity,
    AssessmentCreate,
    AssessmentOut,
    ConversationOut,
    Recovery,
    RecoveryAction,
    StyleResult,
)
from ..timeutil import iso, iso_required, short_date, utcnow
from . import conversations, progress, users
from . import media as media_service
from .analysis import STYLE_NOT_READY, AnalysisInput, missing_dimension, run_analysis

log = logging.getLogger("comlogue.assessments")


def create(svc: AppServices, db: Session, user: User, body: AssessmentCreate) -> Assessment:
    users.require_analysis_consent(user)
    activity_ids = list(dict.fromkeys(body.activity_ids or ACTIVITY_ORDER))
    if body.purpose == "gap_fill" and not body.activity_ids:
        raise validation("A gap-fill task needs at least one activity.")
    targets = list(dict.fromkeys(body.target_dimensions or []))
    if body.purpose == "gap_fill" and not targets:
        targets = sorted({d for a in activity_ids for d in ACTIVITIES[a].dimensions})
    assessment = Assessment(
        id=new_id("asm"), user_id=user.id, route="roleplay", purpose=body.purpose, status="in_progress",
        activity_ids=activity_ids,
        activity_state={a: {"status": "pending", "conversation_id": None} for a in activity_ids},
        target_dimensions=targets, language=users.language(user),
    )
    db.add(assessment)
    db.flush()
    return assessment


def get_owned(db: Session, user: User, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.user_id != user.id:
        raise not_found("Assessment")
    return assessment


def to_out(svc: AppServices, assessment: Assessment) -> AssessmentOut:
    activities = []
    for activity_id in assessment.activity_ids:
        activity = ACTIVITIES[activity_id]
        state = (assessment.activity_state or {}).get(activity_id, {})
        activities.append(AssessmentActivity(
            id=activity_id, title=activity.title, prompt=activity.prompt, duration_label=activity.duration_label,
            suggested_seconds=activity.suggested_seconds, dimensions=list(activity.dimensions),
            status=state.get("status", "pending"), conversation_id=state.get("conversation_id"),
        ))
    result = None
    if assessment.result:
        result = AnalysisResult.model_validate(media_service.resolve_media(svc, assessment.result))
    return AssessmentOut(
        id=assessment.id, route="roleplay", purpose=assessment.purpose, status=assessment.status,
        stage=assessment.stage, activities=activities,
        estimate_minutes=assessment_estimate_minutes(assessment.activity_ids),
        target_dimensions=list(assessment.target_dimensions or []), result=result,
        created_at=iso_required(assessment.created_at), completed_at=iso(assessment.completed_at),
    )


def start_activity(svc: AppServices, db: Session, user: User, assessment: Assessment, activity_id: str) -> ConversationOut:
    if activity_id not in assessment.activity_ids:
        raise not_found("Activity")
    if assessment.status not in ("in_progress", "needs_recovery"):
        raise conflict("This assessment is already being analyzed.")
    state = (assessment.activity_state or {}).get(activity_id, {})
    conversation_id = state.get("conversation_id")
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv is not None and conv.status == "active":
            return conversations.conversation_out(svc, db, conv)
    assessment.status = "in_progress"
    conv = conversations.create_activity_conversation(svc, db, user, assessment, activity_id)
    new_state = dict(assessment.activity_state or {})
    new_state[activity_id] = {"status": "in_progress", "conversation_id": conv.id}
    assessment.activity_state = new_state
    return conversations.conversation_out(svc, db, conv)


def skip_activity(db: Session, assessment: Assessment, activity_id: str) -> None:
    if activity_id not in assessment.activity_ids:
        raise not_found("Activity")
    state = dict(assessment.activity_state or {})
    entry = dict(state.get(activity_id, {}))
    if entry.get("status") != "done":
        entry["status"] = "skipped"
    state[activity_id] = entry
    assessment.activity_state = state
    conversation_id = entry.get("conversation_id")
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv is not None and conv.status == "active":
            conv.status = "finished"
            conv.awaiting = "none"
            conv.finished_at = utcnow()


def finalize(svc: AppServices, db: Session, user: User, assessment: Assessment) -> None:
    if assessment.status == "processing":
        return
    if assessment.status == "complete":
        raise conflict("This assessment is already complete.")
    assessment.status = "processing"
    assessment.stage = "checking_audio"
    assessment.error = None
    db.commit()
    assert svc.jobs is not None
    svc.jobs.submit("assessment.finalize", assessment.id)
    db.refresh(assessment)


def _units(db: Session, assessment: Assessment) -> tuple[list, list[float], list[str], int]:
    units = []
    pauses: list[float] = []
    notes: list[str] = []
    excluded = 0
    for position, activity_id in enumerate(assessment.activity_ids, start=1):
        conversation_id = (assessment.activity_state or {}).get(activity_id, {}).get("conversation_id")
        if not conversation_id:
            continue
        conv = db.get(Conversation, conversation_id)
        if conv is None:
            continue
        turns = list(db.scalars(select(Turn).where(Turn.conversation_id == conv.id).order_by(Turn.index)))
        activity_units = conversations.units_for(conv, turns, uid_prefix=f"A{position}.")
        if any(u.role == "user" for u in activity_units):
            activity = ACTIVITIES[activity_id]
            notes.append(f"A{position} {activity.title} — opportunities for: {', '.join(activity.dimensions)}")
        units.extend(activity_units)
        for turn in turns:
            if turn.speaker == "user":
                if turn.excluded:
                    excluded += 1
                else:
                    pauses.extend((turn.metrics or {}).get("pauses") or [])
    return units, pauses, notes, excluded


def _failed_result(context_label: str) -> dict:
    from ..domain.dimensions import DIMENSION_IDS

    result = AnalysisResult(
        status="none",
        headline="We couldn't finish your analysis right now",
        summary="This was a problem on our side, not with how you communicate. Your answers are saved — try again "
        "in a moment.",
        dimensions=[missing_dimension(d, "Analysis didn't finish.", status="not_assessed") for d in DIMENSION_IDS],
        speech_patterns=None, first_win=None,
        style=StyleResult(status="not_ready", archetype=None, description=None, traits=[], message=STYLE_NOT_READY),
        recovery=Recovery(problem="processing_failed", title="Analysis didn't finish",
                          message="Your answers are saved. Try again in a moment.",
                          actions=[RecoveryAction(type="retry", title="Try again", activity_id=None)],
                          extra_minutes=None),
        context_label=context_label, created_at=iso_required(utcnow()),
    )
    return result.model_dump(mode="json")


def run_finalize_job(svc: AppServices, assessment_id: str) -> None:
    db = svc.session_factory()
    try:
        assessment = db.get(Assessment, assessment_id)
        if assessment is None or assessment.status != "processing":
            return
        user = db.get(User, assessment.user_id)
        if user is None:
            return
        label = ("AI roleplay" if assessment.purpose == "baseline" else "Follow-up roleplay")
        context_label = f"{label} · {short_date(assessment.created_at)}"
        units, pauses, notes, excluded = _units(db, assessment)
        user_speech = sum(u.duration for u in units if u.usable_user)
        assessment.stage = "assessing"
        db.commit()
        inp = AnalysisInput(
            user_id=user.id, language=assessment.language, source_type="assessment", source_id=assessment.id,
            context_label=context_label,
            context_description=(
                "Guided AI roleplay with Maya, an AI character. The user's microphone channel is isolated, so USER "
                "lines are the user's own speech (background voices were already removed)."
            ),
            units=units, pauses=pauses, activity_notes=notes,
            target_dimensions=list(assessment.target_dimensions or []) if assessment.purpose == "gap_fill" else [],
            audio_problem=excluded > 0 and user_speech < MIN_USER_SPEECH_SECONDS, route="roleplay",
        )
        try:
            output = run_analysis(svc, db, inp)
        except AIUnavailableError as exc:
            log.warning("Assessment %s analysis failed: %s", assessment_id, exc)
            assessment.status = "needs_recovery"
            assessment.stage = None
            assessment.error = str(exc)[:500]
            assessment.result = _failed_result(context_label)
            db.commit()
            return
        assessment.result = output.result.model_dump(mode="json")
        assessment.style_vector = output.style_vector
        assessment.status = "complete" if output.result.status != "none" else "needs_recovery"
        assessment.stage = None
        assessment.completed_at = utcnow()
        db.execute(delete(DimensionEstimate).where(DimensionEstimate.source_id == assessment.id))
        for estimate in output.estimates:
            db.add(DimensionEstimate(
                user_id=user.id, dimension=estimate["dimension"], status=estimate["status"],
                level=estimate["level"], confidence=estimate["confidence"] or "low", payload=estimate["payload"],
                source_type="assessment", source_id=assessment.id, context_label=context_label,
                assessed_at=utcnow(),
            ))
        minutes = sum(conversations.conversation_minutes(db, conv) for conv in db.scalars(
            select(Conversation).where(Conversation.assessment_id == assessment.id)))
        progress.log_activity(db, user.id, "assessment", context_label, minutes, assessment.id)
        progress.award(db, user.id, "first_conversation")
        if output.estimates:
            progress.award(db, user.id, "first_profile")
        db.commit()
    except Exception:
        db.rollback()
        assessment = db.get(Assessment, assessment_id)
        if assessment is not None and assessment.status == "processing":
            assessment.status = "needs_recovery"
            assessment.stage = None
            assessment.result = _failed_result(f"AI roleplay · {short_date(assessment.created_at)}")
            db.commit()
        raise
    finally:
        db.close()


def list_for(db: Session, user: User) -> list[Assessment]:
    return list(db.scalars(select(Assessment).where(Assessment.user_id == user.id).order_by(Assessment.created_at.desc())))
