"""ORM models. Result payloads are stored as JSON shaped like the API objects they become.

JSON columns are not mutation-tracked: always assign a new dict/list instead of mutating in place.
Media references inside stored payloads use the placeholder form `media:<id>[#t=start,end]` and are
resolved to signed URLs at response time (see `services.media.resolve_media`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .timeutil import utcnow


def _now() -> datetime:
    return utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(20), default="ios")
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarding: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    practice_settings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    entitlement: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    analysis_consent_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    analysis_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    course_track: Mapped[str | None] = mapped_column(String(40), nullable=True)
    course_focus_module_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    free_mission_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    demo_seed: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # v2: the device's IANA timezone and locale (POST /v1/devices), and notification preferences.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notification_settings: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)  # None ⇒ shared
    kind: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cache_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class VoiceReference(Base):
    __tablename__ = "voice_references"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    consent_version: Mapped[str] = mapped_column(String(40))
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    clip_media_id: Mapped[str] = mapped_column(String(40))
    voiceprint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="active")
    awaiting: Mapped[str] = mapped_column(String(10), default="user")
    partner: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    setup: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    assessment_id: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    activity_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mission_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    persona_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quick: Mapped[bool] = mapped_column(Boolean, default=False)
    event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prep_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    max_user_turns: Mapped[int] = mapped_column(Integer, default=3)
    user_turns: Mapped[int] = mapped_column(Integer, default=0)
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # v2: daily reps and group conversations.
    daily_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    panel_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    participants: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    index: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(10))  # partner | user
    text: Mapped[str] = mapped_column(Text, default="")
    audio_media_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    coach_whisper: Mapped[str | None] = mapped_column(Text, nullable=True)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    segments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    momentum: Mapped[float | None] = mapped_column(Float, nullable=True)
    speaker_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # group participant id


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    route: Mapped[str] = mapped_column(String(20), default="roleplay")
    purpose: Mapped[str] = mapped_column(String(20), default="baseline")
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    activity_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    activity_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    target_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    style_vector: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(10))  # upload | live
    status: Mapped[str] = mapped_column(String(40), default="processing")
    stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    analyzed_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    consent: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    original_media_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    wav_media_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quality: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    segments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    speakers: Mapped[list[Any]] = mapped_column(JSON, default=list)
    attribution: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    style_vector: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    debrief: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    recovery: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DimensionEstimate(Base):
    """One evidence-backed estimate for one dimension from one source (assessment or recording)."""

    __tablename__ = "dimension_estimates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    dimension: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))  # assessed | provisional
    level: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[str] = mapped_column(String(10))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_type: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[str] = mapped_column(String(40), index=True)
    context_label: Mapped[str] = mapped_column(String(120))
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MissionProgress(Base):
    __tablename__ = "mission_progress"
    __table_args__ = (UniqueConstraint("user_id", "mission_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    mission_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    takeaway: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MissionAttempt(Base):
    __tablename__ = "mission_attempts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    mission_id: Mapped[str] = mapped_column(String(80), index=True)
    conversation_id: Mapped[str] = mapped_column(String(40))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    quick: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Reflection(Base):
    __tablename__ = "reflections"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    mission_id: Mapped[str] = mapped_column(String(80), index=True)
    text: Mapped[str] = mapped_column(Text)
    went: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coach_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SparReport(Base):
    __tablename__ = "spar_reports"

    conversation_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UpcomingEvent(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    date: Mapped[str] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    time: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "HH:MM" local, optional
    reflection: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # "How did it go?" afterwards


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("user_id", "milestone_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    milestone_id: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str] = mapped_column(Text)
    achieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ActivityLog(Base):
    """Practice activity, used for progress and the weekly review (never for skill estimates)."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    minutes: Mapped[float] = mapped_column(Float, default=0.0)
    ref_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WeeklyReviewCache(Base):
    __tablename__ = "weekly_reviews"
    __table_args__ = (UniqueConstraint("user_id", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    week_start: Mapped[str] = mapped_column(String(10))
    signature: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FeedbackReport(Base):
    """A user's report that a result looks wrong. Reviewed by the team; never changes results."""

    __tablename__ = "feedback_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[str] = mapped_column(String(80))
    dimension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ---------------------------------------------------------------------------------------------- v2


class Device(Base):
    """The install's push registration. One per user (auth is per install); a token belongs to one device."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    apns_token: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    push_environment: Mapped[str | None] = mapped_column(String(12), nullable=True)
    authorization: Mapped[str] = mapped_column(String(20), default="not_determined")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    locale: Mapped[str] = mapped_column(String(20), default="en-US")
    app_version: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    token_invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Notification(Base):
    """An in-app inbox item; `push_state` tracks delivery to APNs. Unique per (user, dedupe_key)."""

    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    deep_link: Mapped[str] = mapped_column(String(200))
    dedupe_key: Mapped[str] = mapped_column(String(160))
    interruption_level: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # pending → sent | skipped | failed; "none" for inbox-only items (e.g. seeded demo data).
    push_state: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    deliver_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    push_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    push_note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # A push is pointless after this (e.g. "Today: interview" after it started); the inbox item stays.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyAssignment(Base):
    """Which daily prompt a user gets on a local date. Stable once created (also for future dates)."""

    __tablename__ = "daily_assignments"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[str] = mapped_column(String(10))
    prompt_id: Mapped[str] = mapped_column(String(80))
    shuffled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DailyAttempt(Base):
    """One attempt at a daily rep; feedback has the same shape as mission attempt feedback."""

    __tablename__ = "daily_attempts"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    prompt_id: Mapped[str] = mapped_column(String(80))
    conversation_id: Mapped[str] = mapped_column(String(40))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="processing")
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    @property
    def quick(self) -> bool:  # mission-attempt compatibility for shared feedback code
        return False


class MissionOpen(Base):
    """First time a user opened a mission (drives the real-life mission check-in)."""

    __tablename__ = "mission_opens"
    __table_args__ = (UniqueConstraint("user_id", "mission_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(40), index=True)
    mission_id: Mapped[str] = mapped_column(String(80))
    first_opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
