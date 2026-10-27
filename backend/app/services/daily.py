"""Daily rep: one short speaking prompt a day — the core habit action.

The prompt for a date is chosen once and stored, so reminders can name tomorrow's actual prompt. Selection is
deterministic per user and date and weighted towards what helps this person: the course focus skill, their goal
track and market, lighter social prompts at weekends, seasonal prompts in season, a level that follows how many
reps they've done, and no repeats within 30 days.

Feedback uses the same judging as missions (one target behavior, one change, comparison on retries). A rep
counts as a practice session once per day, on its first assessable attempt; retries are free and unlimited.
"""

from __future__ import annotations

import hashlib
import logging
import random
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.content.daily_prompts import DAILY_PROMPTS
from ..domain.content.schema import DailyPromptDef
from ..domain.market_content import DAILY_PROMPTS_BY_ID, daily_prompts_for
from ..errors import AIUnavailableError, conflict, not_found, validation
from ..ids import new_id
from ..models import ActivityLog, Conversation, DailyAssignment, DailyAttempt, User
from ..schemas import AttemptFeedback, ConversationSetup, DailyRep, DailyRepPreview, MissionAttemptOut
from ..timeutil import iso_required, utcnow
from . import conversations, notifications, progress, users
from . import media as media_service

log = logging.getLogger("comlogue.daily")

COACH = {"name": "Maya", "role": "Your coach", "voice": "marin", "symbol": "sparkles", "color_hex": "#5146E6"}
COACH_CHARACTER = "Maya, a warm and encouraging speaking coach who sets up one short prompt and listens."
COACH_TTS = ("Voice: warm, encouraging coach. Tone: friendly and upbeat, like setting up a quick exercise. "
             "Pace: relaxed and clear. Never sound like an announcer.")
CLOSE_LINE = "Got it — thanks. Let's see how that went."
PAST_DAYS = 30
FUTURE_DAYS = 14
NO_REPEAT_DAYS = 30
LEVEL_WEIGHT = {0: 1.0, 1: 0.55, 2: 0.25}


# ------------------------------------------------------------------ selection


def _rep_count(db: Session, user: User) -> int:
    return int(db.scalar(select(func.count(ActivityLog.id)).where(ActivityLog.user_id == user.id,
                                                                  ActivityLog.type == "daily_rep")) or 0)


def _focus_dimension(db: Session, user: User) -> str | None:
    from .course import focus_module  # local import: course imports this package's siblings

    try:
        return focus_module(db, user).dimension
    except (KeyError, IndexError):
        return None


def _weight(prompt: DailyPromptDef, *, day: date, market: str, focus: str | None, track: str, level: int) -> float:
    weight = 1.0
    if focus and prompt.dimension == focus:
        weight *= 3.0
    if prompt.tracks:
        weight *= 2.0 if track in prompt.tracks else 0.7
    if prompt.months and day.month in prompt.months:
        weight *= 3.0
    if day.weekday() >= 5:
        weight *= 2.5 if prompt.context in ("social", "life") else 0.6
    elif prompt.context in ("work", "career"):
        weight *= 1.3
    if prompt.markets == (market,):
        weight *= 1.5
    return weight * LEVEL_WEIGHT.get(min(2, abs(prompt.level - level)), 0.25)


def _choose(user: User, day: date, *, market: str, focus: str | None, track: str, rep_count: int,
            recent: set[str], exclude: set[str], salt: str = "") -> DailyPromptDef:
    offered = sorted(daily_prompts_for(market) or DAILY_PROMPTS, key=lambda p: p.id)
    candidates = [p for p in offered if p.id not in exclude] or offered
    in_season = [p for p in candidates if not p.months or day.month in p.months] or candidates
    fresh = [p for p in in_season if p.id not in recent] or in_season
    level = 1 if rep_count < 5 else (2 if rep_count < 20 else 3)
    weights = [_weight(p, day=day, market=market, focus=focus, track=track, level=level) for p in fresh]
    seed = int(hashlib.sha256(f"{user.id}:{day.isoformat()}:{salt}".encode()).hexdigest()[:16], 16)
    return random.Random(seed).choices(fresh, weights=weights, k=1)[0]


def _recent_ids(db: Session, user: User, day: date) -> set[str]:
    start, end = (day - timedelta(days=NO_REPEAT_DAYS)).isoformat(), (day + timedelta(days=NO_REPEAT_DAYS)).isoformat()
    rows = db.scalars(select(DailyAssignment.prompt_id).where(
        DailyAssignment.user_id == user.id, DailyAssignment.date >= start, DailyAssignment.date <= end,
        DailyAssignment.date != day.isoformat()))
    return set(rows)


def _pick(db: Session, user: User, day: date, *, exclude: set[str] | None = None, salt: str = "") -> DailyPromptDef:
    return _choose(user, day, market=users.market(user), focus=_focus_dimension(db, user),
                   track=users.goal_track(user), rep_count=_rep_count(db, user), recent=_recent_ids(db, user, day),
                   exclude=exclude or set(), salt=salt)


def assignment(db: Session, user: User, day: date) -> DailyAssignment:
    """The stored assignment for `day`, created (deterministically) on first use."""
    row = db.scalar(select(DailyAssignment).where(DailyAssignment.user_id == user.id,
                                                  DailyAssignment.date == day.isoformat()))
    if row is not None:
        if row.prompt_id not in DAILY_PROMPTS_BY_ID:  # content was removed: pick again
            row.prompt_id = _pick(db, user, day).id
            db.flush()
        return row
    row = DailyAssignment(user_id=user.id, date=day.isoformat(), prompt_id=_pick(db, user, day).id, shuffled=False,
                          created_at=utcnow())
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:  # created concurrently
        row = db.scalar(select(DailyAssignment).where(DailyAssignment.user_id == user.id,
                                                      DailyAssignment.date == day.isoformat()))
        assert row is not None
    return row


def _prompt(row: DailyAssignment) -> DailyPromptDef:
    return DAILY_PROMPTS_BY_ID[row.prompt_id]


# ------------------------------------------------------------------ reading


def parse_day(user: User, value: str, *, allow_past: bool = True) -> date:
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise validation("Dates look like 2026-10-27.") from exc
    today = users.today(user)
    earliest = today - timedelta(days=PAST_DAYS) if allow_past else today
    if not earliest <= day <= today + timedelta(days=FUTURE_DAYS):
        raise not_found("Daily rep")
    return day


def preview(svc: AppServices, db: Session, user: User, day: date) -> DailyRepPreview:
    prompt = _prompt(assignment(db, user, day))
    return DailyRepPreview(date=day.isoformat(), prompt_id=prompt.id, title=prompt.title, prompt=prompt.prompt,
                           dimension=prompt.dimension)


def upcoming(svc: AppServices, db: Session, user: User, days: int) -> list[DailyRepPreview]:
    if not 1 <= days <= FUTURE_DAYS:
        raise validation(f"days must be between 1 and {FUTURE_DAYS}.")
    today = users.today(user)
    return [preview(svc, db, user, today + timedelta(days=offset)) for offset in range(days)]


def _attempts(db: Session, user: User, day: date) -> list[DailyAttempt]:
    return list(db.scalars(select(DailyAttempt).where(DailyAttempt.user_id == user.id,
                                                      DailyAttempt.date == day.isoformat())
                           .order_by(DailyAttempt.attempt_number)))


def attempt_out(svc: AppServices, attempt: DailyAttempt) -> MissionAttemptOut:
    feedback = None
    if attempt.feedback:
        feedback = AttemptFeedback.model_validate(media_service.resolve_media(svc, attempt.feedback))
    return MissionAttemptOut(id=attempt.id, conversation_id=attempt.conversation_id,
                             attempt_number=attempt.attempt_number, quick=False, status=attempt.status,
                             feedback=feedback, created_at=iso_required(attempt.created_at))


def _completed(attempts: list[DailyAttempt]) -> bool:
    return any(a.status == "complete" and (a.feedback or {}).get("assessable") not in (None, "no") for a in attempts)


def rep_out(svc: AppServices, db: Session, user: User, day: date) -> DailyRep:
    existing = db.scalar(select(DailyAssignment).where(DailyAssignment.user_id == user.id,
                                                       DailyAssignment.date == day.isoformat()))
    if existing is None and day < users.today(user):
        raise not_found("Daily rep")  # past days are never assigned retroactively
    row = existing or assignment(db, user, day)
    prompt = _prompt(row)
    attempts = _attempts(db, user, day)
    return DailyRep(
        date=day.isoformat(), prompt_id=prompt.id, title=prompt.title, prompt=prompt.prompt, kind=prompt.kind,
        dimension=prompt.dimension, target_behavior=prompt.target_behavior, tips=list(prompt.tips),
        suggested_seconds=prompt.suggested_seconds, example=prompt.example,
        can_shuffle=day == users.today(user) and not row.shuffled and not attempts,
        completed=_completed(attempts), attempts=[attempt_out(svc, a) for a in attempts],
    )


def shuffle(svc: AppServices, db: Session, user: User) -> DailyRep:
    today = users.today(user)
    row = assignment(db, user, today)
    if row.shuffled or _attempts(db, user, today):
        raise conflict("You can swap today's prompt once, before your first try.")
    row.prompt_id = _pick(db, user, today, exclude={row.prompt_id}, salt="shuffle").id
    row.shuffled = True
    db.flush()
    return rep_out(svc, db, user, today)


# ------------------------------------------------------------------ practising


def create_conversation(svc: AppServices, db: Session, user: User, daily_date: str | None) -> Conversation:
    users.require_analysis_consent(user)
    today = users.today(user)
    day = parse_day(user, daily_date) if daily_date else today
    if not today - timedelta(days=1) <= day <= today:
        raise conflict("You can practise today's rep (or yesterday's, if it's just past midnight).")
    row = assignment(db, user, day)
    prompt = _prompt(row)
    setup = ConversationSetup(
        title=prompt.title, context=f"Focus: {prompt.target_behavior}", target_behavior=prompt.target_behavior,
        suggested_seconds=prompt.suggested_seconds, tips=list(prompt.tips), activity_id=None, mission_id=None,
        persona_id=None, difficulty=None, quick=False,
    )
    conv = Conversation(
        id=new_id("cnv"), user_id=user.id, kind="daily", status="active", awaiting="user", partner=dict(COACH),
        setup=setup.model_dump(mode="json"),
        state={"tts_instructions": COACH_TTS, "character": COACH_CHARACTER, "prompt_id": prompt.id},
        language=users.language(user), max_user_turns=1, demo_mode=svc.demo_mode, daily_date=day.isoformat(),
        participants=[],
    )
    db.add(conv)
    db.flush()
    conversations.add_partner_turn(svc, db, conv, prompt.prompt)
    return conv


def finish(svc: AppServices, db: Session, user: User, conv: Conversation) -> str:
    """Create the attempt for a finished daily conversation (idempotent) and queue its feedback."""
    attempt = db.scalar(select(DailyAttempt).where(DailyAttempt.conversation_id == conv.id))
    if attempt is not None:
        return attempt.id
    day = date.fromisoformat(conv.daily_date or users.today(user).isoformat())
    count = db.scalar(select(func.count(DailyAttempt.id)).where(DailyAttempt.user_id == user.id,
                                                                DailyAttempt.date == day.isoformat())) or 0
    attempt = DailyAttempt(id=new_id("att"), user_id=user.id, date=day.isoformat(),
                           prompt_id=conv.state.get("prompt_id", ""), conversation_id=conv.id,
                           attempt_number=int(count) + 1, status="processing", created_at=utcnow())
    db.add(attempt)
    db.commit()
    assert svc.jobs is not None
    svc.jobs.submit("daily.feedback", attempt.id)
    return attempt.id


def run_feedback_job(svc: AppServices, attempt_id: str) -> None:
    from .course import judge_attempt  # local import: course imports notifications, which imports daily lazily

    db = svc.session_factory()
    try:
        attempt = db.get(DailyAttempt, attempt_id)
        if attempt is None or attempt.status != "processing":
            return
        conv = db.get(Conversation, attempt.conversation_id)
        user = db.get(User, attempt.user_id)
        prompt = DAILY_PROMPTS_BY_ID.get(attempt.prompt_id)
        if conv is None or user is None:
            return
        title = prompt.title if prompt else conv.setup.get("title", "Daily rep")
        target = prompt.target_behavior if prompt else (conv.setup.get("target_behavior") or "")
        previous = db.scalar(select(DailyAttempt).where(
            DailyAttempt.user_id == user.id, DailyAttempt.date == attempt.date,
            DailyAttempt.attempt_number < attempt.attempt_number, DailyAttempt.status == "complete",
        ).order_by(DailyAttempt.attempt_number.desc()))
        already_counted = _completed(_attempts(db, user, date.fromisoformat(attempt.date)))
        try:
            feedback = judge_attempt(svc, db, user, conv, title=title, target_behavior=target, quick=False,
                                     previous=previous)
        except AIUnavailableError as exc:
            log.warning("Daily feedback failed: %s", exc)
            attempt.status = "failed"
            db.commit()
            return
        attempt.feedback = feedback.model_dump(mode="json")
        attempt.status = "complete"
        if feedback.assessable != "no" and not already_counted:
            progress.log_activity(db, user.id, "daily_rep", title, conversations.conversation_minutes(db, conv),
                                  f"daily:{attempt.date}")
        db.commit()
        notifications.feedback_ready(svc, db, user.id, attempt_id=attempt.id,
                                     title="Feedback on today's rep is ready",
                                     deep_link=f"comlogue://daily/{attempt.date}")
    except Exception:
        db.rollback()
        attempt = db.get(DailyAttempt, attempt_id)
        if attempt is not None and attempt.status == "processing":
            attempt.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
