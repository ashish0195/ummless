"""Habit progress: local weeks, weeks on target (breaks skipped), best run, this week's days, welcome back."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models import ActivityLog, User
from app.services import progress
from app.timeutil import local_datetime, utcnow, week_start
from tests.helpers import signup

KOLKATA = "Asia/Kolkata"
MONDAY = date(2026, 11, 2)  # "this week" in these tests
NOW = local_datetime(MONDAY + timedelta(days=3), time(12, 0), KOLKATA)  # Thursday noon


def _user(client, **changes) -> str:
    headers = signup(client)
    user_id = client.get("/v1/me", headers=headers).json()["user_id"]
    with client.app.state.services.session_factory() as db:
        user = db.get(User, user_id)
        user.timezone = KOLKATA
        user.created_at = local_datetime(MONDAY - timedelta(weeks=12), time(9, 0), KOLKATA)
        for key, value in changes.items():
            setattr(user, key, value)
        db.commit()
    return user_id


def _sessions(client, user_id: str, moments: list[datetime], type_: str = "daily_rep", minutes: float = 1.0) -> None:
    with client.app.state.services.session_factory() as db:
        for when in moments:
            db.add(ActivityLog(user_id=user_id, type=type_, title="Session", minutes=minutes, created_at=when))
        db.commit()


def _week(back: int, days: tuple[int, ...] = (0, 2, 4)) -> list[datetime]:
    start = MONDAY - timedelta(weeks=back)
    return [local_datetime(start + timedelta(days=d), time(8, 30), KOLKATA) for d in days]


def _build(client, user_id: str, now: datetime = NOW):
    with client.app.state.services.session_factory() as db:
        return progress.build(db, db.get(User, user_id), now)


def test_weeks_on_target_counts_back_from_last_week_plus_this_week_when_met(client):
    user_id = _user(client)
    _sessions(client, user_id, _week(3) + _week(2) + _week(1))
    practice = _build(client, user_id).practice
    assert practice.weeks_on_target == 3 and practice.best_weeks_on_target == 3
    assert practice.this_week.met is False and practice.this_week.days == []
    _sessions(client, user_id, _week(0, (0, 1, 2)))
    practice = _build(client, user_id).practice
    assert practice.weeks_on_target == 4 and practice.this_week.met is True
    assert practice.this_week.days == [1, 2, 3] and practice.this_week.sessions == 3
    assert practice.reps == 12


def test_a_missed_week_resets_the_run_but_not_the_best(client):
    user_id = _user(client)
    _sessions(client, user_id, _week(6) + _week(5) + _week(4) + _week(3, (0,)) + _week(2) + _week(1))
    practice = _build(client, user_id).practice
    assert practice.weeks_on_target == 2 and practice.best_weeks_on_target == 3


def test_planned_break_weeks_neither_count_nor_break_the_run(client):
    break_start = MONDAY - timedelta(weeks=2)
    user_id = _user(client, practice_settings={
        "weekly_target": 3,
        "breaks": [{"start": (break_start + timedelta(days=1)).isoformat(),
                    "end": (break_start + timedelta(days=5)).isoformat()}],
    })
    _sessions(client, user_id, _week(4) + _week(3) + _week(1))  # nothing during the break week
    practice = _build(client, user_id).practice
    assert practice.weeks_on_target == 3 and practice.best_weeks_on_target == 3


def test_the_current_week_can_still_be_met(client):
    user_id = _user(client)
    _sessions(client, user_id, _week(1))
    _sessions(client, user_id, _week(0, (0,)))
    practice = _build(client, user_id).practice
    assert practice.weeks_on_target == 1 and practice.this_week.days == [1]


def test_local_week_boundary_in_india(client):
    user_id = _user(client)
    # Monday 00:20 in India is Sunday 18:50 UTC: it belongs to this week (Monday), not last week.
    _sessions(client, user_id, [local_datetime(MONDAY, time(0, 20), KOLKATA)])
    practice = _build(client, user_id).practice
    assert practice.this_week.sessions == 1 and practice.this_week.days == [1]


def test_welcome_back_after_a_week_away(client):
    user_id = _user(client)
    _sessions(client, user_id, [NOW - timedelta(days=9)])
    welcome = _build(client, user_id).welcome_back
    assert welcome is not None and welcome.days_away == 9
    assert welcome.message == "Welcome back — your progress is saved. Start with a 60-second rep."
    assert _build(client, user_id, NOW - timedelta(days=4)).welcome_back is None  # only 5 days away then
    _sessions(client, user_id, [NOW - timedelta(minutes=30)])
    assert _build(client, user_id).welcome_back is None  # practised today


def test_weekly_target_and_run_milestones_use_local_weeks(client):
    user_id = _user(client, created_at=utcnow() - timedelta(weeks=4))
    last_monday = week_start(utcnow(), KOLKATA) - timedelta(days=7)
    with client.app.state.services.session_factory() as db:
        for offset in (0, 2, 4):  # last week met the target; this week is met by the reps below
            db.add(ActivityLog(user_id=user_id, type="spar_session", title="S", minutes=30,
                               created_at=local_datetime(last_monday + timedelta(days=offset), time(8, 30), KOLKATA)))
        db.commit()
        for _ in range(3):
            progress.log_activity(db, user_id, "daily_rep", "Rep", 1.0, "daily:x")
        db.commit()
        out = {m.id for m in progress.milestones_out(db, user_id)}
    assert "weeks_on_target_2" in out and "minutes_60" in out and "first_rep" in out
    assert any(m.startswith("weekly_target:") for m in out)
