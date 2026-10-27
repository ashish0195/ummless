"""Pilot metrics from the spec, with engagement and learning reported separately.

The spec asks the pilot to test "first-task completion, voluntary retries, return for the next mission, real-life
application, and improvement on a fresh scenario", and to "treat engagement and learning as separate outcomes".
The habit loop adds daily-rep completion and push-to-session conversion (engagement, never learning).
People with seeded demo data are left out. Print a report with `python scripts/pilot_metrics.py`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    ActivityLog,
    DailyAttempt,
    DimensionEstimate,
    FeedbackReport,
    MissionAttempt,
    MissionProgress,
    Notification,
    Reflection,
    UpcomingEvent,
    User,
)
from ..timeutil import as_utc, iso

PUSH_SESSION_WINDOW = timedelta(hours=2)


def _rate(numerator: int, denominator: int, definition: str) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 3) if denominator else None,
        "definition": definition,
    }


def _cohort(db: Session, since: datetime | None, until: datetime | None) -> set[str]:
    # Filtered in Python: SQLite hands back naive datetimes, and a pilot has at most a few thousand people.
    cohort = set()
    for user_id, created_at, demo_seed in db.execute(select(User.id, User.created_at, User.demo_seed)):
        joined = as_utc(created_at)
        if demo_seed or (since and joined < since) or (until and joined >= until):
            continue
        cohort.add(user_id)
    return cohort


def compute(db: Session, since: datetime | None = None, until: datetime | None = None) -> dict[str, Any]:
    """Metrics for the people who joined in [since, until). Both bounds are optional and UTC."""
    cohort = _cohort(db, since, until)

    attempts = [a for a in db.scalars(select(MissionAttempt)) if a.user_id in cohort]
    completions = [p for p in db.scalars(select(MissionProgress)) if p.user_id in cohort]
    reflectors = {r.user_id for r in db.scalars(select(Reflection)) if r.user_id in cohort}
    # "How did the interview go?" on a real event is real-life application too.
    reflectors |= {e.user_id for e in db.scalars(select(UpcomingEvent)) if e.reflection and e.user_id in cohort}

    started = {a.user_id for a in attempts}
    got_feedback = {a.user_id for a in attempts if a.status == "complete"}
    retried = {a.user_id for a in attempts if a.attempt_number >= 2 and a.user_id in got_feedback}

    first_completion: dict[str, MissionProgress] = {}
    for progress in sorted(completions, key=lambda p: as_utc(p.completed_at)):
        first_completion.setdefault(progress.user_id, progress)
    returned = {
        a.user_id for a in attempts
        if a.user_id in first_completion
        and a.mission_id != first_completion[a.user_id].mission_id
        and as_utc(a.created_at).date() > as_utc(first_completion[a.user_id].completed_at).date()
    }

    # Learning: the first estimate of a skill against the latest one from a different conversation. Practice
    # attempts never create estimates, so a later estimate always comes from a fresh scenario.
    by_skill: dict[tuple[str, str], list[DimensionEstimate]] = defaultdict(list)
    for estimate in db.scalars(select(DimensionEstimate)):
        if estimate.user_id in cohort:
            by_skill[(estimate.user_id, estimate.dimension)].append(estimate)
    changes: Counter[str] = Counter()
    for estimates in by_skill.values():
        estimates.sort(key=lambda e: as_utc(e.assessed_at))
        first = estimates[0]
        later = [e for e in estimates if e.source_id != first.source_id]
        if not later:
            continue
        latest = later[-1]
        changes["higher" if latest.level > first.level else "lower" if latest.level < first.level else "same"] += 1
    pairs = sum(changes.values())

    reports = [r for r in db.scalars(select(FeedbackReport)) if r.user_id in cohort]

    # Habit loop. A rep "day" is a person and a date with at least one attempt.
    rep_days: dict[tuple[str, str], bool] = {}
    for attempt in db.scalars(select(DailyAttempt)):
        if attempt.user_id not in cohort:
            continue
        done = attempt.status == "complete" and (attempt.feedback or {}).get("assessable") not in (None, "no")
        key = (attempt.user_id, attempt.date)
        rep_days[key] = rep_days.get(key, False) or done
    from .progress import SESSION_TYPES  # local import: progress pulls in the notification producers

    sessions: dict[str, list[datetime]] = defaultdict(list)
    for log in db.scalars(select(ActivityLog).where(ActivityLog.type.in_(SESSION_TYPES))):
        if log.user_id in cohort:
            sessions[log.user_id].append(as_utc(log.created_at))
    pushed = opened = tapped_total = converted = 0
    for item in db.scalars(select(Notification)):
        if item.user_id not in cohort:
            continue
        if item.push_state == "sent":
            pushed += 1
            opened += item.opened_at is not None
        if item.opened_at is not None:
            tapped_total += 1
            tapped = as_utc(item.opened_at)
            if any(tapped <= when <= tapped + PUSH_SESSION_WINDOW for when in sessions[item.user_id]):
                converted += 1

    return {
        "window": {"since": iso(since), "until": iso(until)},
        "people": len(cohort),
        "engagement": {
            "first_task_completion": _rate(
                len(got_feedback), len(started),
                "Of people who started a mission attempt, the share who finished one and got feedback."),
            "voluntary_retries": _rate(
                len(retried), len(got_feedback),
                "Of people who got feedback on an attempt, the share who chose to try the same mission again."),
            "return_for_next_mission": _rate(
                len(returned), len(first_completion),
                "Of people who completed a mission, the share who started a different mission on a later day."),
            "real_life_application": _rate(
                len(reflectors & set(first_completion)), len(first_completion),
                "Of people who completed a mission, the share who logged how a real conversation went (a real-life "
                "mission or an event they'd prepared for)."),
            "daily_rep_completion": _rate(
                sum(1 for done in rep_days.values() if done), len(rep_days),
                "Of the days someone started a daily rep, the share where they finished it and got feedback."),
            "push_open_rate": _rate(
                opened, pushed, "Of pushes delivered, the share the person tapped."),
            "push_to_session": _rate(
                converted, tapped_total,
                "Of notifications tapped (push or inbox), the share followed by a practice session within 2 hours."),
        },
        "learning": {
            "improvement_on_fresh_scenario": {
                "skills_compared": pairs,
                "higher": changes["higher"],
                "same": changes["same"],
                "lower": changes["lower"],
                "rate": round(changes["higher"] / pairs, 3) if pairs else None,
                "definition": ("For each person and skill with estimates from at least two different conversations, "
                               "the first level compared with the latest one."),
            },
        },
        "calibration": {
            "feedback_reports": len(reports),
            "by_reason": dict(Counter(r.reason for r in reports).most_common()),
            "by_target": dict(Counter(r.target_type for r in reports).most_common()),
        },
    }
