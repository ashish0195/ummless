"""Uploaded and live-recorded conversations.

Pipeline: decode → usability check (10 s windows; usable sections survive) → diarization (with the user's
consented voice reference as a known speaker) → acoustic conflict check → attribution. Confirmation is
always required on the user's first conversation, without a reference, or when the match is missing, weak
or conflicting. Speaker labels never carry across files. Only confirmed user turns are assessed; other
voices are context. "I'm not in this recording" ⇒ no personal assessment. Correction ⇒ reassessment.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections import defaultdict
from typing import Any

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..ai.types import AudioHint, DebriefRequest, KnownSpeaker
from ..audio import ffmpeg, quality, voiceprint
from ..core import AppServices
from ..domain.evidence import MIN_USER_SPEECH_SECONDS, Unit
from ..domain.issues import issue
from ..errors import AIUnavailableError, conflict, not_found, validation
from ..ids import new_id
from ..models import DimensionEstimate, Media, Recording, User, VoiceReference
from ..schemas import (
    AnalysisResult,
    Attribution,
    EvidenceMoment,
    MeetingDebrief,
    RecordingConsent,
    RecordingOut,
    RecordingQuality,
    Recovery,
    RecoveryAction,
    SpeakerCandidate,
    SpeakerConfirmation,
    TalkShare,
    Transcript,
    TranscriptSegment,
)
from ..timeutil import iso_required, short_date, utcnow
from . import media as media_service
from . import progress, users
from .analysis import AnalysisInput, run_analysis

log = logging.getLogger("comlogue.recordings")

MIN_RECORDING_SPEECH_SECONDS = 10.0  # pilot calibration required
OVERLAP_WARN_RATIO = 0.15
ME = "me"  # known-speaker name passed to the diarizer


# ---------------------------------------------------------------- creation & reading


def _safe_ext(filename: str | None) -> str:
    ext = (os.path.splitext(filename or "")[1] or ".m4a").lower().lstrip(".")
    return ext if re.fullmatch(r"[a-z0-9]{1,5}", ext) else "bin"


def create(svc: AppServices, db: Session, user: User, upload_path: str, filename: str | None, source: str,
           title: str | None, consent: RecordingConsent) -> Recording:
    users.require_analysis_consent(user)
    if not consent.attested:
        raise validation("Please confirm that everyone in the conversation agreed to be recorded.")
    svc.limiter.check(f"upload:{user.id}", svc.settings.rate_limit_uploads_per_hour)
    original = media_service.store_file(svc, db, user_id=user.id, kind="recording_original", path=upload_path,
                                        ext=_safe_ext(filename))
    now = utcnow()
    default_title = "Recorded conversation" if source == "live" else "Uploaded conversation"
    recording = Recording(
        id=new_id("rec"), user_id=user.id, title=(title or default_title).strip()[:200] or default_title,
        source=source, status="processing", stage="decoding", language=users.language(user),
        consent={**consent.model_dump(), "accepted_at": iso_required(now)}, original_media_id=original.id,
        attribution={"status": "pending", "user_speaker_label": None, "requires_confirmation": True,
                     "reason": None, "message": None},
    )
    db.add(recording)
    db.commit()
    assert svc.jobs is not None
    svc.jobs.submit("recording.process", recording.id)
    db.refresh(recording)
    return recording


def get_owned(db: Session, user: User, recording_id: str) -> Recording:
    recording = db.get(Recording, recording_id)
    if recording is None or recording.user_id != user.id:
        raise not_found("Recording")
    return recording


def to_out(svc: AppServices, recording: Recording) -> RecordingOut:
    resolve = media_service.resolve_media
    return RecordingOut(
        id=recording.id, title=recording.title, source=recording.source, status=recording.status,
        stage=recording.stage if recording.status in ("processing", "assessing") else None,
        duration_seconds=None if recording.duration_seconds is None else round(recording.duration_seconds, 1),
        created_at=iso_required(recording.created_at),
        quality=RecordingQuality.model_validate(recording.quality) if recording.quality else None,
        speakers=[SpeakerCandidate.model_validate(resolve(svc, s)) for s in recording.speakers or []],
        attribution=Attribution.model_validate(recording.attribution),
        result=AnalysisResult.model_validate(resolve(svc, recording.result)) if recording.result else None,
        debrief=MeetingDebrief.model_validate(resolve(svc, recording.debrief)) if recording.debrief else None,
        recovery=Recovery.model_validate(recording.recovery) if recording.recovery else None,
    )


def list_for(db: Session, user: User) -> list[Recording]:
    return list(db.scalars(select(Recording).where(Recording.user_id == user.id).order_by(Recording.created_at.desc())))


def transcript(recording: Recording) -> Transcript:
    user_label = (recording.attribution or {}).get("user_speaker_label")
    names = {s["label"]: s["display_name"] for s in recording.speakers or []}
    return Transcript(segments=[
        TranscriptSegment(speaker=names.get(seg["speaker"], seg["speaker"]), is_user=seg["speaker"] == user_label,
                          start=round(seg["start"], 2), end=round(seg["end"], 2), text=seg["text"],
                          excluded=bool(seg.get("excluded")), exclusion_reason=seg.get("exclusion_reason"))
        for seg in recording.segments or []
    ])


# ---------------------------------------------------------------- recovery copy


def _recovery_audio(issue_codes: list[str], source: str) -> Recovery:
    explanations = {
        "too_quiet": "the voices were very quiet",
        "noisy": "there was a lot of background noise",
        "no_speech": "we didn't hear any speech",
        "too_short": "there wasn't enough speech",
        "clipping": "the audio was distorted",
        "overlapping_voices": "people talked over each other a lot",
    }
    reasons = [explanations[c] for c in issue_codes if c in explanations] or ["the audio wasn't clear enough"]
    message = (
        f"We couldn't hear enough of your speech clearly — {reasons[0]}. This is about the recording, not how "
        "you communicate. Nothing was scored."
    )
    actions = [
        RecoveryAction(type="record_again" if source == "live" else "upload_another",
                       title="Record somewhere quieter" if source == "live" else "Upload a different recording",
                       activity_id=None),
        RecoveryAction(type="ai_practice", title="Practice with AI instead", activity_id=None),
        RecoveryAction(type="starter_course", title="Start a course based on your goal", activity_id=None),
    ]
    return Recovery(problem="audio_unclear", title="We couldn't hear enough of your speech clearly", message=message,
                    actions=actions, extra_minutes=None)


def _recovery_unreadable() -> Recovery:
    return Recovery(
        problem="file_unreadable", title="We couldn't open this recording",
        message="The file may be damaged or in a format we can't read. This isn't about how you communicate.",
        actions=[
            RecoveryAction(type="upload_another", title="Upload a supported file (M4A, MP3, WAV)", activity_id=None),
            RecoveryAction(type="record_again", title="Record a conversation instead", activity_id=None),
            RecoveryAction(type="ai_practice", title="Practice with AI", activity_id=None),
        ],
        extra_minutes=None,
    )


def _recovery_processing() -> Recovery:
    return Recovery(
        problem="processing_failed", title="We couldn't process this recording right now",
        message="This was a problem on our side. Your recording is saved — try again in a moment.",
        actions=[RecoveryAction(type="retry", title="Try again", activity_id=None)], extra_minutes=None,
    )


# ---------------------------------------------------------------- processing job


def _mark_failed(db: Session, recording: Recording, recovery: Recovery, error: str) -> None:
    recording.status = "failed"
    recording.stage = None
    recording.recovery = recovery.model_dump(mode="json")
    recording.error = error[:500]
    db.commit()


def run_process_job(svc: AppServices, recording_id: str) -> None:
    db = svc.session_factory()
    try:
        recording = db.get(Recording, recording_id)
        if recording is None or recording.status != "processing":
            return
        user = db.get(User, recording.user_id)
        original = db.get(Media, recording.original_media_id) if recording.original_media_id else None
        if user is None or original is None:
            return
        try:
            _process(svc, db, user, recording, original)
        except AIUnavailableError as exc:
            db.rollback()
            recording = db.get(Recording, recording_id)
            if recording is not None:
                _mark_failed(db, recording, _recovery_processing(), str(exc))
    except Exception:
        db.rollback()
        recording = db.get(Recording, recording_id)
        if recording is not None and recording.status in ("processing", "assessing"):
            _mark_failed(db, recording, _recovery_processing(), "internal error")
        raise
    finally:
        db.close()


def _process(svc: AppServices, db: Session, user: User, recording: Recording, original: Media) -> None:
    max_seconds = svc.settings.max_recording_minutes * 60
    with tempfile.TemporaryDirectory() as tmp:
        source_path = media_service.local_path(svc, original)
        wav = os.path.join(tmp, "recording.wav")
        probed = ffmpeg.probe_duration(source_path)
        try:
            ffmpeg.decode_to_wav16k(source_path, wav, max_seconds=max_seconds)
        except ffmpeg.AudioDecodeError as exc:
            recording.quality = None
            _mark_failed(db, recording, _recovery_unreadable(), f"decode: {exc}")
            return
        samples = ffmpeg.read_wav(wav)
        analyzed = len(samples) / ffmpeg.SAMPLE_RATE
        recording.duration_seconds = probed or analyzed
        recording.analyzed_seconds = analyzed
        wav_media = media_service.store_file(svc, db, user_id=user.id, kind="recording_wav", path=wav, ext="wav",
                                             duration=analyzed)
        recording.wav_media_id = wav_media.id
        recording.stage = "checking_audio"
        db.commit()

        report = quality.analyze(samples, min_speech_seconds=MIN_RECORDING_SPEECH_SECONDS)
        warnings = [issue(code, severity="warning") for code in report.issues]
        if probed and probed > max_seconds + 1:
            warnings.append(issue("trimmed"))
        if report.usable == "no":
            blocking = [issue(code, severity="blocking") for code in report.blocking]
            recording.quality = RecordingQuality(usable="no", issues=blocking + warnings,
                                                 usable_seconds=round(report.usable_seconds, 1),
                                                 total_seconds=round(analyzed, 1)).model_dump(mode="json")
            recording.status = "needs_recovery"
            recording.stage = None
            recording.recovery = _recovery_audio(report.blocking, recording.source).model_dump(mode="json")
            db.commit()
            return

        recording.stage = "identifying_speakers"
        db.commit()
        mp3 = os.path.join(tmp, "recording.mp3")
        ffmpeg.encode_mp3(wav, mp3)
        reference = db.scalar(select(VoiceReference).where(VoiceReference.user_id == user.id))
        known: list[KnownSpeaker] = []
        if reference is not None:
            clip_media = db.get(Media, reference.clip_media_id)
            if clip_media is not None:
                known.append(KnownSpeaker(name=ME, wav_path=media_service.local_path(svc, clip_media)))
                reference.last_used_at = utcnow()
        diarization = svc.ai.diarize(mp3, language=recording.language, known_speakers=known,
                                     hint=AudioHint(context_key="recording", wav_path=wav))
        if not diarization.segments:
            blocking = [issue("no_speech", severity="blocking")]
            recording.quality = RecordingQuality(usable="no", issues=blocking + warnings,
                                                 usable_seconds=round(report.usable_seconds, 1),
                                                 total_seconds=round(analyzed, 1)).model_dump(mode="json")
            recording.status = "needs_recovery"
            recording.stage = None
            recording.recovery = _recovery_audio(["no_speech"], recording.source).model_dump(mode="json")
            db.commit()
            return

        segments = _annotate_segments(diarization.segments, report)
        overlap = quality.overlap_ratio([(s["speaker"], s["start"], s["end"]) for s in segments])
        if overlap > OVERLAP_WARN_RATIO:
            warnings.append(issue("overlapping_voices"))
        usable_seconds = sum(s["end"] - s["start"] for s in segments if not s["excluded"])
        recording.quality = RecordingQuality(
            usable="yes" if not warnings and usable_seconds >= 0.8 * report.speech_seconds else "partly",
            issues=warnings, usable_seconds=round(usable_seconds, 1), total_seconds=round(analyzed, 1),
        ).model_dump(mode="json")

        speakers, prints, levels = _speakers(svc, db, user, samples, segments, wav_media.id)
        attribution, speakers = _attribute(db, user, recording, reference, diarization.used_references, speakers,
                                           prints, levels)
        recording.segments = segments
        recording.speakers = speakers
        recording.attribution = attribution
        if attribution["requires_confirmation"]:
            recording.status = "needs_speaker_confirmation"
            recording.stage = None
            db.commit()
            return
        recording.status = "assessing"
        recording.stage = "assessing"
        db.commit()
    _assess(svc, db, user, recording)


def _annotate_segments(raw_segments: list, report: quality.QualityReport) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for index, seg in enumerate(raw_segments):
        start, end = float(seg.start), float(seg.end)
        excluded, reason = False, None
        if not report.usable_window_at((start + end) / 2):
            excluded, reason = True, "audio_unclear"
        if not seg.text.strip():
            excluded, reason = True, "no_speech"
        segments.append({"index": index, "speaker": seg.speaker, "start": round(start, 2), "end": round(end, 2),
                         "text": seg.text.strip(), "excluded": excluded, "exclusion_reason": reason})
    # Mark heavily overlapped segments (another speaker covers > 50% of this one).
    for seg in segments:
        span = seg["end"] - seg["start"]
        if span <= 0 or seg["excluded"]:
            continue
        covered = 0.0
        for other in segments:
            if other is seg or other["speaker"] == seg["speaker"]:
                continue
            covered += max(0.0, min(seg["end"], other["end"]) - max(seg["start"], other["start"]))
        if covered / span > 0.5:
            seg["excluded"], seg["exclusion_reason"] = True, "overlapping_voices"
    return segments


def _speakers(svc: AppServices, db: Session, user: User, samples: np.ndarray, segments: list[dict[str, Any]],
              wav_media_id: str) -> tuple[list[dict[str, Any]], dict[str, dict], dict[str, float]]:
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    order: list[str] = []
    for seg in segments:
        if seg["speaker"] not in by_label:
            order.append(seg["speaker"])
        by_label[seg["speaker"]].append(seg)
    speakers: list[dict[str, Any]] = []
    prints: dict[str, dict] = {}
    levels: dict[str, float] = {}
    for position, label in enumerate(order, start=1):
        segs = by_label[label]
        usable = [s for s in segs if not s["excluded"]] or segs
        best = max(usable, key=lambda s: min(s["end"] - s["start"], 10.0))
        clip_id = media_service.clip(svc, db, user_id=user.id, source_media_id=wav_media_id, start=best["start"],
                                     end=min(best["end"], best["start"] + 8.0), max_seconds=8.5)
        pieces = [ffmpeg.segment_samples(samples, s["start"], s["end"]) for s in usable]
        joined = np.concatenate(pieces)[: 30 * ffmpeg.SAMPLE_RATE] if pieces else samples[:0]
        prints[label] = voiceprint.voiceprint(joined) if joined.size else {"valid": False}
        level_frames = quality.frame_db(joined) if joined.size else np.zeros(0)
        levels[label] = float(np.median(level_frames)) if level_frames.size else -100.0
        speakers.append({
            "label": label,
            "display_name": f"Speaker {position}",
            "speech_seconds": round(sum(s["end"] - s["start"] for s in segs), 1),
            "turns": len(segs),
            "sample_url": media_service.media_ref(clip_id),
            "sample_text": " ".join(best["text"].split()[:24]) or None,
            "is_proposed_user": False,
            "match": "none",
            "match_strength": None,
        })
    return speakers, prints, levels


def _attribute(db: Session, user: User, recording: Recording, reference: VoiceReference | None,
               used_references: bool, speakers: list[dict[str, Any]], prints: dict[str, dict],
               levels: dict[str, float]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    previous = db.scalars(select(Recording).where(Recording.user_id == user.id, Recording.id != recording.id))
    first_conversation = not any((r.attribution or {}).get("status") in ("confirmed", "auto") for r in previous)
    proposed: str | None = None
    match, strength = "none", None
    reason: str | None
    message: str | None = None
    if reference is not None:
        scores = {label: voiceprint.similarity(reference.voiceprint or {}, vp) for label, vp in prints.items()}
        if used_references and any(s["label"] == ME for s in speakers):
            proposed, match = ME, "reference"
            score = scores.get(ME)
            strength = voiceprint.strength(score) or "weak"
            others = [v for label, v in scores.items() if label != ME and v is not None]
            if others and score is not None and max(others) > score + 0.1:
                strength = "conflict"
        else:
            ranked = sorted(((v, label) for label, v in scores.items() if v is not None), reverse=True)
            if ranked and ranked[0][0] >= voiceprint.WEAK_MATCH:
                proposed, match, strength = ranked[0][1], "acoustic", "weak"
        if proposed is None:
            reason, message = "uncertain_match", "We couldn't confidently find your voice. Which voice is yours?"
        elif strength == "conflict":
            reason, message = "conflict", "The voice we matched doesn't sound quite like your voice sample. Is this you?"
        elif strength != "strong":
            reason, message = "uncertain_match", "We think this is you, but we're not sure. Is this you?"
        elif first_conversation:
            reason, message = "first_conversation", "Is this you? We confirm on your first conversation."
        else:
            reason = None
        requires = first_conversation or proposed is None or strength != "strong"
    else:
        if recording.source == "live" and levels:
            proposed = max(levels, key=lambda label: levels[label])
            match, strength = "loudest", "weak"
            message = "The loudest voice is usually the person holding the phone. Is this you?"
        else:
            message = "Which voice is yours? Play the clips and pick yours."
        reason = "no_reference" if not first_conversation else "first_conversation"
        requires = True
    for speaker in speakers:
        if speaker["label"] == proposed:
            speaker.update({"is_proposed_user": True, "match": match, "match_strength": strength})
    status = "pending" if requires else "auto"
    attribution = {"status": status, "user_speaker_label": None if requires else proposed,
                   "requires_confirmation": requires, "reason": reason if requires else None,
                   "message": message if requires else None}
    return attribution, speakers


# ---------------------------------------------------------------- confirmation & assessment


def confirm_speaker(svc: AppServices, db: Session, user: User, recording: Recording, body: SpeakerConfirmation) -> None:
    if recording.status in ("processing", "assessing", "failed") or not recording.speakers:
        raise conflict("This recording isn't ready for speaker confirmation.")
    labels = {s["label"] for s in recording.speakers}
    if body.decision == "not_present":
        recording.attribution = {"status": "not_present", "user_speaker_label": None, "requires_confirmation": False,
                                 "reason": None,
                                 "message": "You told us you're not in this recording, so we didn't assess it."}
        recording.status = "no_user"
        recording.result = None
        recording.debrief = None
        recording.recovery = None
        recording.style_vector = None
        db.execute(delete(DimensionEstimate).where(DimensionEstimate.source_id == recording.id))
        db.commit()
        return
    if body.decision == "confirm":
        label = body.speaker_label or next((s["label"] for s in recording.speakers if s.get("is_proposed_user")), None)
    else:
        label = body.speaker_label
    if not label or label not in labels:
        raise validation("Choose which voice is yours.")
    recording.speakers = [{**s, "is_proposed_user": s["label"] == label} for s in recording.speakers]
    recording.attribution = {"status": "confirmed", "user_speaker_label": label, "requires_confirmation": False,
                             "reason": None, "message": None}
    # Correction (or first confirmation) ⇒ (re)assess with the confirmed attribution.
    db.execute(delete(DimensionEstimate).where(DimensionEstimate.source_id == recording.id))
    recording.result = None
    recording.debrief = None
    recording.recovery = None
    recording.status = "assessing"
    recording.stage = "assessing"
    db.commit()
    assert svc.jobs is not None
    svc.jobs.submit("recording.assess", recording.id)
    db.refresh(recording)


def run_assess_job(svc: AppServices, recording_id: str) -> None:
    db = svc.session_factory()
    try:
        recording = db.get(Recording, recording_id)
        if recording is None or recording.status != "assessing":
            return
        user = db.get(User, recording.user_id)
        if user is None:
            return
        try:
            _assess(svc, db, user, recording)
        except AIUnavailableError as exc:
            db.rollback()
            recording = db.get(Recording, recording_id)
            if recording is not None:
                _mark_failed(db, recording, _recovery_processing(), str(exc))
    except Exception:
        db.rollback()
        recording = db.get(Recording, recording_id)
        if recording is not None and recording.status == "assessing":
            _mark_failed(db, recording, _recovery_processing(), "internal error")
        raise
    finally:
        db.close()


def _assess(svc: AppServices, db: Session, user: User, recording: Recording) -> None:
    user_label = (recording.attribution or {}).get("user_speaker_label")
    names = {s["label"]: s["display_name"] for s in recording.speakers or []}
    units: list[Unit] = []
    for seg in recording.segments or []:
        is_user = seg["speaker"] == user_label
        units.append(Unit(
            uid=f"S{seg['index']}", role="user" if is_user else "other",
            speaker_name="You" if is_user else names.get(seg["speaker"], seg["speaker"]), text=seg["text"],
            source_type="recording", source_id=recording.id, start=seg["start"], end=seg["end"],
            media_id=recording.wav_media_id, excluded=bool(seg.get("excluded")),
            exclusion_reason=seg.get("exclusion_reason"),
        ))
    total_speech = sum(u.duration for u in units if not u.excluded) or 1.0
    user_speech = sum(u.duration for u in units if u.usable_user)
    pauses = _user_pauses(svc, db, recording, units)
    context_label = f"{recording.title} · {short_date(recording.created_at)}"
    n_speakers = len(recording.speakers or [])
    inp = AnalysisInput(
        user_id=user.id, language=recording.language, source_type="recording", source_id=recording.id,
        context_label=context_label,
        context_description=(
            f"A real conversation the user {'recorded live' if recording.source == 'live' else 'uploaded'} "
            f"(\"{recording.title}\") with {n_speakers} speaker(s). The user confirmed which voice is theirs. "
            "Real conversations may not contain opportunities for every dimension."
        ),
        units=units, pauses=pauses, talk_share=user_speech / total_speech if n_speakers > 1 else None,
        audio_problem=any(u.role == "user" and u.excluded for u in units) and user_speech < MIN_USER_SPEECH_SECONDS,
        route="recording",
    )
    output = run_analysis(svc, db, inp)
    recording.result = output.result.model_dump(mode="json")
    recording.style_vector = output.style_vector
    recording.debrief = _debrief(svc, db, user, recording, units, names, user_label)
    if output.result.status == "none":
        recording.status = "needs_recovery"
        recording.recovery = output.result.recovery.model_dump(mode="json") if output.result.recovery else None
    else:
        recording.status = "complete"
        recording.recovery = None
    recording.stage = None
    recording.completed_at = utcnow()
    db.execute(delete(DimensionEstimate).where(DimensionEstimate.source_id == recording.id))
    for estimate in output.estimates:
        db.add(DimensionEstimate(
            user_id=user.id, dimension=estimate["dimension"], status=estimate["status"], level=estimate["level"],
            confidence=estimate["confidence"] or "low", payload=estimate["payload"], source_type="recording",
            source_id=recording.id, context_label=context_label, assessed_at=utcnow(),
        ))
    progress.log_activity(db, user.id, "recording", recording.title, (recording.analyzed_seconds or 0) / 60,
                          recording.id)
    progress.award(db, user.id, "first_upload")
    if output.estimates:
        progress.award(db, user.id, "first_profile")
    db.commit()


def _user_pauses(svc: AppServices, db: Session, recording: Recording, units: list[Unit]) -> list[float]:
    wav = db.get(Media, recording.wav_media_id) if recording.wav_media_id else None
    if wav is None:
        return []
    samples = ffmpeg.read_wav(media_service.local_path(svc, wav))
    runs = quality.analyze(samples, min_speech_seconds=0.5).speech_runs
    pauses: list[float] = []
    for unit in units:
        if unit.usable_user and unit.start is not None and unit.end is not None:
            pauses.extend(quality.pauses_between(runs, unit.start, unit.end))
    return pauses


def _debrief(svc: AppServices, db: Session, user: User, recording: Recording, units: list[Unit],
             names: dict[str, str], user_label: str | None) -> dict | None:
    if len(names) < 2 or not any(u.usable_user for u in units):
        return None
    talk: dict[str, float] = defaultdict(float)
    for seg in recording.segments or []:
        talk[seg["speaker"]] += max(0.0, seg["end"] - seg["start"])
    total = sum(talk.values()) or 1.0
    shares = [TalkShare(label=label, display_name="You" if label == user_label else names.get(label, label),
                        is_user=label == user_label, share=round(seconds / total, 3))
              for label, seconds in sorted(talk.items(), key=lambda kv: -kv[1])]
    try:
        judgement = svc.ai.debrief(DebriefRequest(
            language=recording.language, title=recording.title, units=units,
            talk_share=[(s.display_name, s.share, s.is_user) for s in shares],
        ))
    except AIUnavailableError as exc:
        log.warning("Debrief unavailable for %s: %s", recording.id, exc)
        return MeetingDebrief(talk_share=shares, best_moment=None, decisions=[], follow_up_summary=None,
                              one_thing_to_try=None).model_dump(mode="json")
    best: EvidenceMoment | None = None
    by_uid = {u.uid: u for u in units}
    unit = by_uid.get(judgement.best_moment_segment_id or "")
    if unit is not None and unit.usable_user:
        clip_id = media_service.clip(svc, db, user_id=user.id, source_media_id=unit.media_id, start=unit.start,
                                     end=unit.end)
        best = EvidenceMoment(quote=" ".join(unit.text.split()[:30]), note=judgement.best_moment_note,
                              source_type="recording", source_id=recording.id, turn_index=None,
                              start_seconds=unit.start, end_seconds=unit.end,
                              audio_url=media_service.media_ref(clip_id))
    return MeetingDebrief(talk_share=shares, best_moment=best, decisions=judgement.decisions[:5],
                          follow_up_summary=judgement.follow_up_summary,
                          one_thing_to_try=judgement.one_thing_to_try).model_dump(mode="json")


def retry(svc: AppServices, db: Session, recording: Recording) -> None:
    """Re-run processing after a processing failure (not after poor audio)."""
    if recording.status != "failed" or (recording.recovery or {}).get("problem") != "processing_failed":
        raise conflict("Only recordings that failed on our side can be retried.")
    recording.status = "processing"
    recording.stage = "decoding"
    recording.recovery = None
    recording.error = None
    db.commit()
    assert svc.jobs is not None
    svc.jobs.submit("recording.process", recording.id)
    db.refresh(recording)


def delete_recording(svc: AppServices, db: Session, recording: Recording) -> None:
    for media_id in (recording.original_media_id, recording.wav_media_id):
        if media_id:
            for clip in db.scalars(select(Media).where(Media.cache_key.like(f"clip:{media_id}:%"))):
                media_service.delete_media(svc, db, clip.id)
            media_service.delete_media(svc, db, media_id)
    db.execute(delete(DimensionEstimate).where(DimensionEstimate.source_id == recording.id))
    db.delete(recording)
    db.commit()
