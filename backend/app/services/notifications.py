"""In-app inbox, push delivery rules, the server-side producers and the scheduler.

Every notification is an inbox item first. Delivery to APNs is separate and follows the user's rules:
category toggles, quiet hours in their timezone, at most two pushes per local day, nothing but results and
event prep during a planned break. `results` skip quiet hours and the cap when the user was active in the
last 30 minutes (they're waiting for it).

Producers are idempotent through a unique (user, dedupe_key), so running `tick` twice (or on several
instances) never sends anything twice. Copy is warm, specific and guilt-free: no streak-loss language.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.course import MISSIONS, MODULES
from ..errors import not_found, validation
from ..ids import new_id
from ..models import (
    ActivityLog,
    Assessment,
    Device,
    MissionOpen,
    MissionProgress,
    Notification,
    Recording,
    Reflection,
    UpcomingEvent,
    User,
)
from ..push import PushMessage
from ..schemas import DeviceOut, DeviceRegistration, NotificationList, NotificationOut
from ..timeutil import (
    as_utc,
    day_bounds,
    is_valid_timezone,
    iso,
    iso_required,
    local_datetime,
    parse_hhmm,
    to_local,
    utcnow,
    week_bounds,
    week_start,
)
from . import users

log = logging.getLogger("comlogue.notifications")

# Category → NotificationSettings toggle. Milestones follow `results` (they're outcomes of your own practice).
CATEGORY_SETTING = {
    "practice": "practice_reminders", "event_prep": "event_prep", "results": "results", "check_in": "check_ins",
    "nudge": "nudges", "weekly_reveal": "weekly_reveal", "milestone": "results", "tips": "tips",
}
ALWAYS_IN_INBOX = {"results"}  # created even when the toggle is off; only the push is skipped
ALLOWED_ON_BREAK = {"results", "event_prep"}
PUSHABLE_AUTHORIZATIONS = {"authorized", "provisional", "ephemeral"}
PUSHES_PER_DAY = 2
RESULTS_ACTIVE_WINDOW = 30 * 60
FEEDBACK_IDLE_SECONDS = 120
# Feedback is usually ready within seconds, often while the person is still in the app. Its push waits this long
# and is dropped if they've been back in the app since (they've seen it); otherwise it brings them back.
FEEDBACK_PUSH_DELAY = timedelta(seconds=90)
MAX_PUSH_ATTEMPTS = 3
NUDGE_DAYS = (3, 8)
NUDGE_GAP = timedelta(hours=72)
EVENT_EVE = time(19, 0)
EVENT_MORNING = time(8, 0)
CHECK_IN_EVENING = time(19, 0)
CHECK_IN_WINDOW = (time(10, 0), time(20, 0))
WEEKLY_REVEAL = time(18, 0)
NUDGE_DEFAULT = time(18, 0)
REAL_LIFE_CHECK_IN_AFTER = timedelta(days=2)
REAL_LIFE_CHECK_IN_UNTIL = timedelta(days=14)


# ------------------------------------------------------------------ inbox


def notify(db: Session, user: User, *, category: str, title: str, body: str, deep_link: str, dedupe_key: str,
           now: datetime | None = None, interruption: str = "active",
           expires_at: datetime | None = None, deliver_after: datetime | None = None) -> Notification | None:
    """Create an inbox item (and queue its push). Returns None when the toggle is off or it already exists."""
    now = now or utcnow()
    settings = users.notification_settings(user)
    toggle = CATEGORY_SETTING.get(category)
    enabled = settings.get(toggle, True) if toggle else True
    if not enabled and category not in ALWAYS_IN_INBOX:
        return None
    if db.scalar(select(Notification.id).where(Notification.user_id == user.id,
                                               Notification.dedupe_key == dedupe_key)) is not None:
        return None
    item = Notification(
        id=new_id("ntf"), user_id=user.id, category=category, title=title[:200], body=body, deep_link=deep_link,
        dedupe_key=dedupe_key[:160], interruption_level=interruption, created_at=now,
        deliver_after=deliver_after or now,
        push_state="pending" if enabled else "skipped", push_note=None if enabled else "category off",
        expires_at=expires_at,
    )
    try:
        with db.begin_nested():
            db.add(item)
            db.flush()
    except IntegrityError:  # another instance created it first
        return None
    return item


def notification_out(item: Notification) -> NotificationOut:
    return NotificationOut(id=item.id, category=item.category, title=item.title, body=item.body,
                           deep_link=item.deep_link, created_at=iso_required(item.created_at),
                           read=item.read_at is not None)


def unread_count(db: Session, user_id: str) -> int:
    return int(db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id,
                                                                    Notification.read_at.is_(None))) or 0)


def list_for(db: Session, user: User, limit: int = 50) -> NotificationList:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit))
    return NotificationList(items=[notification_out(n) for n in rows], unread_count=unread_count(db, user.id))


def mark_read(db: Session, user: User, ids: list[str] | None, all_: bool) -> int:
    if not all_ and not ids:
        raise validation("Send the notification ids to mark as read, or all: true.")
    query = select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if not all_:
        query = query.where(Notification.id.in_(ids or []))
    now = utcnow()
    for item in db.scalars(query):
        item.read_at = now
    db.flush()
    return unread_count(db, user.id)


def mark_opened(db: Session, user: User, notification_id: str) -> None:
    item = db.get(Notification, notification_id)
    if item is None or item.user_id != user.id:
        raise not_found("Notification")
    now = utcnow()
    item.opened_at = item.opened_at or now
    item.read_at = item.read_at or now
    db.flush()


def send_test(svc: AppServices, db: Session, user: User) -> NotificationOut:
    """'Notifications are on' — pushed right away, ignoring quiet hours and the daily cap."""
    now = utcnow()
    item = Notification(
        id=new_id("ntf"), user_id=user.id, category="results", title="Notifications are on",
        body="You'll hear from us about your results, the reminders you set and the moments you're preparing for.",
        deep_link="comlogue://settings/notifications", dedupe_key=f"test:{uuid.uuid4().hex}", created_at=now,
        deliver_after=now, push_state="pending", interruption_level="active",
    )
    db.add(item)
    db.flush()
    _deliver(svc, db, item, now, force=True)
    db.flush()
    return notification_out(item)


# ------------------------------------------------------------------ devices


def device_for(db: Session, user_id: str) -> Device | None:
    return db.scalar(select(Device).where(Device.user_id == user_id))


def push_enabled(svc: AppServices, device: Device | None) -> bool:
    """True when the server WILL deliver pushes to this device (so the app shouldn't schedule its own)."""
    return bool(svc.push.enabled and device is not None and device.apns_token
                and device.authorization in PUSHABLE_AUTHORIZATIONS)


def register_device(svc: AppServices, db: Session, user: User, body: DeviceRegistration) -> DeviceOut:
    if not is_valid_timezone(body.timezone):
        raise validation("timezone must be an IANA name such as Asia/Kolkata or America/New_York.")
    now = utcnow()
    if body.apns_token:
        for other in db.scalars(select(Device).where(Device.apns_token == body.apns_token,
                                                     Device.user_id != user.id)):
            other.apns_token = None  # a token belongs to the install that reported it last
        db.flush()
    device = device_for(db, user.id)
    if device is None:
        device = Device(id=new_id("dev"), user_id=user.id, created_at=now)
        db.add(device)
    device.apns_token = body.apns_token
    device.push_environment = body.push_environment or ("production" if body.apns_token else None)
    device.authorization = body.authorization
    device.timezone = body.timezone
    device.locale = body.locale
    device.app_version = body.app_version
    device.updated_at = now
    if body.apns_token:
        device.token_invalidated_at = None
        device.last_error = None
    user.timezone = body.timezone
    user.locale = body.locale
    db.flush()
    return DeviceOut(id=device.id, push_enabled=push_enabled(svc, device))


def delete_device(db: Session, user: User, device_id: str) -> None:
    device = db.get(Device, device_id)
    if device is None or device.user_id != user.id:
        raise not_found("Device")
    db.delete(device)
    db.flush()


# ------------------------------------------------------------------ delivery


def in_quiet_hours(at: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= at < end
    return at >= start or at < end  # wraps past midnight, e.g. 22:00–08:00


def _quiet_end_after(local_now: datetime, end: time, tz: str) -> datetime:
    day = local_now.date() if local_now.time() < end else local_now.date() + timedelta(days=1)
    return local_datetime(day, end, tz)


def _pushes_today(db: Session, user_id: str, today: date, tz: str) -> int:
    start, end = day_bounds(today, tz)
    return int(db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user_id, Notification.push_state == "sent",
        Notification.pushed_at >= start, Notification.pushed_at < end)) or 0)


def _skip(item: Notification, note: str) -> None:
    item.push_state = "skipped"
    item.push_note = note


def _deliver(svc: AppServices, db: Session, item: Notification, now: datetime, force: bool = False) -> None:
    user = db.get(User, item.user_id)
    if user is None:
        _skip(item, "no user")
        return
    if (item.dedupe_key.startswith("feedback:") and user.last_active_at is not None
            and as_utc(user.last_active_at) > as_utc(item.created_at)):
        item.read_at = item.read_at or now  # they were back in the app and saw it: not unread either
        _skip(item, "seen in the app")
        return
    device = device_for(db, user.id)
    if not push_enabled(svc, device):
        _skip(item, "no push device")
        return
    assert device is not None and device.apns_token
    if item.expires_at is not None and as_utc(item.expires_at) <= now:
        _skip(item, "expired")
        return
    tz = users.timezone(user)
    local_now = to_local(now, tz)
    if not force:
        settings = users.notification_settings(user)
        toggle = CATEGORY_SETTING.get(item.category)
        if toggle and not settings.get(toggle, True):
            _skip(item, "category off")
            return
        if users.is_paused(user, local_now.date()) and item.category not in ALLOWED_ON_BREAK:
            _skip(item, "planned break")
            return
        waiting = item.category == "results" and users.was_active_within(user, RESULTS_ACTIVE_WINDOW, now)
        if not waiting:
            quiet_start, quiet_end = parse_hhmm(settings["quiet_start"]), parse_hhmm(settings["quiet_end"])
            if in_quiet_hours(local_now.time(), quiet_start, quiet_end):
                item.deliver_after = _quiet_end_after(local_now, quiet_end, tz)
                return  # stays pending until quiet hours end
            if _pushes_today(db, user.id, local_now.date(), tz) >= PUSHES_PER_DAY:
                _skip(item, "daily cap")
                return
    message = PushMessage(
        token=device.apns_token, environment=device.push_environment or "production", title=item.title,
        body=item.body, badge=unread_count(db, user.id), thread_id=item.category, collapse_id=item.dedupe_key,
        interruption_level=item.interruption_level, deep_link=item.deep_link, notification_id=item.id,
        expires_at=int((as_utc(item.expires_at) if item.expires_at else now + timedelta(hours=12)).timestamp()),
    )
    result = svc.push.send(message)
    item.push_attempts += 1
    if result.ok:
        item.push_state = "sent"
        item.pushed_at = now
        item.push_note = None
    elif result.invalid_token:
        device.apns_token = None
        device.token_invalidated_at = now
        device.last_error = (result.reason or f"HTTP {result.status}")[:200]
        item.push_state = "failed"
        item.push_note = f"token rejected: {result.reason}"[:120]
    elif result.retryable and item.push_attempts < MAX_PUSH_ATTEMPTS:
        item.deliver_after = now + timedelta(minutes=5 * item.push_attempts)
        item.push_note = f"retrying: {result.reason or result.status}"[:120]
    else:
        item.push_state = "failed"
        item.push_note = f"{result.status} {result.reason or ''}".strip()[:120]


def deliver_due(svc: AppServices, db: Session, now: datetime | None = None, user_id: str | None = None) -> int:
    """Push every pending notification that's due. Returns how many were looked at."""
    now = now or utcnow()
    query = select(Notification).where(Notification.push_state == "pending", Notification.deliver_after <= now)
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    items = list(db.scalars(query.order_by(Notification.created_at)))
    for item in items:
        # Claim it first, so two scheduler instances never push the same item.
        claim = update(Notification).where(Notification.id == item.id, Notification.push_state == "pending")
        if db.execute(claim.values(push_state="sending")).rowcount != 1:
            continue
        try:
            _deliver(svc, db, item, now)
        except Exception:  # noqa: BLE001 - one bad push must not block the rest
            log.exception("Push delivery failed for %s", item.id)
            item.push_state = "failed"
            item.push_note = "internal error"
        if item.push_state == "sending":
            item.push_state = "pending"  # deferred to the end of quiet hours, or waiting for a retry
        db.flush()  # the daily cap counts what this pass already sent
    return len(items)


# ------------------------------------------------------------------ result producers (called by jobs)


def _commit_and_push(svc: AppServices, db: Session, user_id: str) -> None:
    db.commit()
    deliver_due(svc, db, utcnow(), user_id=user_id)
    db.commit()


def recording_ready(svc: AppServices, db: Session, recording: Recording) -> None:
    user = db.get(User, recording.user_id)
    if user is None:
        return
    title = recording.title
    link = f"comlogue://recording/{recording.id}"
    stamp = iso(recording.completed_at) or iso_required(utcnow())
    if recording.status == "needs_speaker_confirmation":
        made = notify(db, user, category="results", title="Which voice is yours?",
                      body=f"We separated the voices in “{title}”. Confirm yours to see your feedback.",
                      deep_link=link, dedupe_key=f"recording:{recording.id}:confirm",
                      expires_at=utcnow() + timedelta(hours=24))
    elif recording.status == "complete":
        made = notify(db, user, category="results", title=f"Your feedback on “{title}” is ready",
                      body="See what worked, with the moments that show it, and one thing to try next.",
                      deep_link=link, dedupe_key=f"recording:{recording.id}:complete:{stamp}",
                      expires_at=utcnow() + timedelta(hours=24))
    elif recording.status in ("needs_recovery", "failed"):
        made = notify(db, user, category="results", title=f"We couldn't finish “{title}”",
                      body="Here's what happened and the quickest way to fix it.", deep_link=link,
                      dedupe_key=f"recording:{recording.id}:{recording.status}:{stamp}",
                      expires_at=utcnow() + timedelta(hours=24))
    else:
        return
    if made is not None:
        _commit_and_push(svc, db, user.id)


def assessment_ready(svc: AppServices, db: Session, assessment: Assessment) -> None:
    user = db.get(User, assessment.user_id)
    if user is None or assessment.status not in ("complete", "needs_recovery"):
        return
    link = f"comlogue://assessment/{assessment.id}"
    stamp = iso(assessment.completed_at) or iso_required(utcnow())
    if assessment.status == "complete":
        title = ("Your communication profile is ready" if assessment.purpose == "baseline"
                 else "Your follow-up results are in")
        body = "See what we could assess, the moments behind it, and your first small change."
    else:
        title, body = "We couldn't finish your analysis", "Your answers are saved. Tap to see the next step."
    made = notify(db, user, category="results", title=title, body=body, deep_link=link,
                  dedupe_key=f"assessment:{assessment.id}:{assessment.status}:{stamp}",
                  expires_at=utcnow() + timedelta(hours=24))
    if made is not None:
        _commit_and_push(svc, db, user.id)


def feedback_ready(svc: AppServices, db: Session, user_id: str, *, attempt_id: str, title: str,
                   deep_link: str) -> None:
    """Mission or daily-rep feedback. The push waits FEEDBACK_PUSH_DELAY and is dropped if the user has been in the
    app since (they've seen it there); the scheduler delivers it otherwise."""
    user = db.get(User, user_id)
    if user is None:
        return
    now = utcnow()
    made = notify(db, user, category="results", title=title,
                  body="Where the target showed up, what worked, and one change for next time.",
                  deep_link=deep_link, dedupe_key=f"feedback:{attempt_id}", now=now,
                  deliver_after=now + FEEDBACK_PUSH_DELAY, expires_at=now + timedelta(hours=24))
    if made is not None:
        db.commit()


def milestone_earned(db: Session, user_id: str, milestone_id: str, title: str, detail: str) -> None:
    """Inbox (and a quiet push) when a milestone lands while the app isn't in use."""
    user = db.get(User, user_id)
    if user is None or users.was_active_within(user, FEEDBACK_IDLE_SECONDS):
        return
    notify(db, user, category="milestone", title=f"Milestone: {title}", body=detail, deep_link="comlogue://today",
           dedupe_key=f"milestone:{milestone_id}", interruption="passive",
           expires_at=utcnow() + timedelta(hours=24))


def note_mission_opened(db: Session, user: User, mission_id: str) -> None:
    """Remember the first time a mission was opened (real-life missions get a gentle check-in later)."""
    if db.scalar(select(MissionOpen.id).where(MissionOpen.user_id == user.id,
                                              MissionOpen.mission_id == mission_id)) is None:
        try:
            with db.begin_nested():
                db.add(MissionOpen(user_id=user.id, mission_id=mission_id, first_opened_at=utcnow()))
                db.flush()
        except IntegrityError:
            pass


# ------------------------------------------------------------------ scheduled producers


def _events(db: Session, user: User, now: datetime, local_now: datetime, settings: dict, paused: bool) -> None:
    today = local_now.date()
    tz = users.timezone(user)
    window = [(today + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]
    for event in db.scalars(select(UpcomingEvent).where(UpcomingEvent.user_id == user.id,
                                                        UpcomingEvent.date.in_(window))):
        day = date.fromisoformat(event.date)
        link = f"comlogue://event/{event.id}"
        starts = local_datetime(day, parse_hhmm(event.time), tz) if event.time else None
        if settings["event_prep"] and day == today + timedelta(days=1) and local_now.time() >= EVENT_EVE:
            notify(db, user, category="event_prep", title=f"Tomorrow: {event.title}",
                   body="A five-minute warm-up tonight can make tomorrow feel easier. Want to rehearse?",
                   deep_link=link, dedupe_key=f"event_eve:{event.id}", now=now,
                   expires_at=local_datetime(day, time(0, 0), tz))
        if settings["event_prep"] and day == today:
            due = (starts - timedelta(hours=2)) if starts else local_datetime(day, EVENT_MORNING, tz)
            ends = starts or local_datetime(day, time(23, 0), tz)
            if due <= now < ends:
                when = f"At {event.time}. " if event.time else ""
                notify(db, user, category="event_prep", title=f"Today: {event.title}",
                       body=f"{when}One quick run-through to warm up your voice?", deep_link=link,
                       dedupe_key=f"event_day:{event.id}", now=now, interruption="time-sensitive", expires_at=ends)
        if (settings["check_ins"] and not paused and day == today - timedelta(days=1) and not event.reflection
                and local_now.time() >= CHECK_IN_EVENING):  # no need to ask once they've said how it went
            notify(db, user, category="check_in", title=f"How did {event.title} go?",
                   body="Take thirty seconds to note what worked — it makes the next one easier.", deep_link=link,
                   dedupe_key=f"event_after:{event.id}", now=now,
                   expires_at=local_datetime(today + timedelta(days=1), time(0, 0), tz))


def _real_life_check_ins(db: Session, user: User, now: datetime, local_now: datetime) -> None:
    if not (CHECK_IN_WINDOW[0] <= local_now.time() < CHECK_IN_WINDOW[1]):
        return
    opens = db.scalars(select(MissionOpen).where(MissionOpen.user_id == user.id,
                                                 MissionOpen.first_opened_at <= now - REAL_LIFE_CHECK_IN_AFTER,
                                                 MissionOpen.first_opened_at >= now - REAL_LIFE_CHECK_IN_UNTIL))
    for opened in opens:
        mission = MISSIONS.get(opened.mission_id)
        if mission is None or mission.type != "real_life":
            continue
        reflected = db.scalar(select(Reflection.id).where(Reflection.user_id == user.id,
                                                          Reflection.mission_id == mission.id).limit(1))
        done = db.scalar(select(MissionProgress.id).where(MissionProgress.user_id == user.id,
                                                          MissionProgress.mission_id == mission.id))
        if reflected is not None or done is not None:
            continue
        target = MODULES[mission.module_id].target_behavior
        notify(db, user, category="check_in", title="Did you get to try it?",
               body=f"“{target}” — even a small try counts. How did it go?",
               deep_link=f"comlogue://reflect/{mission.id}", dedupe_key=f"real_life:{mission.id}", now=now,
               expires_at=now + timedelta(hours=10))


def _last_return(db: Session, user: User) -> datetime:
    """When the user last practised or opened one of our notifications (resets nudge back-off)."""
    last_session = db.scalar(select(func.max(ActivityLog.created_at)).where(
        ActivityLog.user_id == user.id, ActivityLog.type.in_(_session_types())))
    last_open = db.scalar(select(func.max(Notification.opened_at)).where(Notification.user_id == user.id))
    candidates = [as_utc(user.created_at)] + [as_utc(v) for v in (last_session, last_open) if v is not None]
    return max(candidates)


def _session_types() -> tuple[str, ...]:
    from .progress import SESSION_TYPES

    return SESSION_TYPES


def _nudges(svc: AppServices, db: Session, user: User, now: datetime, local_now: datetime, settings: dict) -> None:
    if not settings["nudges"] or not users.onboarding(user).get("completed"):
        return
    if not users.practice_settings(user).get("weekly_target"):
        return
    tz = users.timezone(user)
    anchor = _last_return(db, user)
    quiet_days = (local_now.date() - to_local(anchor, tz).date()).days
    reminder = users.practice_settings(user).get("reminder_time")
    send_at = parse_hhmm(reminder) if reminder else NUDGE_DEFAULT
    if local_now.time() < send_at:
        return
    last_nudge = db.scalar(select(func.max(Notification.created_at)).where(
        Notification.user_id == user.id, Notification.category == "nudge"))
    if last_nudge is not None and now - as_utc(last_nudge) < NUDGE_GAP:
        return
    anchor_key = to_local(anchor, tz).date().isoformat()
    sent = set(db.scalars(select(Notification.dedupe_key).where(
        Notification.user_id == user.id, Notification.category == "nudge",
        Notification.dedupe_key.like(f"nudge:{anchor_key}:%"))))
    for number, days in enumerate(NUDGE_DAYS, start=1):
        key = f"nudge:{anchor_key}:{number}"
        if key in sent:
            continue
        if quiet_days < days:
            return
        if number == 1:
            from . import daily  # local import: daily imports notifications

            rep = daily.preview(svc, db, user, local_now.date())
            title, body = "Your 1-minute practice is ready", f"Today: {rep.title}. One minute is plenty — whenever suits you."
        else:
            title = "Pick up where you left off"
            body = "Your progress is saved. Start again with a 1-minute practice — no catching up needed."
        notify(db, user, category="nudge", title=title, body=body, deep_link="comlogue://daily", dedupe_key=key,
               now=now, expires_at=local_datetime(local_now.date() + timedelta(days=1), time(0, 0), tz))
        return  # at most one nudge per tick


def _weekly_reveal(db: Session, user: User, now: datetime, local_now: datetime, settings: dict) -> None:
    if not settings["weekly_reveal"] or local_now.weekday() != 6 or local_now.time() < WEEKLY_REVEAL:
        return
    tz = users.timezone(user)
    start, end = week_bounds(now, tz)
    logs = list(db.scalars(select(ActivityLog).where(
        ActivityLog.user_id == user.id, ActivityLog.type.in_(_session_types()),
        ActivityLog.created_at >= start, ActivityLog.created_at < end)))
    if not logs:
        return
    sessions = len(logs)
    minutes = int(round(sum(log.minutes for log in logs)))
    practice = f"{sessions} session{'s' if sessions != 1 else ''}"
    if minutes:
        practice += f" and {minutes} min of practice"
    notify(db, user, category="weekly_reveal", title="Your week in Comlogue",
           body=f"{practice} this week. See what changed and pick next week's focus.",
           deep_link="comlogue://review/weekly", dedupe_key=f"weekly:{week_start(now, tz).isoformat()}", now=now,
           interruption="passive", expires_at=end + timedelta(hours=12))


def produce(svc: AppServices, db: Session, user: User, now: datetime) -> None:
    local_now = to_local(now, users.timezone(user))
    settings = users.notification_settings(user)
    paused = users.is_paused(user, local_now.date())
    _events(db, user, now, local_now, settings, paused)
    if paused:
        return
    if settings["check_ins"]:
        _real_life_check_ins(db, user, now, local_now)
    _nudges(svc, db, user, now, local_now, settings)
    _weekly_reveal(db, user, now, local_now, settings)


def tick(svc: AppServices, now: datetime | None = None) -> None:
    """One scheduler pass: produce what's due for recently active users, then deliver pending pushes."""
    now = now or utcnow()
    db = svc.session_factory()
    try:
        cutoff = now - timedelta(days=60)
        user_ids = list(db.scalars(select(User.id).where(or_(User.last_active_at >= cutoff,
                                                             User.created_at >= cutoff))))
        for user_id in user_ids:
            user = db.get(User, user_id)
            if user is None:
                continue
            try:
                with db.begin_nested():
                    produce(svc, db, user, now)
            except Exception:  # noqa: BLE001 - one user's data must not stop the scheduler
                log.exception("Notification producers failed for %s", user_id)
        db.commit()
        deliver_due(svc, db, now)
        db.commit()
    finally:
        db.close()


class NotificationScheduler:
    """Runs `tick` every few minutes on a daemon thread (started from the app lifespan)."""

    def __init__(self, svc: AppServices, interval_seconds: int):
        self.svc = svc
        self.interval = max(30, interval_seconds)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="notifications", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                tick(self.svc)
            except Exception:  # noqa: BLE001
                log.exception("Notification tick failed")

    def stop(self) -> None:
        self._stop.set()
