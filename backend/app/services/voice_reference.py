"""Consented voice reference: a short solo sample used only to find the user's turns in their recordings.

Checks run locally (no third party sees the setup recording): usable audio, ≥ 8 s of speech, one speaker.
We keep only the best 8-second clip (for the diarizer's known-speaker reference) and acoustic features (for
conflict checks). The setup recording is never scored.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audio import ffmpeg, quality, voiceprint
from ..core import AppServices
from ..domain.consents import VOICE_REFERENCE_VERSION
from ..domain.issues import issue
from ..errors import validation
from ..ids import new_id
from ..models import Media, User, VoiceReference
from ..schemas import Issue, VoiceEnrollmentResult
from ..timeutil import utcnow
from . import media as media_service
from . import users

MIN_SPEECH_SECONDS = 8.0  # pilot calibration required
CLIP_SECONDS = 8.0


def _multiple_speakers(samples: np.ndarray, runs: list[tuple[float, float]]) -> bool:
    """Heuristic: pitch medians of ~3 s chunks split into two clearly different groups."""
    medians: list[float] = []
    for start, end in runs:
        t = start
        while t < end - 1.0:
            chunk = ffmpeg.segment_samples(samples, t, min(end, t + 3.0))
            f0 = voiceprint.pitch_track(chunk)
            if f0.size >= 8:
                medians.append(float(np.median(f0)))
            t += 3.0
    if len(medians) < 4:
        return False
    values = np.sort(np.array(medians))
    best_ratio, best_balance = 1.0, 0.0
    for split in range(1, len(values)):
        low, high = values[:split], values[split:]
        ratio = float(np.median(high) / max(1.0, np.median(low)))
        balance = min(len(low), len(high)) / len(values)
        if ratio > best_ratio:
            best_ratio, best_balance = ratio, balance
    return best_ratio > 1.45 and best_balance >= 0.25


def _best_window(samples: np.ndarray, runs: list[tuple[float, float]], seconds: float) -> tuple[float, float]:
    duration = len(samples) / ffmpeg.SAMPLE_RATE
    if duration <= seconds:
        return 0.0, duration
    best_start, best_speech = 0.0, -1.0
    step = 0.5
    start = 0.0
    while start + seconds <= duration:
        end = start + seconds
        speech = sum(max(0.0, min(b, end) - max(a, start)) for a, b in runs)
        if speech > best_speech:
            best_start, best_speech = start, speech
        start += step
    return best_start, best_start + seconds


def enroll(svc: AppServices, db: Session, user: User, upload_path: str, consent_version: str,
           consent_accepted: bool) -> VoiceEnrollmentResult:
    if not consent_accepted:
        raise validation("Please accept the voice reference consent to save a voice sample.")
    if consent_version != VOICE_REFERENCE_VERSION:
        raise validation("The voice reference consent text has changed. Please review it again.")
    issues: list[Issue] = []
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "enroll.wav")
        try:
            ffmpeg.decode_to_wav16k(upload_path, wav, max_seconds=90)
        except ffmpeg.AudioDecodeError:
            return _rejected(db, user, [issue("file_unreadable", severity="blocking")])
        samples = ffmpeg.read_wav(wav)
        report = quality.analyze(samples, min_speech_seconds=MIN_SPEECH_SECONDS)
        if report.blocking:
            return _rejected(db, user, [issue(code, severity="blocking") for code in report.blocking])
        if report.speech_seconds < MIN_SPEECH_SECONDS:
            return _rejected(db, user, [issue("too_short", severity="blocking",
                                              detail="Keep talking for about 20–30 seconds.")])
        if _multiple_speakers(samples, report.speech_runs):
            return _rejected(db, user, [issue("multiple_speakers", severity="blocking")])
        issues += [issue(code, severity="warning") for code in report.issues]
        start, end = _best_window(samples, report.speech_runs, CLIP_SECONDS)
        clip_samples = ffmpeg.segment_samples(samples, start, end)
        speech_only = np.concatenate([ffmpeg.segment_samples(samples, a, b) for a, b in report.speech_runs]) \
            if report.speech_runs else samples
        print_ = voiceprint.voiceprint(speech_only)
        clip_path = os.path.join(tmp, "reference.wav")
        ffmpeg.write_wav(clip_path, clip_samples)
        _delete_existing(svc, db, user)
        clip_media = media_service.store_file(svc, db, user_id=user.id, kind="voice_reference", path=clip_path,
                                              ext="wav", duration=len(clip_samples) / ffmpeg.SAMPLE_RATE)
    reference = VoiceReference(
        id=new_id("ref"), user_id=user.id, duration_seconds=report.speech_seconds, consent_version=consent_version,
        consented_at=utcnow(), clip_media_id=clip_media.id, voiceprint=print_,
    )
    db.add(reference)
    db.flush()
    return VoiceEnrollmentResult(
        status="active", issues=issues,
        message="Got it. We'll use this only to find your turns in your own recordings.",
        reference=users.voice_reference_status(db, user),
    )


def _rejected(db: Session, user: User, issues: list[Issue]) -> VoiceEnrollmentResult:
    first = issues[0]
    return VoiceEnrollmentResult(status="rejected", issues=issues, message=f"{first.title}. {first.detail}",
                                 reference=users.voice_reference_status(db, user))


def _delete_existing(svc: AppServices, db: Session, user: User) -> None:
    existing = db.scalar(select(VoiceReference).where(VoiceReference.user_id == user.id))
    if existing is None:
        return
    media_service.delete_media(svc, db, existing.clip_media_id)
    db.delete(existing)
    db.flush()


def delete(svc: AppServices, db: Session, user: User) -> None:
    """Stops future automatic matching. Recordings and results have their own delete controls."""
    _delete_existing(svc, db, user)
    for media in db.scalars(select(Media).where(Media.user_id == user.id, Media.kind == "voice_reference")):
        media_service.delete_media(svc, db, media.id)
