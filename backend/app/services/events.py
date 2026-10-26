"""Upcoming events (interviews, meetings…) with AI-built rehearsal scenarios."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.mock_provider import MockProvider
from ..ai.types import EventPrepRequest
from ..core import AppServices
from ..domain.course import TRACKS
from ..errors import AIUnavailableError, not_found
from ..ids import new_id
from ..models import UpcomingEvent, User
from ..schemas import EventCreate, PrepItem, UpcomingEventOut
from ..timeutil import iso_required
from . import users

log = logging.getLogger("comlogue.events")


def to_out(event: UpcomingEvent) -> UpcomingEventOut:
    return UpcomingEventOut(id=event.id, title=event.title, kind=event.kind, date=event.date, notes=event.notes,
                            prep=[PrepItem.model_validate(p) for p in event.prep or []],
                            created_at=iso_required(event.created_at))


def create(svc: AppServices, db: Session, user: User, body: EventCreate) -> UpcomingEvent:
    request = EventPrepRequest(language=users.language(user), title=body.title, kind=body.kind, date=body.date,
                               notes=body.notes, goal_title=TRACKS[users.goal_track(user)]["title"])
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
                          notes=body.notes, prep=items)
    db.add(event)
    db.flush()
    return event


def list_for(db: Session, user: User) -> list[UpcomingEvent]:
    return list(db.scalars(select(UpcomingEvent).where(UpcomingEvent.user_id == user.id).order_by(UpcomingEvent.date)))


def delete(db: Session, user: User, event_id: str) -> None:
    event = db.get(UpcomingEvent, event_id)
    if event is None or event.user_id != user.id:
        raise not_found("Event")
    db.delete(event)
