"""Data export (GET /v1/me/export): everything stored about the user, as one JSON document. No audio.

Covers access requests under India's DPDP Act and US state privacy laws. Shapes reuse the API objects; media links
are removed (they'd expire anyway, and audio isn't part of the export).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..models import (
    ActivityLog,
    Assessment,
    Conversation,
    DailyAssignment,
    DailyAttempt,
    Device,
    FeedbackReport,
    Milestone,
    MissionAttempt,
    MissionProgress,
    Notification,
    Recording,
    Reflection,
    SparReport,
    Turn,
    UpcomingEvent,
    User,
    VoiceReference,
)
from ..timeutil import iso, iso_required, utcnow
from . import assessments, conversations, events, notifications, profile, recordings, users
from . import course as course_service
from . import daily as daily_service

EXPORT_VERSION = "1"
FILENAME = "comlogue-export.json"


def _strip_media(value: Any) -> Any:
    """Drop media links (keys ending in `_url`) everywhere, keeping the shapes."""
    if isinstance(value, dict):
        return {k: (None if k.endswith("_url") else _strip_media(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_media(v) for v in value]
    return value


def _transcript(db: Session, conv: Conversation) -> list[dict[str, Any]]:
    names = conversations.participant_names(conv)
    partner = conv.partner.get("name", "Partner")
    rows: list[Turn] = conversations.turns_of(db, conv)
    return [{"index": t.index, "speaker": "You" if t.speaker == "user" else names.get(t.speaker_id or "", partner),
             "is_user": t.speaker == "user", "text": t.text, "excluded": bool(t.excluded),
             "created_at": iso_required(t.created_at)} for t in rows]


def _conversation(db: Session, conv: Conversation) -> dict[str, Any]:
    return {"id": conv.id, "kind": conv.kind, "title": conv.setup.get("title"), "status": conv.status,
            "language": conv.language, "created_at": iso_required(conv.created_at),
            "finished_at": iso(conv.finished_at), "turns": _transcript(db, conv)}


def build(svc: AppServices, db: Session, user: User) -> dict[str, Any]:
    uid = user.id
    convs = list(db.scalars(select(Conversation).where(Conversation.user_id == uid).order_by(Conversation.created_at)))
    by_id = {c.id: c for c in convs}

    assessment_rows = list(db.scalars(select(Assessment).where(Assessment.user_id == uid)
                                      .order_by(Assessment.created_at)))
    assessment_out = []
    for row in assessment_rows:
        item = assessments.to_out(svc, row).model_dump(mode="json")
        item["conversations"] = [_conversation(db, c) for c in convs if c.assessment_id == row.id]
        assessment_out.append(item)

    recording_out = []
    for row in db.scalars(select(Recording).where(Recording.user_id == uid).order_by(Recording.created_at)):
        item = recordings.to_out(svc, row).model_dump(mode="json")
        item["consent"] = row.consent or {}
        item["transcript"] = recordings.transcript(row).model_dump(mode="json")["segments"]
        recording_out.append(item)

    attempts = []
    for row in db.scalars(select(MissionAttempt).where(MissionAttempt.user_id == uid)
                          .order_by(MissionAttempt.created_at)):
        item = course_service._feedback_out(svc, row).model_dump(mode="json")
        item["mission_id"] = row.mission_id
        conv = by_id.get(row.conversation_id)
        item["transcript"] = _transcript(db, conv) if conv else []
        attempts.append(item)

    reps: dict[str, dict[str, Any]] = {}
    for row in db.scalars(select(DailyAssignment).where(DailyAssignment.user_id == uid)
                          .order_by(DailyAssignment.date)):
        reps[row.date] = {"date": row.date, "prompt_id": row.prompt_id, "shuffled": bool(row.shuffled),
                          "attempts": []}
    for row in db.scalars(select(DailyAttempt).where(DailyAttempt.user_id == uid).order_by(DailyAttempt.created_at)):
        rep = reps.setdefault(row.date, {"date": row.date, "prompt_id": row.prompt_id, "shuffled": False,
                                         "attempts": []})
        item = daily_service.attempt_out(svc, row).model_dump(mode="json")
        conv = by_id.get(row.conversation_id)
        item["transcript"] = _transcript(db, conv) if conv else []
        rep["attempts"].append(item)

    sessions = []
    for conv in convs:
        if conv.kind not in ("spar", "group"):
            continue
        item = _conversation(db, conv)
        report = db.get(SparReport, conv.id)
        item["report"] = report.report if report and report.report else None
        sessions.append(item)

    ref = db.scalar(select(VoiceReference).where(VoiceReference.user_id == uid))
    devices = [{"id": d.id, "push_token_registered": bool(d.apns_token), "push_environment": d.push_environment,
                "authorization": d.authorization, "timezone": d.timezone, "locale": d.locale,
                "app_version": d.app_version, "created_at": iso(d.created_at), "updated_at": iso(d.updated_at)}
               for d in db.scalars(select(Device).where(Device.user_id == uid))]
    notification_rows = list(db.scalars(select(Notification).where(Notification.user_id == uid)
                                        .order_by(Notification.created_at)))

    data = {
        "export_version": EXPORT_VERSION,
        "exported_at": iso_required(utcnow()),
        "account": {
            **users.build_me(svc, db, user).model_dump(mode="json"),
            "locale": user.locale,
            "age_confirmed_at": users.onboarding(user).get("age_confirmed_at"),
            "practice_breaks": users.practice_settings(user).get("breaks") or [],
        },
        "voice_reference": None if ref is None else {
            "created_at": iso(ref.created_at), "duration_seconds": round(ref.duration_seconds, 1),
            "consent_version": ref.consent_version, "consented_at": iso(ref.consented_at),
            "last_used_at": iso(ref.last_used_at),
            "voiceprint": ref.voiceprint or {},  # acoustic features measured from your reference clip
        },
        "profile": profile.build(svc, db, user).model_dump(mode="json"),
        "assessments": assessment_out,
        "recordings": recording_out,
        "missions": {
            "completed": [{"mission_id": p.mission_id, "takeaway": p.takeaway, "completed_at": iso(p.completed_at)}
                          for p in db.scalars(select(MissionProgress).where(MissionProgress.user_id == uid))],
            "attempts": attempts,
            "reflections": [{"id": r.id, "mission_id": r.mission_id, "text": r.text, "went": r.went,
                             "coach_reply": r.coach_reply, "created_at": iso(r.created_at)}
                            for r in db.scalars(select(Reflection).where(Reflection.user_id == uid)
                                                .order_by(Reflection.created_at))],
        },
        "daily_reps": list(reps.values()),
        "spar_and_group_sessions": sessions,
        "events": [events.to_out(e).model_dump(mode="json")
                   for e in db.scalars(select(UpcomingEvent).where(UpcomingEvent.user_id == uid)
                                       .order_by(UpcomingEvent.date))],
        "notifications": [{**notifications.notification_out(n).model_dump(mode="json"),
                           "opened_at": iso(n.opened_at), "push": n.push_state}
                          for n in notification_rows],
        "devices": devices,
        "milestones": [{"id": m.milestone_id, "title": m.title, "detail": m.detail,
                        "achieved_at": iso(m.achieved_at)}
                       for m in db.scalars(select(Milestone).where(Milestone.user_id == uid))],
        "practice_log": [{"type": a.type, "title": a.title, "minutes": round(a.minutes, 2),
                          "created_at": iso(a.created_at)}
                         for a in db.scalars(select(ActivityLog).where(ActivityLog.user_id == uid)
                                             .order_by(ActivityLog.created_at))],
        "feedback_reports": [{"id": f.id, "target_type": f.target_type, "target_id": f.target_id,
                              "dimension": f.dimension, "reason": f.reason, "note": f.note,
                              "created_at": iso(f.created_at)}
                             for f in db.scalars(select(FeedbackReport).where(FeedbackReport.user_id == uid))],
    }
    return _strip_media(data)
