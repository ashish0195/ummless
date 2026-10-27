"""Devices, the inbox, push delivery rules and the scheduled producers (fixed clock, RecordingSender)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.models import ActivityLog, Device, MissionOpen, Notification, Recording, Reflection, UpcomingEvent, User
from app.push import PushResult, RecordingSender
from app.services import notifications, progress
from app.timeutil import local_datetime, utcnow
from tests.helpers import signup

TOKEN = "ab" * 32
KOLKATA = "Asia/Kolkata"
NEW_YORK = "America/New_York"
DAY = date(2026, 11, 4)  # a Wednesday, after the US clocks change


def _svc(client):
    return client.app.state.services


def _user_id(client, headers) -> str:
    return client.get("/v1/me", headers=headers).json()["user_id"]


def _register(client, headers, *, token: str | None = TOKEN, authorization: str = "authorized",
              tz: str = KOLKATA, environment: str | None = "sandbox"):
    body = {"apns_token": token, "push_environment": environment, "authorization": authorization, "timezone": tz,
            "locale": "en-IN", "app_version": "2.0"}
    return client.post("/v1/devices", headers=headers, json=body)


def _update_user(client, user_id: str, **changes) -> None:
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        for key, value in changes.items():
            setattr(user, key, value)
        db.commit()


def _items(client, user_id: str, category: str | None = None) -> list[Notification]:
    with _svc(client).session_factory() as db:
        query = select(Notification).where(Notification.user_id == user_id)
        if category is not None:
            query = query.where(Notification.category == category)
        return list(db.scalars(query.order_by(Notification.created_at, Notification.id)))


def _by_key(client, user_id: str, key: str) -> Notification:
    return next(n for n in _items(client, user_id) if n.dedupe_key == key)


def _notify(client, user_id: str, **fields) -> Notification | None:
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        fields.setdefault("title", "Title")
        fields.setdefault("body", "Body")
        fields.setdefault("deep_link", "comlogue://today")
        item = notifications.notify(db, user, **fields)
        db.commit()
        return item


def _deliver(client, now: datetime) -> None:
    with _svc(client).session_factory() as db:
        notifications.deliver_due(_svc(client), db, now)
        db.commit()


def _push_user(client, tz: str = KOLKATA, **user_changes) -> tuple[dict, str, RecordingSender]:
    """A signed-up user with a push-capable device and a recording sender; inactive unless told otherwise."""
    sender = RecordingSender()
    _svc(client).push = sender
    headers = signup(client)
    assert _register(client, headers, tz=tz).json()["push_enabled"] is True
    user_id = _user_id(client, headers)
    _update_user(client, user_id, last_active_at=utcnow() - timedelta(days=30), **user_changes)
    return headers, user_id, sender


# ------------------------------------------------------------------ devices


def test_push_enabled_means_the_server_will_deliver(client):
    headers = signup(client)
    # No APNs configured (NullSender): false even with a token and permission — the app keeps local reminders.
    registered = _register(client, headers)
    assert registered.status_code == 200, registered.text
    assert registered.json()["id"].startswith("dev_") and registered.json()["push_enabled"] is False
    assert client.get("/v1/me", headers=headers).json()["timezone"] == KOLKATA

    _svc(client).push = RecordingSender()
    assert _register(client, headers).json()["push_enabled"] is True
    assert _register(client, headers, authorization="provisional").json()["push_enabled"] is True
    assert _register(client, headers, authorization="denied").json()["push_enabled"] is False
    assert _register(client, headers, token=None).json()["push_enabled"] is False
    assert _register(client, headers, authorization="not_determined").json()["push_enabled"] is False

    bad_tz = _register(client, headers, tz="Mars/Olympus")
    assert bad_tz.status_code == 422 and bad_tz.json()["error"]["code"] == "validation_error"
    assert _register(client, headers, token="not-hex").status_code == 422


def test_a_token_belongs_to_the_latest_install_and_devices_can_be_deleted(client):
    _svc(client).push = RecordingSender()
    first, second = signup(client), signup(client)
    device_id = _register(client, first).json()["id"]
    assert _register(client, second, token=TOKEN.upper()).json()["push_enabled"] is True  # tokens are normalized
    with _svc(client).session_factory() as db:
        device = db.get(Device, device_id)
        assert device.apns_token is None
    assert client.delete(f"/v1/devices/{device_id}", headers=second).status_code == 404
    assert client.delete(f"/v1/devices/{device_id}", headers=first).status_code == 204
    assert client.delete(f"/v1/devices/{device_id}", headers=first).status_code == 404


# ------------------------------------------------------------------ inbox


def test_inbox_list_read_and_opened(client):
    headers = signup(client)
    user_id = _user_id(client, headers)
    base = utcnow() - timedelta(hours=3)
    for index in range(3):
        _notify(client, user_id, category="check_in", title=f"Item {index}", dedupe_key=f"k{index}",
                now=base + timedelta(minutes=index))
    inbox = client.get("/v1/notifications", headers=headers).json()
    assert [n["title"] for n in inbox["items"]] == ["Item 2", "Item 1", "Item 0"] and inbox["unread_count"] == 3
    assert set(inbox["items"][0]) == {"id", "category", "title", "body", "deep_link", "created_at", "read"}
    assert len(client.get("/v1/notifications?limit=2", headers=headers).json()["items"]) == 2

    newest, middle, oldest = (n["id"] for n in inbox["items"])
    assert client.post("/v1/notifications/read", headers=headers, json={"ids": [newest]}).json() == {"unread_count": 2}
    missing = client.post("/v1/notifications/read", headers=headers, json={})
    assert missing.status_code == 422
    assert client.post(f"/v1/notifications/{middle}/opened", headers=headers).status_code == 204
    other = signup(client)
    assert client.post(f"/v1/notifications/{oldest}/opened", headers=other).status_code == 404
    assert client.post("/v1/notifications/read", headers=other, json={"all": True}).json() == {"unread_count": 0}
    assert client.get("/v1/notifications", headers=headers).json()["unread_count"] == 1
    assert client.post("/v1/notifications/read", headers=headers, json={"all": True}).json() == {"unread_count": 0}
    with _svc(client).session_factory() as db:
        opened = db.get(Notification, middle)
        assert opened.opened_at is not None and opened.read_at is not None


def test_dedupe_keys_make_producers_idempotent(client):
    headers = signup(client)
    user_id = _user_id(client, headers)
    assert _notify(client, user_id, category="check_in", dedupe_key="same") is not None
    assert _notify(client, user_id, category="check_in", dedupe_key="same") is None
    assert len(_items(client, user_id)) == 1


def test_test_notification_is_pushed_right_away(client):
    headers, user_id, sender = _push_user(client)
    client.patch("/v1/me", headers=headers, json={"notification_settings": {"quiet_start": "00:00",
                                                                            "quiet_end": "23:59"}})
    response = client.post("/v1/notifications/test", headers=headers)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["category"] == "results" and item["title"] == "Notifications are on" and item["read"] is False
    assert item["deep_link"] == "comlogue://settings/notifications"
    assert len(sender.sent) == 1
    message = sender.sent[0]
    assert message.token == TOKEN and message.environment == "sandbox" and message.badge == 1
    payload = message.payload()
    assert payload["aps"]["alert"] == {"title": "Notifications are on", "body": item["body"]}
    assert payload["aps"]["thread-id"] == "results" and payload["aps"]["sound"] == "default"
    assert payload["deep_link"] == item["deep_link"] and payload["notification_id"] == item["id"]
    assert _items(client, user_id)[0].push_state == "sent"


# ------------------------------------------------------------------ delivery rules


def test_quiet_hours_defer_to_quiet_end_in_the_users_timezone(client):
    _, user_id, sender = _push_user(client)
    late = local_datetime(DAY, time(23, 0), KOLKATA)
    _notify(client, user_id, category="check_in", dedupe_key="late", now=late)
    _deliver(client, late)
    item = _items(client, user_id)[0]
    assert item.push_state == "pending" and not sender.sent
    assert item.deliver_after.replace(tzinfo=None) == local_datetime(DAY + timedelta(days=1), time(8, 0),
                                                                      KOLKATA).replace(tzinfo=None)
    _deliver(client, local_datetime(DAY + timedelta(days=1), time(7, 59), KOLKATA))
    assert not sender.sent
    _deliver(client, local_datetime(DAY + timedelta(days=1), time(8, 1), KOLKATA))
    assert len(sender.sent) == 1 and _items(client, user_id)[0].push_state == "sent"


def test_at_most_two_pushes_per_local_day_and_badge_is_unread_count(client):
    _, user_id, sender = _push_user(client, tz=NEW_YORK)
    noon = local_datetime(DAY, time(12, 0), NEW_YORK)
    for index in range(3):
        _notify(client, user_id, category="check_in", dedupe_key=f"c{index}", now=noon + timedelta(seconds=index))
    _deliver(client, noon + timedelta(minutes=1))
    states = [n.push_state for n in _items(client, user_id)]
    assert states == ["sent", "sent", "skipped"] and _items(client, user_id)[2].push_note == "daily cap"
    assert [m.badge for m in sender.sent] == [3, 3]
    # A new local day resets the cap.
    tomorrow = local_datetime(DAY + timedelta(days=1), time(12, 0), NEW_YORK)
    _notify(client, user_id, category="check_in", dedupe_key="next-day", now=tomorrow)
    _deliver(client, tomorrow)
    assert len(sender.sent) == 3


def test_results_skip_quiet_hours_and_cap_while_the_user_is_waiting(client):
    _, user_id, sender = _push_user(client)
    late = local_datetime(DAY, time(23, 30), KOLKATA)
    _update_user(client, user_id, last_active_at=late - timedelta(minutes=10))
    for index in range(3):
        _notify(client, user_id, category="results", dedupe_key=f"r{index}", now=late)
    _deliver(client, late)
    assert len(sender.sent) == 3
    # Not waiting (inactive for an hour): quiet hours apply to results too.
    _update_user(client, user_id, last_active_at=late - timedelta(hours=1))
    _notify(client, user_id, category="results", dedupe_key="r-late", now=late)
    _deliver(client, late)
    assert len(sender.sent) == 3 and _by_key(client, user_id, "r-late").push_state == "pending"


def test_category_toggles(client):
    headers, user_id, sender = _push_user(client)
    client.patch("/v1/me", headers=headers, json={"notification_settings": {"check_ins": False, "results": False}})
    noon = local_datetime(DAY, time(12, 0), KOLKATA)
    assert _notify(client, user_id, category="check_in", dedupe_key="off", now=noon) is None  # not even the inbox
    results = _notify(client, user_id, category="results", dedupe_key="res", now=noon)
    assert results is not None and results.push_state == "skipped"  # results always reach the inbox
    milestone = _notify(client, user_id, category="milestone", dedupe_key="ms", now=noon)
    assert milestone is None  # milestones follow the results toggle
    _deliver(client, noon)
    assert not sender.sent and len(_items(client, user_id)) == 1


def test_planned_break_allows_only_results_and_event_prep(client):
    headers, user_id, sender = _push_user(client)
    noon = local_datetime(DAY, time(12, 0), KOLKATA)
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        user.practice_settings = {**(user.practice_settings or {}), "paused_until": (DAY + timedelta(days=3)).isoformat()}
        db.commit()
    for category in ("check_in", "nudge", "results", "event_prep"):
        _notify(client, user_id, category=category, dedupe_key=category, now=noon)
    _deliver(client, noon)
    by_category = {n.category: n for n in _items(client, user_id)}
    assert by_category["check_in"].push_state == "skipped" and by_category["check_in"].push_note == "planned break"
    assert by_category["nudge"].push_state == "skipped"
    assert {m.thread_id for m in sender.sent} == {"results", "event_prep"}


def test_rejected_token_disables_the_device_and_server_errors_retry(client):
    headers, user_id, sender = _push_user(client)
    noon = local_datetime(DAY, time(12, 0), KOLKATA)
    sender.responses = [PushResult(ok=False, status=503, reason="ServiceUnavailable", retryable=True)] * 3
    _notify(client, user_id, category="results", dedupe_key="retry", now=noon)
    _deliver(client, noon)
    item = _items(client, user_id)[0]
    assert item.push_state == "pending" and item.push_attempts == 1
    _deliver(client, noon + timedelta(minutes=1))  # not due yet
    assert len(sender.sent) == 1
    _deliver(client, noon + timedelta(minutes=6))
    _deliver(client, noon + timedelta(minutes=20))
    item = _items(client, user_id)[0]
    assert item.push_state == "failed" and item.push_attempts == 3

    sender.responses = [PushResult(ok=False, status=410, reason="Unregistered", invalid_token=True)]
    _notify(client, user_id, category="results", dedupe_key="gone", now=noon)
    _deliver(client, noon + timedelta(minutes=30))
    assert _items(client, user_id)[-1].push_state == "failed"
    with _svc(client).session_factory() as db:
        device = db.scalar(select(Device).where(Device.user_id == user_id))
        assert device.apns_token is None and device.token_invalidated_at is not None
        assert device.last_error == "Unregistered"
    assert _register(client, headers, token=None).json()["push_enabled"] is False


def test_expired_notifications_are_never_pushed(client):
    _, user_id, sender = _push_user(client)
    noon = local_datetime(DAY, time(12, 0), KOLKATA)
    _notify(client, user_id, category="event_prep", dedupe_key="old", now=noon, expires_at=noon + timedelta(hours=1))
    _deliver(client, noon + timedelta(hours=2))
    assert not sender.sent and _items(client, user_id)[0].push_note == "expired"


# ------------------------------------------------------------------ scheduled producers


def _event(client, user_id: str, day: date, title: str = "Placement interview", at: str | None = None) -> str:
    with _svc(client).session_factory() as db:
        event = UpcomingEvent(id=f"evt_{title[:4]}{day.isoformat()}", user_id=user_id, title=title,
                              kind="placement", date=day.isoformat(), time=at, prep=[])
        db.add(event)
        db.commit()
        return event.id


def _tick(client, now: datetime) -> None:
    notifications.tick(_svc(client), now)


def test_event_prep_the_evening_before_and_on_the_day(client):
    _, user_id, sender = _push_user(client)
    event_id = _event(client, user_id, DAY + timedelta(days=1))
    _tick(client, local_datetime(DAY, time(18, 59), KOLKATA))
    assert _items(client, user_id, "event_prep") == []
    _tick(client, local_datetime(DAY, time(19, 5), KOLKATA))
    _tick(client, local_datetime(DAY, time(19, 10), KOLKATA))  # idempotent
    items = _items(client, user_id, "event_prep")
    assert [n.title for n in items] == ["Tomorrow: Placement interview"]
    assert items[0].deep_link == f"comlogue://event/{event_id}"
    assert [m.thread_id for m in sender.sent].count("event_prep") == 1

    _tick(client, local_datetime(DAY + timedelta(days=1), time(8, 5), KOLKATA))
    today = [n for n in _items(client, user_id, "event_prep") if n.title.startswith("Today")]
    assert len(today) == 1 and today[0].interruption_level == "time-sensitive"
    assert sender.sent[-1].interruption_level == "time-sensitive"


def test_event_with_a_time_is_prepped_two_hours_before(client):
    _, user_id, _ = _push_user(client, tz=NEW_YORK)
    _event(client, user_id, DAY, title="Client call", at="15:00")
    _tick(client, local_datetime(DAY, time(12, 30), NEW_YORK))
    assert not _items(client, user_id, "event_prep")
    _tick(client, local_datetime(DAY, time(13, 5), NEW_YORK))
    today = [n for n in _items(client, user_id, "event_prep") if n.title.startswith("Today")]
    assert len(today) == 1 and "At 15:00." in today[0].body


def test_check_in_the_day_after_an_event(client):
    _, user_id, _ = _push_user(client)
    _event(client, user_id, DAY - timedelta(days=1), title="Group discussion")
    _tick(client, local_datetime(DAY, time(18, 0), KOLKATA))
    assert not _items(client, user_id, "check_in")
    _tick(client, local_datetime(DAY, time(19, 5), KOLKATA))
    check_ins = _items(client, user_id, "check_in")
    assert [n.title for n in check_ins] == ["How did Group discussion go?"]


def test_real_life_mission_check_in(client):
    _, user_id, _ = _push_user(client)
    now = local_datetime(DAY, time(11, 0), KOLKATA)
    with _svc(client).session_factory() as db:
        db.add(MissionOpen(user_id=user_id, mission_id="business.m1.real", first_opened_at=now - timedelta(days=3)))
        db.add(MissionOpen(user_id=user_id, mission_id="business.m1.learn", first_opened_at=now - timedelta(days=3)))
        db.commit()
    _tick(client, local_datetime(DAY, time(9, 0), KOLKATA))  # outside the 10:00–20:00 window
    assert not _items(client, user_id, "check_in")
    _tick(client, now)
    items = _items(client, user_id, "check_in")
    assert [n.title for n in items] == ["Did you get to try it?"]
    assert items[0].deep_link == "comlogue://reflect/business.m1.real"


def test_no_real_life_check_in_after_a_reflection(client):
    _, user_id, _ = _push_user(client)
    now = local_datetime(DAY, time(11, 0), KOLKATA)
    with _svc(client).session_factory() as db:
        db.add(MissionOpen(user_id=user_id, mission_id="business.m1.real", first_opened_at=now - timedelta(days=3)))
        db.add(Reflection(id="rfl_t", user_id=user_id, mission_id="business.m1.real", text="Tried it."))
        db.commit()
    _tick(client, now)
    assert not _items(client, user_id, "check_in")


def _nudges(client, user_id: str) -> list[Notification]:
    return _items(client, user_id, "nudge")


def test_nudges_after_3_and_8_quiet_days_then_wait_for_a_return(client):
    created = local_datetime(DAY - timedelta(days=12), time(9, 0), KOLKATA)
    _, user_id, _ = _push_user(client, created_at=created)
    start = DAY - timedelta(days=12)

    def tick_day(offset: int, at: time = time(18, 5)) -> None:
        _tick(client, local_datetime(start + timedelta(days=offset), at, KOLKATA))

    tick_day(2)
    assert not _nudges(client, user_id)
    tick_day(3, time(17, 0))  # before the default 18:00
    assert not _nudges(client, user_id)
    tick_day(3)
    first = _nudges(client, user_id)
    assert [n.title for n in first] == ["Your 60-second rep is ready"]
    assert first[0].deep_link == "comlogue://daily" and "Today:" in first[0].body
    for offset in (4, 5, 6, 7):
        tick_day(offset)
    assert len(_nudges(client, user_id)) == 1  # nothing more until 8 quiet days
    tick_day(8)
    assert [n.title for n in _nudges(client, user_id)][-1] == "Pick up where you left off"
    for offset in (11, 12):
        tick_day(offset)
    assert len(_nudges(client, user_id)) == 2  # two unopened nudges: none until they come back

    # They return (tap the second nudge) on day 12: the count starts again from there.
    with _svc(client).session_factory() as db:
        nudge = db.get(Notification, _nudges(client, user_id)[-1].id)
        nudge.opened_at = local_datetime(start + timedelta(days=12), time(19, 0), KOLKATA)
        db.commit()
    tick_day(14)
    assert len(_nudges(client, user_id)) == 2
    tick_day(15)
    assert len(_nudges(client, user_id)) == 3


def test_nudges_at_most_one_per_72_hours(client):
    created = local_datetime(DAY - timedelta(days=20), time(9, 0), KOLKATA)
    _, user_id, _ = _push_user(client, created_at=created)
    with _svc(client).session_factory() as db:  # returned (practised) 9 days ago: both nudges are due
        db.add(ActivityLog(user_id=user_id, type="daily_rep", title="Rep", minutes=1,
                           created_at=local_datetime(DAY - timedelta(days=9), time(8, 0), KOLKATA)))
        db.commit()
    _tick(client, local_datetime(DAY, time(18, 5), KOLKATA))
    _tick(client, local_datetime(DAY, time(18, 10), KOLKATA))
    _tick(client, local_datetime(DAY + timedelta(days=2), time(18, 5), KOLKATA))
    assert len(_nudges(client, user_id)) == 1
    _tick(client, local_datetime(DAY + timedelta(days=3), time(18, 10), KOLKATA))
    assert len(_nudges(client, user_id)) == 2


def test_no_nudges_on_a_break_without_a_target_or_when_turned_off(client):
    created = local_datetime(DAY - timedelta(days=10), time(9, 0), KOLKATA)
    now = local_datetime(DAY, time(18, 5), KOLKATA)
    headers, user_id, _ = _push_user(client, created_at=created)
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        user.practice_settings = {**(user.practice_settings or {}), "weekly_target": 0}
        db.commit()
    _tick(client, now)
    assert not _nudges(client, user_id)

    headers, user_id, _ = _push_user(client, created_at=created)
    client.patch("/v1/me", headers=headers, json={"notification_settings": {"nudges": False}})
    _tick(client, now)
    assert not _nudges(client, user_id)

    _, user_id, _ = _push_user(client, created_at=created)
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        user.practice_settings = {**(user.practice_settings or {}), "paused_until": (DAY + timedelta(days=2)).isoformat()}
        db.commit()
    _tick(client, now)
    assert not _nudges(client, user_id)


def test_weekly_reveal_on_sunday_evening_when_they_practised(client):
    _, user_id, _ = _push_user(client)
    sunday = DAY + timedelta(days=4)
    assert sunday.weekday() == 6
    _tick(client, local_datetime(sunday, time(18, 5), KOLKATA))
    assert not _items(client, user_id, "weekly_reveal")  # no practice this week
    with _svc(client).session_factory() as db:
        for offset in (0, 2):
            db.add(ActivityLog(user_id=user_id, type="daily_rep", title="Rep", minutes=1.5,
                               created_at=local_datetime(DAY + timedelta(days=offset), time(8, 30), KOLKATA)))
        db.commit()
    _tick(client, local_datetime(sunday, time(17, 0), KOLKATA))
    assert not _items(client, user_id, "weekly_reveal")
    _tick(client, local_datetime(sunday, time(18, 5), KOLKATA))
    _tick(client, local_datetime(sunday, time(19, 0), KOLKATA))
    reveals = _items(client, user_id, "weekly_reveal")
    assert len(reveals) == 1 and reveals[0].body.startswith("2 sessions and 3 min of practice")
    assert reveals[0].interruption_level == "passive" and reveals[0].deep_link == "comlogue://review/weekly"


# ------------------------------------------------------------------ result producers


def test_feedback_and_milestones_notify_only_when_the_app_is_not_in_use(client):
    headers = signup(client)
    user_id = _user_id(client, headers)
    svc = _svc(client)
    _update_user(client, user_id, last_active_at=utcnow())
    with svc.session_factory() as db:
        notifications.feedback_ready(svc, db, user_id, attempt_id="att_1", title="Feedback ready",
                                     deep_link="comlogue://daily")
        progress.award(db, user_id, "first_rep")
        db.commit()
    assert _items(client, user_id) == []

    _update_user(client, user_id, last_active_at=utcnow() - timedelta(minutes=5))
    with svc.session_factory() as db:
        notifications.feedback_ready(svc, db, user_id, attempt_id="att_2", title="Feedback ready",
                                     deep_link="comlogue://daily/2026-11-04")
        progress.award(db, user_id, "reps_10")
        db.commit()
    items = {n.category: n for n in _items(client, user_id)}
    assert items["results"].deep_link == "comlogue://daily/2026-11-04"
    assert items["milestone"].title == "Milestone: 10 daily reps" and items["milestone"].interruption_level == "passive"


def test_recording_states_produce_results_notifications(client):
    headers = signup(client)
    user_id = _user_id(client, headers)
    svc = _svc(client)
    with svc.session_factory() as db:
        recording = Recording(id="rec_t", user_id=user_id, title="Team sync", source="upload",
                              status="needs_speaker_confirmation")
        db.add(recording)
        db.commit()
        notifications.recording_ready(svc, db, recording)
        notifications.recording_ready(svc, db, recording)  # same state twice: one item
        recording.status, recording.completed_at = "complete", utcnow()
        db.commit()
        notifications.recording_ready(svc, db, recording)
        recording.status = "processing"
        notifications.recording_ready(svc, db, recording)  # nothing to say yet
    titles = sorted(n.title for n in _items(client, user_id))
    assert titles == ["Which voice is yours?", "Your feedback on “Team sync” is ready"]
    assert all(n.deep_link == "comlogue://recording/rec_t" for n in _items(client, user_id))


def test_scheduler_thread_starts_and_stops(client):
    scheduler = notifications.NotificationScheduler(_svc(client), interval_seconds=3600)
    scheduler.start()
    scheduler.stop()
    assert scheduler._thread is not None
    scheduler._thread.join(timeout=2)
    assert not scheduler._thread.is_alive()


def test_an_item_another_instance_is_sending_is_left_alone(client):
    _, user_id, sender = _push_user(client)
    noon = local_datetime(DAY, time(12, 0), KOLKATA)
    item = _notify(client, user_id, category="results", dedupe_key="claimed", now=noon)
    with _svc(client).session_factory() as db:
        db.get(Notification, item.id).push_state = "sending"  # claimed by another scheduler
        db.commit()
    _deliver(client, noon)
    assert not sender.sent and _by_key(client, user_id, "claimed").push_state == "sending"


def test_no_event_check_in_once_they_have_reflected(client):
    _, user_id, _ = _push_user(client)
    event_id = _event(client, user_id, DAY - timedelta(days=1), title="Viva")
    with _svc(client).session_factory() as db:
        db.get(UpcomingEvent, event_id).reflection = {"id": "rfl_x", "text": "Went fine.", "went": "well",
                                                      "coach_reply": None, "created_at": "2026-11-03T18:00:00Z"}
        db.commit()
    _tick(client, local_datetime(DAY, time(19, 5), KOLKATA))
    assert not _items(client, user_id, "check_in")
