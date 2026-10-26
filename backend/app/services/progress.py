"""Practice progress and milestones. Practice completion is tracked separately from demonstrated skill."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ActivityLog, Milestone, MissionProgress, User
from ..schemas import MilestoneOut, PracticeTotals, Progress, RecentItem, ThisWeek
from ..timeutil import as_utc, iso_required, utcnow, week_bounds, week_start
from . import users

SESSION_TYPES = ("assessment", "recording", "mission_attempt", "spar_session", "real_life")

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
}


def award(db: Session, user_id: str, milestone_key: str, suffix: str | None = None) -> bool:
    milestone_id = f"{milestone_key}:{suffix}" if suffix else milestone_key
    exists = db.scalar(select(Milestone).where(Milestone.user_id == user_id, Milestone.milestone_id == milestone_id))
    if exists is not None:
        return False
    title, detail = MILESTONES[milestone_key]
    db.add(Milestone(user_id=user_id, milestone_id=milestone_id, title=title, detail=detail))
    db.flush()
    return True


def log_activity(db: Session, user_id: str, type_: str, title: str, minutes: float, ref_id: str | None) -> None:
    db.add(ActivityLog(user_id=user_id, type=type_, title=title[:200], minutes=max(0.0, minutes), ref_id=ref_id))
    db.flush()
    if type_ in SESSION_TYPES:
        user = db.get(User, user_id)
        if user is not None:
            target = users.practice_settings(user)["weekly_target"]
            start, end = week_bounds()
            count = db.scalar(select(func.count(ActivityLog.id)).where(
                ActivityLog.user_id == user_id, ActivityLog.type.in_(SESSION_TYPES),
                ActivityLog.created_at >= start, ActivityLog.created_at < end)) or 0
            if count >= target:
                award(db, user_id, "weekly_target", week_start().isoformat())


def milestones_out(db: Session, user_id: str, since=None) -> list[MilestoneOut]:
    query = select(Milestone).where(Milestone.user_id == user_id).order_by(Milestone.achieved_at.desc())
    rows = list(db.scalars(query))
    if since is not None:
        rows = [m for m in rows if as_utc(m.achieved_at) >= since]
    return [MilestoneOut(id=m.milestone_id, title=m.title, detail=m.detail, achieved_at=iso_required(m.achieved_at))
            for m in rows]


def build(db: Session, user: User) -> Progress:
    logs = list(db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id).order_by(ActivityLog.created_at.desc())))
    sessions = [log for log in logs if log.type in SESSION_TYPES]
    start, end = week_bounds()
    this_week = sum(1 for log in sessions if start <= as_utc(log.created_at) < end)
    weeks = {week_start(log.created_at) for log in sessions}
    missions_completed = db.scalar(select(func.count(MissionProgress.id)).where(MissionProgress.user_id == user.id)) or 0
    target = users.practice_settings(user)["weekly_target"]
    return Progress(
        practice=PracticeTotals(
            total_sessions=len(sessions),
            missions_completed=int(missions_completed),
            minutes=int(round(sum(log.minutes for log in logs if log.type in SESSION_TYPES))),
            weeks_active=len(weeks),
            this_week=ThisWeek(sessions=this_week, target=target),
        ),
        milestones=milestones_out(db, user.id),
        recent=[RecentItem(type=log.type, title=log.title, created_at=iso_required(log.created_at)) for log in logs[:10]],
    )


def now_week_bounds():
    return week_bounds(utcnow())
