"""Talks for "steal their style" shadowing. Line audio is generated with TTS and cached."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.talks import (
    TALKS,
    TALKS_BY_ID,
    TalkDef,
    avg_sentence_words,
    display_text,
    pause_count,
    tts_text,
)
from ..errors import APIError, not_found, subscription_required
from ..models import Media, User
from ..schemas import Talk, TalkLine, TalkList, TalkStyle, TalkSummary
from . import media as media_service
from . import tts, users

PREVIEW_LINES = 2


def _is_free(svc: AppServices, talk: TalkDef) -> bool:
    return TALKS.index(talk) < svc.settings.free_talks


def _summary(svc: AppServices, talk: TalkDef) -> TalkSummary:
    return TalkSummary(
        id=talk.id, title=talk.title, speaker=talk.speaker, source_note=talk.source_note, year=talk.year,
        duration_label=talk.duration_label, lines_count=len(talk.lines),
        style=TalkStyle(wpm=talk.wpm, avg_pause_seconds=talk.avg_pause_seconds,
                        avg_sentence_words=avg_sentence_words(talk)),
        tags=list(talk.tags), is_free=_is_free(svc, talk),
    )


def list_talks(svc: AppServices) -> TalkList:
    return TalkList(talks=[_summary(svc, talk) for talk in TALKS])


def _locked(svc: AppServices, user: User, talk: TalkDef) -> bool:
    return not users.is_pro(user) and not _is_free(svc, talk)


def talk_detail(svc: AppServices, user: User, talk_id: str) -> Talk:
    talk = TALKS_BY_ID.get(talk_id)
    if talk is None:
        raise not_found("Talk")
    locked = _locked(svc, user, talk)
    lines = talk.lines[:PREVIEW_LINES] if locked else talk.lines
    return Talk(
        **_summary(svc, talk).model_dump(), technique=talk.technique, breakdown=list(talk.breakdown), locked=locked,
        lines=[TalkLine(index=i, text=line, display_text=display_text(line), pause_count=pause_count(line),
                        audio_url=None if svc.demo_mode else f"/v1/talks/{talk.id}/lines/{i}/audio")
               for i, line in enumerate(lines)],
    )


def line_audio(svc: AppServices, db: Session, user: User, talk_id: str, index: int) -> Media:
    talk = TALKS_BY_ID.get(talk_id)
    if talk is None or not 0 <= index < len(talk.lines):
        raise not_found("Talk line")
    if _locked(svc, user, talk) and index >= PREVIEW_LINES:
        raise subscription_required("The full talk is part of Comlogue Pro.")
    media_id = tts.speak(svc, db, tts_text(talk.lines[index]), talk.tts_voice, talk.tts_instructions)
    media = db.get(Media, media_id) if media_id else None
    if media is None:
        raise APIError(404, "not_found", "Audio isn't available right now — the app can read this line aloud instead.")
    return media


__all__ = ["list_talks", "talk_detail", "line_audio", "media_service"]
