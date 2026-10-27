"""Account deletion: every recording, result, voice reference, device, notification and the account itself."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..models import (
    ActivityLog,
    Assessment,
    Conversation,
    DailyAssignment,
    DailyAttempt,
    Device,
    DimensionEstimate,
    FeedbackReport,
    Media,
    Milestone,
    MissionAttempt,
    MissionOpen,
    MissionProgress,
    Notification,
    Recording,
    Reflection,
    SparReport,
    Turn,
    UpcomingEvent,
    User,
    VoiceReference,
    WeeklyReviewCache,
)


def delete_account(svc: AppServices, db: Session, user: User) -> None:
    user_id = user.id
    conversation_ids = list(db.scalars(select(Conversation.id).where(Conversation.user_id == user_id)))
    if conversation_ids:
        db.execute(delete(Turn).where(Turn.conversation_id.in_(conversation_ids)))
    for model in (Conversation, Assessment, Recording, DimensionEstimate, MissionAttempt, MissionProgress, Reflection,
                  SparReport, UpcomingEvent, Milestone, ActivityLog, WeeklyReviewCache, VoiceReference,
                  FeedbackReport, Device, Notification, DailyAssignment, DailyAttempt, MissionOpen):
        db.execute(delete(model).where(model.user_id == user_id))
    db.execute(delete(Media).where(Media.user_id == user_id))
    db.delete(user)
    db.commit()
    svc.storage.delete_prefix(user_id)
