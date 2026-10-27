"""Users, onboarding state, entitlement and the `Me` view."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.course import suggest_track
from ..domain.languages import normalize_language
from ..domain.markets import default_timezone, market_for
from ..errors import consent_required, validation
from ..ids import new_id
from ..models import DimensionEstimate, User, VoiceReference
from ..schemas import (
    Entitlement,
    Me,
    MePatch,
    NotificationSettings,
    Onboarding,
    PracticeSettings,
    VoiceReferenceStatus,
)
from ..timeutil import as_utc, iso, local_date, utcnow

DEFAULT_ONBOARDING = {
    "completed": False,
    "contexts_ranked": [],
    "ease_targets": [],
    "goal_track": None,
    "language": "en",
    "region": None,
    "course_started": False,
    "age_confirmed": False,
}
# `breaks` (internal, not in the API) keeps every planned break as {"start", "end"} so past weeks inside a break
# neither count nor break the weekly run.
DEFAULT_PRACTICE = {"weekly_target": 3, "reminder_time": None, "reminder_days": [], "anchor": None,
                    "paused_until": None, "breaks": []}
DEFAULT_NOTIFICATIONS = {
    "practice_reminders": True, "event_prep": True, "results": True, "check_ins": True, "nudges": True,
    "weekly_reveal": True, "tips": False, "quiet_start": "22:00", "quiet_end": "08:00",
}
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


def notification_settings(user: User) -> dict:
    return {**DEFAULT_NOTIFICATIONS, **(user.notification_settings or {})}


def market(user: User) -> str:
    return market_for(onboarding(user).get("region"))


def timezone(user: User) -> str:
    """The device-reported IANA timezone, or the market default until the device reports one."""
    return user.timezone or default_timezone(market(user))


def today(user: User, now: datetime | None = None) -> date:
    return local_date(now or utcnow(), timezone(user))


def breaks(user: User) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for item in practice_settings(user).get("breaks") or []:
        try:
            out.append((date.fromisoformat(item["start"]), date.fromisoformat(item["end"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def paused_until(user: User, day: date | None = None) -> str | None:
    """The end of the current planned break, or None when the user isn't on one."""
    value = practice_settings(user).get("paused_until")
    if not value:
        return None
    try:
        end = date.fromisoformat(value)
    except ValueError:
        return None
    return value if end >= (day or today(user)) else None


def is_paused(user: User, day: date | None = None) -> bool:
    return paused_until(user, day) is not None


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
            age_confirmed=bool(data.get("age_confirmed")),
        ),
        practice_settings=practice_settings_out(user),
        voice_reference=voice_reference_status(db, user),
        entitlement=Entitlement(tier=ent["tier"], expires_at=ent.get("expires_at"), source=ent.get("source", "none"),
                                product_id=ent.get("product_id")),
        has_results=results,
        next_step=next_step,
        market=market(user),
        timezone=timezone(user),
        notification_settings=NotificationSettings(**{k: v for k, v in notification_settings(user).items()
                                                      if k in NotificationSettings.model_fields}),
    )


def practice_settings_out(user: User) -> PracticeSettings:
    data = practice_settings(user)
    return PracticeSettings(weekly_target=data["weekly_target"], reminder_time=data.get("reminder_time"),
                            reminder_days=list(data.get("reminder_days") or []), anchor=data.get("anchor"),
                            paused_until=paused_until(user))


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
        if "age_confirmed" in provided and patch.onboarding.age_confirmed is not None:
            data["age_confirmed"] = bool(patch.onboarding.age_confirmed)
            data["age_confirmed_at"] = iso(utcnow()) if patch.onboarding.age_confirmed else None
        if "analysis_consent_version" in provided and patch.onboarding.analysis_consent_version:
            if not data.get("age_confirmed"):
                raise validation("Please confirm you're 18 or older to continue (onboarding.age_confirmed).")
            user.analysis_consent_version = patch.onboarding.analysis_consent_version
            user.analysis_consented_at = utcnow()
        user.onboarding = data
    if patch.practice_settings is not None:
        data = practice_settings(user)
        provided = patch.practice_settings.model_fields_set
        for field in ("weekly_target", "reminder_time", "reminder_days"):
            if field in provided:
                data[field] = getattr(patch.practice_settings, field)
        if "anchor" in provided:
            anchor = (patch.practice_settings.anchor or "").strip()
            data["anchor"] = anchor or None
        if "paused_until" in provided:
            data["breaks"] = _updated_breaks(user, data, patch.practice_settings.paused_until)
            data["paused_until"] = patch.practice_settings.paused_until
        user.practice_settings = data
    if patch.notification_settings is not None:
        data = notification_settings(user)
        for field in patch.notification_settings.model_fields_set:
            value = getattr(patch.notification_settings, field)
            if value is not None:
                data[field] = value
        user.notification_settings = data


def _updated_breaks(user: User, data: dict, new_until: str | None) -> list[dict]:
    """Start, extend or end the current planned break, keeping earlier breaks for the weekly run."""
    day = today(user)
    items = [dict(item) for item in data.get("breaks") or []]
    active = next((item for item in items if item.get("start", "") <= day.isoformat() <= item.get("end", "")), None)
    if new_until is None:
        if active is not None:
            active["end"] = day.isoformat()  # the break covered today; it ends now
        return items
    if active is not None:
        active["end"] = new_until
    elif new_until >= day.isoformat():
        items.append({"start": day.isoformat(), "end": new_until})
    return items[-50:]


def was_active_within(user: User, seconds: float, now: datetime | None = None) -> bool:
    if user.last_active_at is None:
        return False
    return ((now or utcnow()) - as_utc(user.last_active_at)) <= timedelta(seconds=seconds)
