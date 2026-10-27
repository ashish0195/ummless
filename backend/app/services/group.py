"""Group conversations: a campus-placement group discussion (GD) or a panel interview with several AI voices.

The moderator is the conversation's `partner` and opens it (turn 0); up to two participants may speak before the
user's first turn. After each user turn one or two participants respond in character — building on, challenging
or ignoring what the user said — and at the last turn the moderator closes. The report uses the spar machinery,
focused on the panel's `evaluation_focus`.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..ai.types import GroupMember, GroupReplyRequest
from ..core import AppServices
from ..domain.content.schema import PanelDef, ParticipantDef
from ..domain.market_content import PANELS_BY_ID, panels_for
from ..domain.personas import DIFFICULTY_BEHAVIOUR
from ..errors import AIUnavailableError, not_found, subscription_required, validation
from ..ids import new_id
from ..models import Conversation, Turn, User
from ..schemas import ConversationCreate, ConversationSetup, Panel, PanelList, Participant
from . import conversations, users

log = logging.getLogger("comlogue.group")

MAX_LINES_PER_TURN = 2
TIPS = {
    "group_discussion": ["Enter early with one clear point.", "Build on someone by name, then add something new.",
                         "Invite a quiet voice in, and offer a summary near the end."],
    "panel_interview": ["Answer the person who asked, then include the others.",
                        "Use one specific example per answer.", "It's fine to pause before you answer."],
}
FALLBACK_REACTIONS = {
    "group_discussion": ("That's one way to see it. I'd still say the practical side matters more.",
                         "Okay, but what about the people who'd actually have to make this work?",
                         "I partly agree. Can we hear a concrete example, though?"),
    "panel_interview": ("Thanks. Could you give us a specific example?",
                        "Can you say a bit more about your own part in that?",
                        "How did you know it had worked?"),
}
FALLBACK_CLOSING = {
    "group_discussion": "Thank you, everyone — time's up. Good discussion.",
    "panel_interview": "Thank you — that's all our questions for today.",
}


def participant_out(person: ParticipantDef) -> Participant:
    return Participant(id=person.id, name=person.name, role=person.role, voice=person.voice, symbol=person.symbol,
                       color_hex=person.color_hex)


def panel_out(panel: PanelDef) -> Panel:
    return Panel(
        id=panel.id, kind=panel.kind, title=panel.title, scenario=panel.scenario,  # type: ignore[arg-type]
        description=panel.description, topic=panel.topic, user_role=panel.user_role,
        participants=[participant_out(p) for p in (panel.moderator, *panel.participants)], minutes=panel.minutes,
        markets=list(panel.markets), is_free=panel.is_free, symbol=panel.symbol,  # type: ignore[arg-type]
        color_hex=panel.color_hex, default_difficulty=panel.default_difficulty,  # type: ignore[arg-type]
    )


def panels(user: User) -> PanelList:
    return PanelList(panels=[panel_out(p) for p in panels_for(users.market(user))])


def get_panel(panel_id: str | None) -> PanelDef:
    panel = PANELS_BY_ID.get(panel_id or "")
    if panel is None:
        raise not_found("Panel")
    return panel


def conversation_fields(panel: PanelDef, difficulty: str) -> dict[str, Any]:
    """Conversation columns for a group session on `panel` (the moderator is the partner)."""
    moderator = panel.moderator
    people = (moderator, *panel.participants)
    setup = ConversationSetup(
        title=panel.title, context=panel.description, target_behavior=None, suggested_seconds=45,
        tips=TIPS.get(panel.kind, TIPS["group_discussion"]), activity_id=None, mission_id=None, persona_id=None,
        difficulty=difficulty, quick=False,  # type: ignore[arg-type]
    )
    return {
        "partner": {"name": moderator.name, "role": moderator.role, "voice": moderator.voice,
                    "symbol": moderator.symbol, "color_hex": moderator.color_hex},
        "setup": setup.model_dump(mode="json"),
        "state": {
            "tts_instructions": moderator.tts_instructions, "character": moderator.stance,
            "moderator_id": moderator.id, "panel_kind": panel.kind, "topic": panel.topic,
            "user_role": panel.user_role, "evaluation_focus": list(panel.evaluation_focus),
            "stances": {p.id: p.stance for p in people},
            "voices": {p.id: {"voice": p.voice, "tts_instructions": p.tts_instructions} for p in people},
        },
        "panel_id": panel.id, "participants": [participant_out(p).model_dump(mode="json") for p in people],
        "difficulty": difficulty, "max_user_turns": panel.max_user_turns,
    }


def create(svc: AppServices, db: Session, user: User, body: ConversationCreate) -> Conversation:
    users.require_analysis_consent(user)
    if not body.panel_id:
        raise validation("panel_id is required.")
    panel = get_panel(body.panel_id)
    if not panel.is_free and not users.is_pro(user):
        raise subscription_required("This group session is part of Comlogue Pro.")
    difficulty = body.difficulty or panel.default_difficulty
    conv = Conversation(id=new_id("cnv"), user_id=user.id, kind="group", status="active", awaiting="user",
                        language=users.language(user), demo_mode=svc.demo_mode,
                        **conversation_fields(panel, difficulty))
    db.add(conv)
    db.flush()
    moderator = panel.moderator
    people = (moderator, *panel.participants)
    conversations.add_partner_turn(svc, db, conv, panel.opening, speaker_id=moderator.id)
    known = {p.id for p in people}
    for speaker_id, line in panel.pre_user_lines[:2]:
        if speaker_id in known and line.strip():
            conversations.add_partner_turn(svc, db, conv, line.strip(), speaker_id=speaker_id)
    return conv


def _members(conv: Conversation) -> list[GroupMember]:
    moderator_id = conv.state.get("moderator_id")
    stances = conv.state.get("stances") or {}
    return [GroupMember(id=p["id"], name=p["name"], role=p["role"], stance=stances.get(p["id"], ""),
                        is_moderator=p["id"] == moderator_id) for p in conv.participants or []]


def _fallback(conv: Conversation, turns: list[Turn], is_closing: bool) -> list[tuple[str, str]]:
    kind = conv.state.get("panel_kind", "group_discussion")
    moderator_id = conv.state.get("moderator_id") or "mod"
    if is_closing:
        return [(moderator_id, FALLBACK_CLOSING.get(kind, FALLBACK_CLOSING["group_discussion"]))]
    others = [p["id"] for p in conv.participants or [] if p["id"] != moderator_id] or [moderator_id]
    last_ai = next((t.speaker_id for t in reversed(turns) if t.speaker == "partner" and t.speaker_id), None)
    rotation = [pid for pid in others if pid != last_ai] or others
    speaker = rotation[(conv.user_turns - 1) % len(rotation)]
    reactions = FALLBACK_REACTIONS.get(kind, FALLBACK_REACTIONS["group_discussion"])
    return [(speaker, reactions[(conv.user_turns - 1) % len(reactions)])]


def _clean_lines(conv: Conversation, raw: list[tuple[str, str]], is_closing: bool) -> list[tuple[str, str]]:
    """Keep lines from known participants only, at most two, never the same voice twice in a row."""
    known = {p["id"] for p in conv.participants or []}
    moderator_id = conv.state.get("moderator_id")
    lines: list[tuple[str, str]] = []
    for speaker_id, text in raw:
        text = (text or "").strip().strip('"“”').strip()
        if speaker_id not in known or not text:
            continue
        if lines and lines[-1][0] == speaker_id:
            lines[-1] = (speaker_id, f"{lines[-1][1]} {text}")
            continue
        lines.append((speaker_id, text))
    lines = lines[:MAX_LINES_PER_TURN]
    if is_closing and lines and lines[-1][0] != moderator_id:
        return []  # the moderator must have the last word; fall back to the scripted close
    return lines


def respond(svc: AppServices, db: Session, conv: Conversation) -> tuple[list[Turn], bool]:
    """The AI participants' lines after a user turn. Returns (new partner turns, done)."""
    turns = conversations.turns_of(db, conv)
    is_closing = conv.user_turns >= conv.max_user_turns
    fallback = _fallback(conv, turns, is_closing)
    difficulty = conv.difficulty
    request = GroupReplyRequest(
        language=conv.language, panel_kind=conv.state.get("panel_kind", "group_discussion"),
        title=conv.setup.get("title", "Group discussion"), topic=conv.state.get("topic"),
        situation=conv.setup.get("context", ""), user_role=conv.state.get("user_role", "Participant"),
        members=_members(conv), history=conversations.history_for(conv, turns), is_closing=is_closing,
        turns_left=max(0, conv.max_user_turns - conv.user_turns), fallback_lines=fallback, difficulty=difficulty,
        difficulty_behaviour=DIFFICULTY_BEHAVIOUR.get(difficulty or ""),
    )
    end = is_closing
    try:
        reply = svc.ai.group_reply(request)
        lines = _clean_lines(conv, [(line.speaker_id, line.text) for line in reply.lines], is_closing)
        moderator_id = conv.state.get("moderator_id")
        if (not is_closing and reply.end_discussion and lines and lines[-1][0] == moderator_id
                and conv.user_turns >= 2):
            end = True  # the moderator wrapped up early, naturally
    except AIUnavailableError as exc:
        log.warning("Group reply fell back to script: %s", exc)
        lines = []
    if not lines:
        lines = fallback
    new_turns = [conversations.add_partner_turn(svc, db, conv, text, speaker_id=speaker_id)
                 for speaker_id, text in lines]
    return new_turns, end
