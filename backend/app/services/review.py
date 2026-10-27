"""Weekly review ("weekly reveal").

Skill estimates change only when new, assessable recordings or AI assessments happened this week;
otherwise prior estimates are kept. Practice stats are reported separately from skill.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.mock_provider import MockProvider
from ..ai.types import WeeklyRequest
from ..core import AppServices
from ..domain.course import MISSIONS, MODULES
from ..domain.dimensions import DIMENSIONS
from ..errors import AIUnavailableError
from ..models import (
    ActivityLog,
    DimensionEstimate,
    MissionAttempt,
    User,
    WeeklyReviewCache,
)
from ..schemas import BeforeAfter, FocusOption, SkillUpdate, WeeklyReview, WeekPractice
from ..timeutil import as_utc, week_bounds, week_start
from . import course as course_service
from . import progress, users

log = logging.getLogger("comlogue.review")


def build(svc: AppServices, db: Session, user: User) -> WeeklyReview:
    start, end = week_bounds(tz=users.timezone(user))
    logs = [log_ for log_ in db.scalars(select(ActivityLog).where(ActivityLog.user_id == user.id))
            if start <= as_utc(log_.created_at) < end]
    sessions = [entry for entry in logs if entry.type in progress.SESSION_TYPES]
    attempts = [a for a in db.scalars(select(MissionAttempt).where(MissionAttempt.user_id == user.id))
                if start <= as_utc(a.created_at) < end]
    target = users.practice_settings(user)["weekly_target"]
    practice = WeekPractice(
        sessions=len(sessions),
        missions_completed=sum(1 for e in logs if e.type == "mission_completed"),
        attempts=len(attempts),
        retries=sum(1 for a in attempts if a.attempt_number >= 2),
        real_life_attempts=sum(1 for e in logs if e.type == "real_life"),
        minutes=int(round(sum(e.minutes for e in sessions))),
        target=target,
        met_target=len(sessions) >= target,
    )

    new_estimates = [e for e in db.scalars(select(DimensionEstimate).where(DimensionEstimate.user_id == user.id))
                     if start <= as_utc(e.assessed_at) < end]
    skill_updates = [
        SkillUpdate(dimension=e.dimension, change="new_estimate",
                    note=f"New {e.status} estimate from {e.context_label}.")
        for e in sorted(new_estimates, key=lambda e: e.dimension)
    ]
    if skill_updates:
        evidence_note = "Skill estimates below changed only where a new conversation gave us evidence."
    else:
        evidence_note = ("No new comparable recordings this week, so your skill estimates stay as they were. "
                         "Practice still counts — it just isn't the same as audio-verified evidence.")

    before_after = None
    by_mission: dict[str, list[MissionAttempt]] = {}
    for attempt in sorted(attempts, key=lambda a: a.attempt_number):
        if attempt.feedback and attempt.feedback.get("where"):
            by_mission.setdefault(attempt.mission_id, []).append(attempt)
    for mission_id, items in by_mission.items():
        if len(items) >= 2:
            before_after = BeforeAfter(
                mission_title=MISSIONS[mission_id].title,
                before_quote=items[0].feedback["where"]["quote"],
                after_quote=items[-1].feedback["where"]["quote"],
                note=course_service.COMPARISON_NOTE,
            )
            break

    course = course_service.build_course(svc, db, user)
    options = [FocusOption(module_id=m.id, title=m.title,
                           reason=f"Practice {DIMENSIONS[m.dimension].title.lower()}: {m.target_behavior}")
               for m in course.modules if m.status != "completed" and m.id != course.focus_module_id][:3]
    focus_title = MODULES[course.focus_module_id].title

    facts = [
        f"{practice.sessions} practice session(s) this week; weekly target {target}.",
        f"{practice.attempts} mission attempt(s), {practice.retries} retr{'y' if practice.retries == 1 else 'ies'}.",
    ]
    if practice.real_life_attempts:
        facts.append(f"{practice.real_life_attempts} real-life mission(s).")
    if before_after:
        facts.append(f"Retried '{before_after.mission_title}' against the same target.")
    if skill_updates:
        facts.append("New evidence for: " + ", ".join(DIMENSIONS[s.dimension].title for s in skill_updates) + ".")
    signature = hashlib.sha256("|".join(facts + [focus_title]).encode()).hexdigest()[:40]
    cached = db.scalar(select(WeeklyReviewCache).where(WeeklyReviewCache.user_id == user.id,
                                                       WeeklyReviewCache.week_start == week_start(start, users.timezone(user)).isoformat()))
    if cached is not None and cached.signature == signature:
        highlights, message = cached.payload["highlights"], cached.payload["message"]
    else:
        request = WeeklyRequest(language=users.language(user), facts=facts, focus_title=focus_title)
        try:
            judgement = svc.ai.weekly(request) if logs else MockProvider().weekly(request)
        except AIUnavailableError:
            judgement = MockProvider().weekly(request)
        highlights, message = judgement.highlights[:3], judgement.message
        if not logs:
            message = "A quiet week — that's okay. One short session is all it takes to pick up again."
        if cached is None:
            db.add(WeeklyReviewCache(user_id=user.id, week_start=week_start(start, users.timezone(user)).isoformat(),
                                     signature=signature,
                                     payload={"highlights": highlights, "message": message}))
        else:
            cached.signature = signature
            cached.payload = {"highlights": highlights, "message": message}
        db.flush()

    first_day = week_start(start, users.timezone(user))
    return WeeklyReview(
        week_start=first_day.isoformat(), week_end=(first_day + timedelta(days=6)).isoformat(),
        practice=practice, highlights=highlights, before_after=before_after, skill_updates=skill_updates,
        evidence_note=evidence_note, next_focus_options=options,
        milestones=progress.milestones_out(db, user.id, since=start), message=message,
    )
