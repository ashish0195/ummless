"""Users, onboarding state, entitlement and the `Me` view."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.course import suggest_track
from ..domain.languages import normalize_language
from ..errors import consent_required
from ..ids import new_id
from ..models import DimensionEstimate, User, VoiceReference
from ..schemas import (
    Entitlement,
    Me,
    MePatch,
    Onboarding,
    PracticeSettings,
    VoiceReferenceStatus,
)
from ..timeutil import as_utc, iso, utcnow

DEFAULT_ONBOARDING = {
    "completed": False,
    "contexts_ranked": [],
    "ease_targets": [],
    "goal_track": None,
    "language": "en",
    "region": None,
    "course_started": False,
}
DEFAULT_PRACTICE = {"weekly_target": 3, "reminder_time": None, "reminder_days": []}
DEFAULT_ENTITLEMENT = {"tier": "free", "expires_at": None, "source": "none", "product_id": None}


def get_or_create_by_device(db: Session, device_id: str, platform: str, app_version: str | None) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.device_id == device_id))
    if user is not None:
        user.app_version = app_version or user.app_version
        user.last_active_at = utcnow()
        return user, False
    user = User(
        id=new_id("usr"),
        device_id=device_id,
        platform=platform,
        app_version=app_version,
        onboarding=dict(DEFAULT_ONBOARDING),
        practice_settings=dict(DEFAULT_PRACTICE),
        entitlement=dict(DEFAULT_ENTITLEMENT),
        last_active_at=utcnow(),
    )
    db.add(user)
    db.flush()
    return user, True


def onboarding(user: User) -> dict:
    return {**DEFAULT_ONBOARDING, **(user.onboarding or {})}


def practice_settings(user: User) -> dict:
    return {**DEFAULT_PRACTICE, **(user.practice_settings or {})}


def language(user: User) -> str:
    return normalize_language(onboarding(user).get("language"))


def goal_track(user: User) -> str:
    data = onboarding(user)
    return user.course_track or data.get("goal_track") or suggest_track(
        data.get("contexts_ranked") or [], data.get("ease_targets") or []
    )


def entitlement(user: User) -> dict:
    data = {**DEFAULT_ENTITLEMENT, **(user.entitlement or {})}
    if data["tier"] == "pro" and data.get("expires_at"):
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        if as_utc(expires) < utcnow():
            data = {**data, "tier": "free"}
    return data


def is_pro(user: User) -> bool:
    return entitlement(user)["tier"] == "pro"


def require_analysis_consent(user: User) -> None:
    if not user.analysis_consent_version:
        raise consent_required()


def has_results(db: Session, user: User) -> bool:
    return bool(db.scalar(select(exists().where(DimensionEstimate.user_id == user.id))))


def voice_reference_status(db: Session, user: User) -> VoiceReferenceStatus:
    ref = db.scalar(select(VoiceReference).where(VoiceReference.user_id == user.id))
    if ref is None:
        return VoiceReferenceStatus(status="none", created_at=None, duration_seconds=None, consent_version=None)
    return VoiceReferenceStatus(status="active", created_at=iso(ref.created_at),
                                duration_seconds=round(ref.duration_seconds, 1), consent_version=ref.consent_version)


def build_me(svc: AppServices, db: Session, user: User) -> Me:
    data = onboarding(user)
    results = has_results(db, user)
    if not data["completed"]:
        next_step = "onboarding"
    elif results or data.get("course_started"):
        next_step = "home"
    else:
        next_step = "choose_input"
    ent = entitlement(user)
    return Me(
        user_id=user.id,
        created_at=iso(user.created_at) or "",
        demo_mode=svc.demo_mode,
        onboarding=Onboarding(
            completed=bool(data["completed"]),
            contexts_ranked=list(data.get("contexts_ranked") or []),
            ease_targets=list(data.get("ease_targets") or []),
            goal_track=data.get("goal_track"),
            language=normalize_language(data.get("language")),
            region=data.get("region"),
            analysis_consent_version=user.analysis_consent_version,
            analysis_consented_at=iso(user.analysis_consented_at),
            course_started=bool(data.get("course_started")),
        ),
        practice_settings=PracticeSettings(**practice_settings(user)),
        voice_reference=voice_reference_status(db, user),
        entitlement=Entitlement(tier=ent["tier"], expires_at=ent.get("expires_at"), source=ent.get("source", "none"),
                                product_id=ent.get("product_id")),
        has_results=results,
        next_step=next_step,
    )


def apply_patch(user: User, patch: MePatch) -> None:
    if patch.onboarding is not None:
        data = onboarding(user)
        provided = patch.onboarding.model_fields_set
        for field in ("completed", "contexts_ranked", "ease_targets", "goal_track", "region", "course_started"):
            if field in provided:
                data[field] = getattr(patch.onboarding, field)
        if "language" in provided and patch.onboarding.language:
            data["language"] = normalize_language(patch.onboarding.language)
        if "goal_track" in provided and patch.onboarding.goal_track:
            user.course_track = patch.onboarding.goal_track
            user.course_focus_module_id = None
        if "analysis_consent_version" in provided and patch.onboarding.analysis_consent_version:
            user.analysis_consent_version = patch.onboarding.analysis_consent_version
            user.analysis_consented_at = utcnow()
        user.onboarding = data
    if patch.practice_settings is not None:
        data = practice_settings(user)
        for field in patch.practice_settings.model_fields_set:
            data[field] = getattr(patch.practice_settings, field)
        user.practice_settings = data
