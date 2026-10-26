"""Partner voice lines (TTS), cached by content hash and shared across users."""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from ..core import AppServices
from . import media as media_service

log = logging.getLogger("comlogue.tts")


def speak(svc: AppServices, db: Session, text: str, voice: str, instructions: str | None) -> str | None:
    """Return a media id for the spoken line, or None (the app then speaks on-device)."""
    if not text.strip() or svc.demo_mode:
        return None
    digest = hashlib.sha256(f"{svc.settings.tts_models}|{voice}|{instructions}|{text}".encode()).hexdigest()
    cache_key = f"tts:{digest}"
    cached = media_service.find_cached(db, cache_key)
    if cached is not None:
        return cached.id
    try:
        audio = svc.ai.synthesize(text, voice=voice, instructions=instructions)
    except Exception as exc:  # noqa: BLE001 - TTS must never break a conversation
        log.warning("TTS failed: %s", exc)
        return None
    if not audio:
        return None
    media = media_service.store_bytes(svc, db, user_id=None, kind="tts", data=audio, ext="mp3", cache_key=cache_key)
    return media.id
