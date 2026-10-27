"""Practice progress, the weekly run and milestones. Practice completion is tracked separately from skill.

Weeks run Monday–Sunday in the user's timezone. "Weeks on target" counts consecutive weeks that met the user's own
weekly target; weeks overlapping a planned break neither count nor break the run. Nothing here is a skill score.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ActivityLog, Milestone, MissionProgress, User
from ..schemas import MilestoneOut, PracticeTotals, Progress, RecentItem, ThisWeek, WelcomeBack
from ..timeutil import as_utc, iso_required, local_date, utcnow, week_start
from . import users

SESSION_TYPES = ("assessment", "recording", "mission_attempt", "spar_session", "real_life", "daily_rep",
                 "group_session")
WELCOME_BACK_DAYS = 7
WELCOME_BACK_MESSAGE = "Welcome back — your progress is saved. Start with a 1-minute practice."

MILESTONES: dict[str, tuple[str, str]] = {
    "first_conversation": ("First conversation", "You finished your first AI conversation."),
    "first_profile": ("First insight", "Your communication web has its first evidence-backed point."),
    "first_upload": ("First real conversation", "You added a real conversation for feedback."),
    "first_mission": ("First mission complete", "One target behavior, practiced and done."),
    "first_retry": ("Tried it again", "You retried a mission — that's how skills stick."),
    "first_real_life": ("First real-life attempt", "You used a skill in an actual conversation."),
    "new_scenario": ("Skill transferred", "You hit the target in a new scenario, not just a memorized one."),
    "first_spar": ("First spar", "You held your ground with an AI sparring partner."),
    "weekly_target": ("Weekly target met", "You hit your practice target this week."),
    "first_rep": ("First practice", "One prompt, one minute — that's how the habit starts."),
    "reps_10": ("10 practices", "Ten done. Small and steady is how speaking gets easier."),
    "reps_30": ("30 practices", "Thirty done. Speaking practice is part of your routine now."),
    "weeks_on_target_2": ("2 weeks on target", "Two weeks in a row at the practice target you chose."),
    "weeks_on_target_4": ("4 weeks on target", "A month of meeting your own target."),
    "weeks_on_target_8": ("8 weeks on target", "Two months of steady practice."),
    "weeks_on_target_12": ("12 weeks on target", "Three months — practice is part of your week now."),
    "minutes_60": ("An hour of practice", "Sixty minutes of speaking practice, one session at a time."),
    "first_group": ("First group discussion", "You found your way into a group conversation."),
}
RUN_MILESTONES = (2, 4, 8, 12)
REP_MILESTONES = ((1, "first_rep"), (10, "reps_10"), (30, "reps_30"))


def award(db: Session, user_id: str, milestone_key: str, suffix: str | None = None) -> bool:
    milestone_id = f"{milestone_key}:{suffix}" if suffix else milestone_key
    exists = db.scalar(select(Milestone).where(Milestone.user_id == user_id, Milestone.milestone_id == milestone_id))
    if exists is not None:
        return False
    title, detail = MILESTONES[milestone_key]
    db.add(Milestone(user_id=user_id, milestone_id=milestone_id, title=title, detail=detail))
    db.flush()
    from . import notifications  # local import: notifications reads progress

    notifications.milestone_earned(db, user_id, milestone_id, title, detail)
    return True


def _session_logs(db: Session, user_id: str) -> list[ActivityLog]:
    return list(db.scalars(select(ActivityLog).where(ActivityLog.user_id == user_id,
                                                      ActivityLog.type.in_(SESSION_TYPES))
                           .order_by(ActivityLog.created_at)))


def log_activity(db: Session, user_id: str, type_: str, title: str, minutes: float, ref_id: str | None) -> None:
    db.add(ActivityLog(user_id=user_id, type=type_, title=title[:200], minutes=max(0.0, minutes), ref_id=ref_id))
    db.flush()
    if type_ not in SESSION_TYPES:
        return
    user = db.get(User, user_id)
    if user is None:
        return
    tz = users.timezone(user)
    target = users.practice_settings(user)["weekly_target"]
    logs = _session_logs(db, user_id)
    this_week = week_start(utcnow(), tz)
    if sum(1 for log in logs if week_start(log.created_at, tz) == this_week) >= target:
        award(db, user_id, "weekly_target", this_week.isoformat())
    current, _ = weekly_run(user, logs)
    for weeks in RUN_MILESTONES:
        if current >= weeks:
            award(db, user_id, f"weeks_on_target_{weeks}")
    if sum(log.minutes for log in logs) >= 60:
        award(db, user_id, "minutes_60")
    if type_ == "daily_rep":
        reps = sum(1 for log in logs if log.type == "daily_rep")
        for count, key in REP_MILESTONES:
            if reps >= count:
                award(db, user_id, key)


def weekly_run(user: User, logs: list[ActivityLog], now: datetime | None = None) -> tuple[int, int]:
    """(current run, best run) of weeks meeting the weekly target; planned-break weeks are skipped."""
    tz = users.timezone(user)
    target = users.practice_settings(user)["weekly_target"]
    this_week = week_start(now or utcnow(), tz)
    per_week = Counter(week_start(log.created_at, tz) for log in logs)
    breaks = users.breaks(user)
    earliest = min([this_week, week_start(user.created_at, tz), *per_week.keys()])

    def on_break(start: date) -> bool:
        end = start + timedelta(days=6)
        return any(not (b_end < start or b_start > end) for b_start, b_end in breaks)

    current = 0
    week = this_week - timedelta(days=7)
    while week >= earliest:
        if on_break(week):
            week -= timedelta(days=7)
            continue
        if per_week[week] < target:
            break
        current += 1
        week -= timedelta(days=7)
    if per_week[this_week] >= target:
        current += 1

    best = running = 0
    week = earliest
    while week <= this_week:
        if not on_break(week):
            if per_week[week] >= target:
                running += 1
                best = max(best, running)
            elif week != this_week:  # the current week can still be met
                running = 0
        week += timedelta(days=7)
    return current, max(best, current)


def milestones_out(db: Session, user_id: str, since=None) -> list[MilestoneOut]:
    query = select(Milestone).where(Milestone.user_id == user_id).order_by(Milestone.achieved_at.desc())
    rows = list(db.scalars(query))
    if since is not None:
        rows = [m for m in rows if as_utc(m.achieved_at) >= since]
    return [MilestoneOut(id=m.milestone_id, title=m.title, detail=m.detail, achieved_at=iso_required(m.achieved_at))
            for m in rows]


def welcome_back(user: User, logs: list[ActivityLog], now: datetime | None = None) -> WelcomeBack | None:
    """Shown when the last session was a week or more ago (gone again once they practise today)."""
    tz = users.timezone(user)
    today = local_date(now or utcnow(), tz)
    days = [local_date(log.created_at, tz) for log in logs]
    if not days:
        return None
    days_away = (today - max(days)).days
    if days_away < WELCOME_BACK_DAYS:
        return None
    return WelcomeBack(days_away=days_away, message=WELCOME_BACK_MESSAGE)


def build(db: Session, user: User, now: datetime | None = None) -> Progress:
    now = now or utcnow()
    tz = users.timezone(user)
    all_logs = list(db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id)
                               .order_by(ActivityLog.created_at.desc())))
    sessions = sorted((log for log in all_logs if log.type in SESSION_TYPES), key=lambda log: as_utc(log.created_at))
    this_week = week_start(now, tz)
    week_sessions = [log for log in sessions if week_start(log.created_at, tz) == this_week]
    target = users.practice_settings(user)["weekly_target"]
    days = sorted({local_date(log.created_at, tz).isoweekday() for log in week_sessions})
    missions_completed = db.scalar(select(func.count(MissionProgress.id)).where(MissionProgress.user_id == user.id)) or 0
    current, best = weekly_run(user, sessions, now)
    return Progress(
        practice=PracticeTotals(
            total_sessions=len(sessions),
            missions_completed=int(missions_completed),
            minutes=int(round(sum(log.minutes for log in sessions))),
            weeks_active=len({week_start(log.created_at, tz) for log in sessions}),
            this_week=ThisWeek(sessions=len(week_sessions), target=target, days=days,
                               met=len(week_sessions) >= target),
            reps=sum(1 for log in sessions if log.type == "daily_rep"),
            weeks_on_target=current,
            best_weeks_on_target=best,
            paused_until=users.paused_until(user, local_date(now, tz)),
        ),
        milestones=milestones_out(db, user.id),
        recent=[RecentItem(type=log.type, title=log.title, created_at=iso_required(log.created_at))
                for log in all_logs[:10]],
        welcome_back=welcome_back(user, sessions, now),
    )


def sessions_between(db: Session, user_id: str, start: datetime, end: datetime) -> list[ActivityLog]:
    return [log for log in _session_logs(db, user_id) if start <= as_utc(log.created_at) < end]
