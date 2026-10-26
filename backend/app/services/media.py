"""Media storage, clip cutting and signed URLs.

Stored result payloads reference media as `media:<id>`; `resolve_media` swaps those for short-lived
signed URLs at response time, so stored payloads never contain expiring links.
"""

from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audio import ffmpeg
from ..core import AppServices
from ..ids import new_id
from ..models import Media
from ..security import sign_media

log = logging.getLogger("comlogue.media")

MEDIA_PREFIX = "media:"
CONTENT_TYPES = {"m4a": "audio/mp4", "mp3": "audio/mpeg", "wav": "audio/wav", "aac": "audio/aac"}


def media_ref(media_id: str | None) -> str | None:
    return f"{MEDIA_PREFIX}{media_id}" if media_id else None


def _key(user_id: str | None, media_id: str, ext: str) -> str:
    return f"{user_id or 'shared'}/{media_id}.{ext}"


def store_bytes(svc: AppServices, db: Session, *, user_id: str | None, kind: str, data: bytes, ext: str,
                duration: float | None = None, cache_key: str | None = None) -> Media:
    media_id = new_id("med")
    key = _key(user_id, media_id, ext)
    size = svc.storage.put_bytes(key, data)
    media = Media(id=media_id, user_id=user_id, kind=kind, storage_key=key,
                  content_type=CONTENT_TYPES.get(ext, "application/octet-stream"), size_bytes=size,
                  duration_seconds=duration, cache_key=cache_key)
    db.add(media)
    db.flush()
    return media


def store_file(svc: AppServices, db: Session, *, user_id: str | None, kind: str, path: str, ext: str,
               duration: float | None = None, cache_key: str | None = None) -> Media:
    media_id = new_id("med")
    key = _key(user_id, media_id, ext)
    size = svc.storage.put_file(key, path)
    media = Media(id=media_id, user_id=user_id, kind=kind, storage_key=key,
                  content_type=CONTENT_TYPES.get(ext, "application/octet-stream"), size_bytes=size,
                  duration_seconds=duration, cache_key=cache_key)
    db.add(media)
    db.flush()
    return media


def find_cached(db: Session, cache_key: str) -> Media | None:
    return db.scalar(select(Media).where(Media.cache_key == cache_key))


def local_path(svc: AppServices, media: Media) -> str:
    return svc.storage.local_path(media.storage_key)


def signed_url(svc: AppServices, media_id: str) -> str:
    expires, signature = sign_media(svc.settings.secret_key, media_id, svc.settings.media_url_ttl_seconds)
    return f"/v1/media/{media_id}?exp={expires}&sig={signature}"


def url_for(svc: AppServices, media_id: str | None) -> str | None:
    return signed_url(svc, media_id) if media_id else None


def resolve_media(svc: AppServices, value: Any) -> Any:
    """Recursively replace `media:<id>` strings with signed URLs."""
    if isinstance(value, str):
        if value.startswith(MEDIA_PREFIX):
            return signed_url(svc, value[len(MEDIA_PREFIX):])
        return value
    if isinstance(value, list):
        return [resolve_media(svc, item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_media(svc, item) for key, item in value.items()}
    return value


def delete_media(svc: AppServices, db: Session, media_id: str | None) -> None:
    if not media_id:
        return
    media = db.get(Media, media_id)
    if media is None:
        return
    svc.storage.delete(media.storage_key)
    db.delete(media)


def clip(svc: AppServices, db: Session, *, user_id: str, source_media_id: str | None, start: float | None,
         end: float | None, max_seconds: float = 20.0) -> str | None:
    """Cut a playable clip from a stored source; returns the clip's media id (cached per range)."""
    if not source_media_id or start is None or end is None:
        return None
    start = max(0.0, start - 0.25)
    end = min(end + 0.25, start + max_seconds)
    cache_key = f"clip:{source_media_id}:{start:.2f}:{end:.2f}"
    cached = find_cached(db, cache_key)
    if cached is not None:
        return cached.id
    source = db.get(Media, source_media_id)
    if source is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "clip.m4a")
        try:
            ffmpeg.cut_clip(local_path(svc, source), out, start, end)
        except ffmpeg.AudioDecodeError as exc:
            log.warning("Clip cut failed for %s: %s", source_media_id, exc)
            return None
        media = store_file(svc, db, user_id=user_id, kind="clip", path=out, ext="m4a", duration=end - start,
                           cache_key=cache_key)
    return media.id
