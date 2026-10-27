"""Upcoming events (interviews, meetings…) with AI-built rehearsal scenarios."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.mock_provider import MockProvider
from ..ai.types import EventPrepRequest, ReflectionRequest
from ..core import AppServices
from ..domain.course import TRACKS
from ..domain.market_content import event_kind
from ..errors import AIUnavailableError, conflict, not_found
from ..ids import new_id
from ..models import UpcomingEvent, User
from ..schemas import EventCreate, PrepItem, ReflectionCreate, ReflectionOut, UpcomingEventOut
from ..timeutil import iso_required, utcnow
from . import progress, users

REFLECTION_FALLBACK = "Thanks for reflecting — noticing what happened is how the next one gets easier."

log = logging.getLogger("comlogue.events")


def to_out(event: UpcomingEvent) -> UpcomingEventOut:
    return UpcomingEventOut(id=event.id, title=event.title, kind=event.kind, date=event.date, notes=event.notes,
                            prep=[PrepItem.model_validate(p) for p in event.prep or []],
                            created_at=iso_required(event.created_at), time=event.time,
                            reflection=ReflectionOut.model_validate(event.reflection) if event.reflection else None)


def create(svc: AppServices, db: Session, user: User, body: EventCreate) -> UpcomingEvent:
    kind = event_kind(body.kind)
    request = EventPrepRequest(language=users.language(user), title=body.title, kind=body.kind,
                               date=body.date, notes=body.notes, goal_title=TRACKS[users.goal_track(user)]["title"],
                               kind_hint=kind.prep_hint if kind else None, market=users.market(user), time=body.time)
    try:
        prep = svc.ai.event_prep(request)
    except AIUnavailableError as exc:
        log.warning("Event prep fell back to templates: %s", exc)
        prep = MockProvider().event_prep(request)
    items = [
        {"id": f"prep_{i}", "title": item.title, "scenario": item.scenario, "partner_role": item.partner_role,
         "difficulty": item.difficulty}
        for i, item in enumerate(prep.items[:3], start=1)
    ]
    event = UpcomingEvent(id=new_id("evt"), user_id=user.id, title=body.title, kind=body.kind, date=body.date,
                          time=body.time, notes=body.notes, prep=items)
    db.add(event)
    db.flush()
    return event


def list_for(db: Session, user: User) -> list[UpcomingEvent]:
    return list(db.scalars(select(UpcomingEvent).where(UpcomingEvent.user_id == user.id).order_by(UpcomingEvent.date)))


def reflect(svc: AppServices, db: Session, user: User, event_id: str, body: ReflectionCreate) -> UpcomingEvent:
    """"How did it go?" once the day has come. The first reflection counts as a real-life practice session."""
    from .course import focus_module  # local import: course imports this package's siblings

    event = db.get(UpcomingEvent, event_id)
    if event is None or event.user_id != user.id:
        raise not_found("Event")
    if event.date > users.today(user).isoformat():
        raise conflict("You can reflect on this once the day has come.")
    kind = event_kind(event.kind)
    try:
        reply = svc.ai.reflection_reply(ReflectionRequest(
            language=users.language(user), mission_title=event.title,
            target_behavior=focus_module(db, user).target_behavior,
            real_life_prompt=kind.prep_hint if kind else event.title, text=body.text, went=body.went,
        )).reply
    except AIUnavailableError:
        reply = REFLECTION_FALLBACK
    first = event.reflection is None
    event.reflection = {"id": (event.reflection or {}).get("id") or new_id("rfl"), "text": body.text,
                        "went": body.went, "coach_reply": reply, "created_at": iso_required(utcnow())}
    if first:
        progress.log_activity(db, user.id, "real_life", event.title, 1.0, f"event:{event.id}")
        progress.award(db, user.id, "first_real_life")
    db.flush()
    return event


def delete(db: Session, user: User, event_id: str) -> None:
    event = db.get(UpcomingEvent, event_id)
    if event is None or event.user_id != user.id:
        raise not_found("Event")
    db.delete(event)
