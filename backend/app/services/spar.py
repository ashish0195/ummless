"""Spar: free-form roleplay with personas (or a described scenario), coach whispers and a report."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.types import CustomScenarioRequest, SparRequest
from ..core import AppServices
from ..domain.personas import CUSTOM_PERSONA_COLOR, PERSONAS
from ..errors import AIUnavailableError, not_found, subscription_required, validation
from ..models import Conversation, SparReport, UpcomingEvent, User
from ..schemas import (
    ConversationCreate,
    MomentumPoint,
    Observation,
    Persona,
    PersonaList,
    RewriteMoment,
    SparOutcome,
    SparReportOut,
    SparSession,
)
from ..timeutil import iso_required, utcnow
from . import conversations, progress, users
from . import media as media_service
from .analysis import find_unit

log = logging.getLogger("comlogue.spar")

CUSTOM_TTS = "Voice: natural, realistic for the role. Pace: everyday conversation."


def personas() -> PersonaList:
    return PersonaList(personas=[
        Persona(id=p.id, name=p.name, title=p.title, scenario=p.scenario, description=p.description,
                default_difficulty=p.default_difficulty, symbol=p.symbol, color_hex=p.color_hex, is_free=p.is_free)
        for p in PERSONAS.values()
    ])


def _check_free_limits(svc: AppServices, db: Session, user: User, *, persona_free: bool) -> None:
    if users.is_pro(user):
        return
    if not persona_free:
        raise subscription_required("This sparring partner is part of Comlogue Pro.")
    since = utcnow() - timedelta(days=7)
    count = db.scalar(select(func.count(Conversation.id)).where(
        Conversation.user_id == user.id, Conversation.kind == "spar", Conversation.created_at >= since)) or 0
    if count >= svc.settings.free_spar_per_week:
        raise subscription_required("You've used this week's free spar. Pro includes unlimited sparring.")


def create(svc: AppServices, db: Session, user: User, body: ConversationCreate) -> Conversation:
    users.require_analysis_consent(user)
    language = users.language(user)
    if body.persona_id:
        persona = PERSONAS.get(body.persona_id)
        if persona is None:
            raise not_found("Persona")
        _check_free_limits(svc, db, user, persona_free=persona.is_free)
        difficulty = body.difficulty or persona.default_difficulty
        return conversations.create_spar_conversation(
            svc, db, user, language=language, title=persona.scenario,
            partner={"name": persona.name, "role": persona.title, "voice": persona.voice, "symbol": persona.symbol,
                     "color_hex": persona.color_hex},
            opening=persona.opening, context=persona.description, character=persona.character,
            win_condition=persona.win_condition, difficulty=difficulty, tts_instructions=persona.tts_instructions,
            persona_id=persona.id, max_user_turns=persona.max_user_turns,
        )
    scenario: str | None = body.custom_scenario
    difficulty = body.difficulty or "real"
    extra: dict = {}
    if body.event_id:
        event = db.get(UpcomingEvent, body.event_id)
        if event is None or event.user_id != user.id:
            raise not_found("Event")
        item = next((p for p in event.prep or [] if p.get("id") == body.prep_id), None)
        if item is None:
            raise not_found("Prep item")
        scenario = f"{item['scenario']} (Partner: {item['partner_role']}.)"
        difficulty = body.difficulty or item.get("difficulty", "real")
        extra = {"event_id": event.id, "prep_id": item["id"]}
    if not scenario or not scenario.strip():
        raise validation("Pick a persona or describe a scenario.")
    _check_free_limits(svc, db, user, persona_free=False)
    try:
        custom = svc.ai.custom_scenario(CustomScenarioRequest(language=language, scenario=scenario.strip(),
                                                              difficulty=difficulty))
    except AIUnavailableError:
        from ..ai.mock_provider import MockProvider

        custom = MockProvider().custom_scenario(CustomScenarioRequest(language=language, scenario=scenario,
                                                                      difficulty=difficulty))
    conv = conversations.create_spar_conversation(
        svc, db, user, language=language, title=scenario.strip()[:80],
        partner={"name": custom.partner_name, "role": custom.partner_role, "voice": "marin",
                 "symbol": "person.wave.2", "color_hex": CUSTOM_PERSONA_COLOR},
        opening=custom.opening_line, context=custom.context, character=custom.character,
        win_condition=custom.win_condition, difficulty=difficulty, tts_instructions=CUSTOM_TTS, persona_id=None,
        max_user_turns=6, extra_state=extra,
    )
    conv.event_id = extra.get("event_id")
    conv.prep_id = extra.get("prep_id")
    return conv


def sessions(db: Session, user: User) -> list[SparSession]:
    rows = list(db.scalars(select(Conversation).where(Conversation.user_id == user.id, Conversation.kind == "spar")
                           .order_by(Conversation.created_at.desc()).limit(50)))
    out = []
    for conv in rows:
        report = db.get(SparReport, conv.id)
        outcome = ((report.report or {}).get("outcome") or {}).get("label") if report and report.report else None
        out.append(SparSession(
            conversation_id=conv.id, title=conv.setup.get("title", "Spar"), persona_name=conv.partner.get("name", ""),
            difficulty=conv.difficulty or "real", created_at=iso_required(conv.created_at),
            status=report.status if report else conv.status, outcome_label=outcome or conv.state.get("outcome_label"),
        ))
    return out


def report_out(svc: AppServices, db: Session, user: User, conversation_id: str) -> SparReportOut:
    conv = conversations.get_owned(db, user, conversation_id)
    if conv.kind != "spar":
        raise not_found("Spar report")
    report = db.get(SparReport, conv.id)
    title = conv.setup.get("title", "Spar")
    if report is None:
        raise not_found("Spar report")
    if report.status != "complete" or not report.report:
        return SparReportOut(conversation_id=conv.id, status=report.status, title=title, outcome=None, momentum=[],
                             moments=[], observations=[], next_step=None)
    return SparReportOut.model_validate(media_service.resolve_media(svc, report.report))


def run_report_job(svc: AppServices, conversation_id: str) -> None:
    db = svc.session_factory()
    try:
        report = db.get(SparReport, conversation_id)
        conv = db.get(Conversation, conversation_id)
        if report is None or conv is None or report.status != "processing":
            return
        turns = conversations.turns_of(db, conv)
        units = conversations.units_for(conv, turns)
        user_units = [u for u in units if u.usable_user]
        momentum = [(t.index, float(t.momentum)) for t in turns if t.speaker == "partner" and t.momentum is not None]
        title = conv.setup.get("title", "Spar")
        if not user_units:
            report.report = SparReportOut(
                conversation_id=conv.id, status="complete", title=title,
                outcome=SparOutcome(label="Not enough to review",
                                    detail="We didn't hear enough of your side to write a report. Nothing was scored."),
                momentum=[], moments=[], observations=[], next_step="Try again somewhere quiet.",
            ).model_dump(mode="json")
            report.status = "complete"
            db.commit()
            return
        try:
            judgement = svc.ai.spar_report(SparRequest(
                language=conv.language, persona_name=conv.partner.get("name", "Partner"),
                persona_title=conv.partner.get("role", ""), scenario=title, difficulty=conv.difficulty or "real",
                win_condition=conv.state.get("win_condition", ""), units=units, momentum=momentum,
            ))
        except AIUnavailableError as exc:
            log.warning("Spar report failed: %s", exc)
            report.status = "failed"
            db.commit()
            return
        units_by_id = {u.uid: u for u in units}
        notes = {n.turn_index: n.note for n in judgement.momentum_notes}
        moments = []
        for rewrite in judgement.moments[:3]:
            unit = find_unit(units_by_id, user_units, rewrite.segment_id, rewrite.you_said)
            if unit is None:
                continue
            clip_id = media_service.clip(svc, db, user_id=conv.user_id, source_media_id=unit.media_id,
                                         start=unit.start, end=unit.end)
            moments.append(RewriteMoment(dimension=rewrite.dimension, you_said=rewrite.you_said,
                                         try_instead=rewrite.try_instead, why=rewrite.why, source_type="conversation",
                                         source_id=conv.id, turn_index=unit.turn_index, start_seconds=unit.start,
                                         end_seconds=unit.end, audio_url=media_service.media_ref(clip_id)))
        observations = [Observation(dimension=o.dimension, note=o.note) for o in judgement.observations
                        if find_unit(units_by_id, user_units, o.segment_id, "") is not None][:4]
        report.report = SparReportOut(
            conversation_id=conv.id, status="complete", title=title,
            outcome=SparOutcome(label=judgement.outcome_label, detail=judgement.outcome_detail),
            momentum=[MomentumPoint(turn_index=i, value=round(v, 2), note=notes.get(i)) for i, v in momentum],
            moments=moments, observations=observations, next_step=judgement.next_step,
        ).model_dump(mode="json")
        report.status = "complete"
        progress.award(db, conv.user_id, "first_spar")
        db.commit()
    except Exception:
        db.rollback()
        report = db.get(SparReport, conversation_id)
        if report is not None and report.status == "processing":
            report.status = "failed"
            db.commit()
        raise
    finally:
        db.close()
