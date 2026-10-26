"""The AI voice-conversation engine used by assessment activities, missions and spar.

Per user turn: decode → audio usability gate → transcription (with token confidence) and, in parallel,
diarization to catch background voices → intelligibility gate → partner reply that follows the
activity/mission/persona policy → TTS. A failed partner reply falls back to a scripted line; a failed
transcription returns 503 so the app can resend the same audio.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.types import AudioHint, PartnerReplyRequest
from ..audio import ffmpeg, quality
from ..audio.speech_stats import turn_metrics
from ..core import AppServices
from ..domain.activities import (
    ACTIVITIES,
    CLOSE_INSTRUCTION,
    MAYA,
    MAYA_CHARACTER,
    MAYA_TTS_INSTRUCTIONS,
)
from ..domain.course import MISSIONS, MODULES
from ..domain.evidence import Unit
from ..domain.issues import issue
from ..domain.personas import DIFFICULTY_BEHAVIOUR
from ..errors import AIUnavailableError, conflict, not_found
from ..ids import new_id
from ..models import Assessment, Conversation, MissionAttempt, SparReport, Turn, User
from ..schemas import (
    ConversationOut,
    ConversationSetup,
    FinishResult,
    Partner,
    ResultRef,
    TurnQuality,
    TurnResult,
)
from ..schemas import Turn as TurnOut
from ..timeutil import iso_required, utcnow
from . import media as media_service
from . import tts

log = logging.getLogger("comlogue.conversations")

MIN_TURN_SPEECH_SECONDS = 1.5  # pilot calibration required
LOW_CONFIDENCE_BLOCK = -1.3  # mean token logprob below this ⇒ we can't trust the transcript
LOW_CONFIDENCE_WARN = -0.8
BACKGROUND_MIN_SECONDS = 2.5
BACKGROUND_MIN_SHARE = 0.15
VERBATIM_PROMPTS = {
    # Encourages verbatim transcription (keeps disfluencies) — used for filler statistics.
    "en": "Umm, let me think, like, hmm... Okay, here's what I'm, like, thinking.",
}
GENERIC_TTS = "Voice: natural and conversational. Pace: everyday speech. Never sound like an announcer."


# ------------------------------------------------------------------------- creation


def _add_partner_turn(svc: AppServices, db: Session, conv: Conversation, text: str, *, coach_whisper: str | None = None,
                      momentum: float | None = None) -> Turn:
    partner = conv.partner
    media_id = tts.speak(svc, db, text, partner.get("voice", "marin"), conv.state.get("tts_instructions"))
    index = (db.scalar(select(Turn.index).where(Turn.conversation_id == conv.id).order_by(Turn.index.desc()).limit(1))
             if conv.id else None)
    turn = Turn(conversation_id=conv.id, index=0 if index is None else index + 1, speaker="partner", text=text,
                audio_media_id=media_id, coach_whisper=coach_whisper, momentum=momentum, metrics={}, segments=[])
    db.add(turn)
    db.flush()
    return turn


def create_activity_conversation(svc: AppServices, db: Session, user: User, assessment: Assessment,
                                 activity_id: str) -> Conversation:
    activity = ACTIVITIES[activity_id]
    setup = ConversationSetup(
        title=activity.title, context=activity.context, target_behavior=None,
        suggested_seconds=activity.suggested_seconds, tips=list(activity.tips), activity_id=activity_id,
        mission_id=None, persona_id=None, difficulty=None, quick=False,
    )
    conv = Conversation(
        id=new_id("cnv"), user_id=user.id, kind="assessment_activity", status="active", awaiting="user",
        partner=dict(MAYA), setup=setup.model_dump(mode="json"),
        state={"tts_instructions": MAYA_TTS_INSTRUCTIONS, "character": MAYA_CHARACTER},
        assessment_id=assessment.id, activity_id=activity_id, language=assessment.language,
        max_user_turns=activity.max_user_turns, demo_mode=svc.demo_mode,
    )
    db.add(conv)
    db.flush()
    _add_partner_turn(svc, db, conv, activity.prompt)
    return conv


def create_mission_conversation(svc: AppServices, db: Session, user: User, mission_id: str, quick: bool,
                                language: str, difficulty: str | None = None) -> Conversation:
    """`difficulty="brutal"` is the app's "Harder challenge": the partner raises a tougher objection."""
    mission = MISSIONS.get(mission_id)
    if mission is None:
        raise not_found("Mission")
    if mission.partner is None:
        raise conflict("This mission doesn't include a conversation.")
    module = MODULES[mission.module_id]
    partner = mission.partner
    context = mission.context if mission.type != "real_life" else (mission.ai_alternative_title or mission.context)
    setup = ConversationSetup(
        title=mission.title, context=context, target_behavior=module.target_behavior,
        suggested_seconds=45 if quick else mission.suggested_seconds,
        tips=[f"Target: {module.target_behavior}",
              f"{partner.name} will push back hard — stay calm and adapt." if difficulty == "brutal"
              else f"{partner.name} may push back once — adapt to it."]
        if not quick else [f"Target: {module.target_behavior}"],
        activity_id=None, mission_id=mission_id, persona_id=None, difficulty=difficulty, quick=quick,
    )
    conv = Conversation(
        id=new_id("cnv"), user_id=user.id, kind="mission", status="active", awaiting="user",
        partner={"name": partner.name, "role": partner.role, "voice": partner.voice, "symbol": partner.symbol,
                 "color_hex": partner.color_hex},
        setup=setup.model_dump(mode="json"),
        state={"tts_instructions": partner.tts_instructions, "character": partner.character},
        mission_id=mission_id, quick=quick, difficulty=difficulty, language=language,
        max_user_turns=1 if quick else 2, demo_mode=svc.demo_mode,
    )
    db.add(conv)
    db.flush()
    _add_partner_turn(svc, db, conv, partner.opening)
    return conv


def create_spar_conversation(svc: AppServices, db: Session, user: User, *, language: str, title: str,
                             partner: dict[str, Any], opening: str, context: str, character: str,
                             win_condition: str, difficulty: str, tts_instructions: str, persona_id: str | None,
                             max_user_turns: int, extra_state: dict[str, Any] | None = None) -> Conversation:
    setup = ConversationSetup(
        title=title, context=context, target_behavior=None, suggested_seconds=45,
        tips=["Say it the way you would in real life.", "You can end the conversation whenever you like."],
        activity_id=None, mission_id=None, persona_id=persona_id, difficulty=difficulty, quick=False,
    )
    conv = Conversation(
        id=new_id("cnv"), user_id=user.id, kind="spar", status="active", awaiting="user", partner=partner,
        setup=setup.model_dump(mode="json"),
        state={"tts_instructions": tts_instructions, "character": character, "win_condition": win_condition,
               **(extra_state or {})},
        persona_id=persona_id, difficulty=difficulty, language=language, max_user_turns=max_user_turns,
        demo_mode=svc.demo_mode,
    )
    db.add(conv)
    db.flush()
    _add_partner_turn(svc, db, conv, opening, momentum=0.3)
    return conv


# ------------------------------------------------------------------------- reading


def get_owned(db: Session, user: User, conversation_id: str) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise not_found("Conversation")
    return conv


def turns_of(db: Session, conv: Conversation) -> list[Turn]:
    return list(db.scalars(select(Turn).where(Turn.conversation_id == conv.id).order_by(Turn.index)))


def turn_out(svc: AppServices, turn: Turn) -> TurnOut:
    quality_out = None
    if turn.speaker == "user" and turn.quality is not None:
        quality_out = TurnQuality.model_validate(turn.quality)
    return TurnOut(
        index=turn.index, speaker=turn.speaker, text=turn.text, audio_url=media_service.url_for(svc, turn.audio_media_id),
        created_at=iso_required(turn.created_at), quality=quality_out, coach_whisper=turn.coach_whisper,
        excluded=bool(turn.excluded),
    )


def conversation_out(svc: AppServices, db: Session, conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id, kind=conv.kind, status=conv.status, partner=Partner.model_validate(conv.partner),
        setup=ConversationSetup.model_validate(conv.setup), turns=[turn_out(svc, t) for t in turns_of(db, conv)],
        awaiting=conv.awaiting if conv.status == "active" else "none", user_turns=conv.user_turns,
        max_user_turns=conv.max_user_turns, assessment_id=conv.assessment_id, mission_id=conv.mission_id,
        demo_mode=conv.demo_mode, created_at=iso_required(conv.created_at),
    )


# ------------------------------------------------------------------------- turns


def _context_key(conv: Conversation) -> str:
    if conv.kind == "assessment_activity":
        return f"assessment:{conv.activity_id}"
    if conv.kind == "mission":
        return f"mission:{conv.mission_id}"
    return f"spar:{conv.persona_id or 'custom'}"


def _plan_step(conv: Conversation) -> tuple[str, str, str, bool]:
    """(step_key, instruction, fallback_line, is_closing) for the partner's next line."""
    k = conv.user_turns
    if conv.kind == "assessment_activity":
        activity = ACTIVITIES[conv.activity_id or ""]
        steps = activity.steps
        step = steps[-1] if k >= activity.max_user_turns else steps[min(k - 1, len(steps) - 2)]
        return step.key, step.instruction, step.fallback, step.key == "close"
    if conv.kind == "mission":
        mission = MISSIONS[conv.mission_id or ""]
        partner = mission.partner
        assert partner is not None
        if conv.quick or k >= conv.max_user_turns:
            return "close", CLOSE_INSTRUCTION + " Stay in your role.", "Okay, that's helpful. Thanks.", True
        if conv.difficulty == "brutal":
            return ("follow_up", partner.follow_up + " HARDER CHALLENGE: make the objection tougher and more "
                    "specific, sound unconvinced, and don't concede easily — but stay professional.",
                    "Honestly, I'm not convinced. " + partner.follow_up_fallback, False)
        if conv.difficulty == "kind":
            return ("follow_up", partner.follow_up + " Keep the objection gentle and easy to address.",
                    partner.follow_up_fallback, False)
        return "follow_up", partner.follow_up, partner.follow_up_fallback, False
    if k >= conv.max_user_turns:
        return ("close", "Give your final decision or reaction in character, in one or two sentences.",
                "Alright. Let me think about it and get back to you.", True)
    return ("respond", "Respond in character to their last turn and keep the scenario moving realistically.",
            "Go on — I'm listening.", False)


def _history(conv: Conversation, turns: list[Turn]) -> list[tuple[str, str]]:
    name = conv.partner.get("name", "Partner")
    history: list[tuple[str, str]] = []
    for turn in turns:
        if turn.speaker == "partner":
            history.append((name, turn.text))
        elif not turn.excluded and turn.text:
            history.append(("USER", turn.text))
    return history


def _store_turn_audio(svc: AppServices, db: Session, user: User, wav_path: str, duration: float) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "turn.m4a")
        try:
            ffmpeg.cut_clip(wav_path, out, 0.0, duration)
        except ffmpeg.AudioDecodeError:
            return None
        return media_service.store_file(svc, db, user_id=user.id, kind="turn_audio", path=out, ext="m4a",
                                        duration=duration).id


def _new_user_turn(db: Session, conv: Conversation, **fields: Any) -> Turn:
    last = db.scalar(select(Turn.index).where(Turn.conversation_id == conv.id).order_by(Turn.index.desc()).limit(1))
    turn = Turn(conversation_id=conv.id, index=0 if last is None else last + 1, speaker="user", **fields)
    db.add(turn)
    db.flush()
    return turn


def _mark_activity(db: Session, conv: Conversation, status: str) -> None:
    if conv.kind != "assessment_activity" or not conv.assessment_id:
        return
    assessment = db.get(Assessment, conv.assessment_id)
    if assessment is None:
        return
    state = dict(assessment.activity_state or {})
    entry = dict(state.get(conv.activity_id or "", {}))
    entry.update({"status": status, "conversation_id": conv.id})
    state[conv.activity_id or ""] = entry
    assessment.activity_state = state


def submit_turn(svc: AppServices, db: Session, user: User, conv: Conversation, upload_path: str,
                elapsed_seconds: float | None, client_metrics: dict[str, Any]) -> TurnResult:
    if conv.status != "active" or conv.awaiting != "user":
        raise conflict("This conversation isn't waiting for you to speak.")
    svc.limiter.check(f"ai:{user.id}", svc.settings.rate_limit_ai_per_hour)
    language = conv.language
    _mark_activity(db, conv, "in_progress")

    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "turn.wav")
        try:
            ffmpeg.decode_to_wav16k(upload_path, wav, max_seconds=svc.settings.max_turn_seconds)
        except ffmpeg.AudioDecodeError:
            bad = issue("file_unreadable")
            turn = _new_user_turn(db, conv, text="", excluded=True, metrics={},
                                  quality={"usable": "no", "issues": [bad.model_dump()], "speech_seconds": 0.0,
                                           "duration_seconds": 0.0})
            return TurnResult(conversation=conversation_out(svc, db, conv), user_turn=turn_out(svc, turn),
                              partner_turn=None, retry_suggested=True, done=False)
        samples = ffmpeg.read_wav(wav)
        duration = len(samples) / ffmpeg.SAMPLE_RATE
        report = quality.analyze(samples, min_speech_seconds=MIN_TURN_SPEECH_SECONDS)
        audio_media_id = _store_turn_audio(svc, db, user, wav, duration)
        base_metrics = {"elapsed_seconds": elapsed_seconds, "audio": report.as_dict(), "client": client_metrics}

        if report.usable == "no":
            issues = [issue(code, severity="blocking").model_dump() for code in report.blocking]
            turn = _new_user_turn(
                db, conv, text="", excluded=True, audio_media_id=audio_media_id, metrics=base_metrics,
                quality={"usable": "no", "issues": issues, "speech_seconds": round(report.speech_seconds, 1),
                         "duration_seconds": round(duration, 1)},
            )
            return TurnResult(conversation=conversation_out(svc, db, conv), user_turn=turn_out(svc, turn),
                              partner_turn=None, retry_suggested=True, done=False)

        mp3 = os.path.join(tmp, "turn.mp3")
        ffmpeg.encode_mp3(wav, mp3)
        hint = AudioHint(
            context_key=_context_key(conv), turn_index=conv.user_turns, wav_path=wav,
            mock_text=(client_metrics.get("mock_transcript") if svc.demo_mode else None),
        )
        prompt = VERBATIM_PROMPTS.get(language)
        with ThreadPoolExecutor(max_workers=2) as pool:
            transcription_future = pool.submit(svc.ai.transcribe, mp3, language=language, prompt=prompt, hint=hint)
            diarization_future = (
                pool.submit(svc.ai.diarize, mp3, language=language, known_speakers=[], hint=hint)
                if svc.settings.turn_background_check else None
            )
            transcription = transcription_future.result()  # AIUnavailableError ⇒ 503, audio can be resent
            diarization = None
            if diarization_future is not None:
                try:
                    diarization = diarization_future.result()
                except Exception as exc:  # noqa: BLE001 - background check is best-effort
                    log.warning("Background-voice check unavailable: %s", exc)

    text = transcription.text.strip()
    usable = report.usable
    issues_out = [issue(code, severity="warning") for code in report.issues]
    segments: list[dict[str, Any]] = []
    if diarization and diarization.segments:
        talk = Counter[str]()
        for seg in diarization.segments:
            talk[seg.speaker] += max(0.0, seg.end - seg.start)
        dominant, dominant_time = talk.most_common(1)[0]
        total = sum(talk.values()) or 1.0
        background = [s for s, t in talk.items()
                      if s != dominant and t >= BACKGROUND_MIN_SECONDS and t / total >= BACKGROUND_MIN_SHARE]
        segments = [{"speaker": s.speaker, "start": s.start, "end": s.end, "text": s.text,
                     "excluded": s.speaker != dominant} for s in diarization.segments]
        if background:
            issues_out.append(issue("background_voices"))
            usable = "partly"
            dominant_text = " ".join(s.text for s in diarization.segments if s.speaker == dominant).strip()
            if dominant_text and not svc.demo_mode:
                text = dominant_text  # only the user's own voice counts

    blocking: str | None = None
    if not text:
        blocking = "no_speech"
    elif transcription.avg_logprob is not None and transcription.avg_logprob < LOW_CONFIDENCE_BLOCK:
        blocking = "low_intelligibility"
    elif transcription.avg_logprob is not None and transcription.avg_logprob < LOW_CONFIDENCE_WARN:
        issues_out.append(issue("low_intelligibility"))
        usable = "partly"

    runs = report.speech_runs
    speech_start = runs[0][0] if runs else 0.0
    speech_end = runs[-1][1] if runs else duration
    span = max(0.1, speech_end - speech_start)
    metrics = {
        **base_metrics,
        **turn_metrics(text, span, quality.pauses_between(runs), language),
        "speech_start": speech_start,
        "speech_end": speech_end,
        "avg_logprob": transcription.avg_logprob,
        "transcription_model": transcription.model,
    }
    if blocking:
        turn = _new_user_turn(
            db, conv, text=text, excluded=True, audio_media_id=audio_media_id, metrics=metrics, segments=segments,
            quality={"usable": "no", "issues": [issue(blocking, severity="blocking").model_dump()],
                     "speech_seconds": round(report.speech_seconds, 1), "duration_seconds": round(duration, 1)},
        )
        return TurnResult(conversation=conversation_out(svc, db, conv), user_turn=turn_out(svc, turn),
                          partner_turn=None, retry_suggested=True, done=False)

    user_turn = _new_user_turn(
        db, conv, text=text, excluded=False, audio_media_id=audio_media_id, metrics=metrics, segments=segments,
        quality={"usable": usable, "issues": [i.model_dump() for i in issues_out],
                 "speech_seconds": round(report.speech_seconds, 1), "duration_seconds": round(duration, 1)},
    )
    conv.user_turns += 1

    partner_turn, done = _partner_respond(svc, db, conv)
    if done:
        conv.awaiting = "none"
        if conv.kind == "assessment_activity":
            conv.status = "finished"
            conv.finished_at = utcnow()
            _mark_activity(db, conv, "done")
    db.flush()
    return TurnResult(conversation=conversation_out(svc, db, conv), user_turn=turn_out(svc, user_turn),
                      partner_turn=turn_out(svc, partner_turn), retry_suggested=False, done=done)


def _partner_respond(svc: AppServices, db: Session, conv: Conversation) -> tuple[Turn, bool]:
    step_key, instruction, fallback, is_closing = _plan_step(conv)
    turns = turns_of(db, conv)
    partner = conv.partner
    difficulty = conv.difficulty
    request = PartnerReplyRequest(
        kind=conv.kind,
        language=conv.language,
        partner_name=partner.get("name", "Partner"),
        partner_role=partner.get("role", ""),
        partner_character=conv.state.get("character", ""),
        situation=conv.setup.get("context", ""),
        step_key=step_key,
        step_instruction=instruction,
        fallback_line=fallback,
        is_closing=is_closing,
        history=_history(conv, turns),
        difficulty=difficulty,
        difficulty_behaviour=DIFFICULTY_BEHAVIOUR.get(difficulty or "") if conv.kind in ("spar", "mission") else None,
        win_condition=conv.state.get("win_condition"),
        target_behavior=conv.setup.get("target_behavior"),
        want_coach_whisper=conv.kind == "spar",
        want_momentum=conv.kind == "spar",
        turns_left=max(0, conv.max_user_turns - conv.user_turns),
    )
    try:
        reply = svc.ai.partner_reply(request)
        text = reply.reply.strip() or fallback
        end = is_closing or (conv.kind == "spar" and reply.end_conversation)
        whisper = reply.coach_whisper if conv.kind == "spar" else None
        momentum = reply.momentum if conv.kind == "spar" else None
        if conv.kind == "spar" and reply.outcome_label:
            conv.state = {**conv.state, "outcome_label": reply.outcome_label}
    except AIUnavailableError as exc:
        log.warning("Partner reply fell back to script: %s", exc)
        text, end, whisper, momentum = fallback, is_closing, None, None
    turn = _add_partner_turn(svc, db, conv, text, coach_whisper=whisper, momentum=momentum)
    return turn, end


# ------------------------------------------------------------------------- finishing


def finish(svc: AppServices, db: Session, user: User, conv: Conversation) -> FinishResult:
    if conv.status != "finished":
        conv.status = "finished"
        conv.awaiting = "none"
        conv.finished_at = utcnow()
    result_ref: ResultRef | None = None
    if conv.kind == "assessment_activity":
        _mark_activity(db, conv, "done" if conv.user_turns > 0 else "skipped")
        result_ref = ResultRef(type="assessment", id=conv.assessment_id or "")
    elif conv.kind == "mission":
        attempt = db.scalar(select(MissionAttempt).where(MissionAttempt.conversation_id == conv.id))
        if attempt is None:
            count = len(list(db.scalars(select(MissionAttempt.id).where(
                MissionAttempt.user_id == user.id, MissionAttempt.mission_id == conv.mission_id))))
            attempt = MissionAttempt(id=new_id("att"), user_id=user.id, mission_id=conv.mission_id or "",
                                     conversation_id=conv.id, attempt_number=count + 1, quick=conv.quick,
                                     status="processing")
            db.add(attempt)
            db.flush()
            from . import progress  # local import: avoids a cycle

            progress.log_activity(db, user.id, "mission_attempt", conv.setup.get("title", "Mission attempt"),
                                  conversation_minutes(db, conv), attempt.id)
            db.commit()
            assert svc.jobs is not None
            svc.jobs.submit("mission.feedback", attempt.id)
            db.refresh(attempt)
        result_ref = ResultRef(type="mission_attempt", id=attempt.id)
    else:
        report = db.get(SparReport, conv.id)
        if report is None:
            db.add(SparReport(conversation_id=conv.id, user_id=user.id, status="processing"))
            from . import progress

            progress.log_activity(db, user.id, "spar_session", conv.setup.get("title", "Spar"),
                                  conversation_minutes(db, conv), conv.id)
            db.commit()
            assert svc.jobs is not None
            svc.jobs.submit("spar.report", conv.id)
        result_ref = ResultRef(type="spar_report", id=conv.id)
    db.flush()
    return FinishResult(conversation=conversation_out(svc, db, conv), result_ref=result_ref)


def conversation_minutes(db: Session, conv: Conversation) -> float:
    total = 0.0
    for turn in turns_of(db, conv):
        if turn.speaker == "user":
            total += float((turn.metrics or {}).get("duration") or 0.0)
        else:
            total += len(turn.text.split()) / 2.5
    return round(total / 60.0, 2)


# ------------------------------------------------------------------------- evidence units


def units_for(conv: Conversation, turns: list[Turn], uid_prefix: str = "") -> list[Unit]:
    units: list[Unit] = []
    partner_name = conv.partner.get("name", "Partner")
    for turn in turns:
        uid = f"{uid_prefix}T{turn.index}"
        if turn.speaker == "partner":
            units.append(Unit(uid=uid, role="partner", speaker_name=partner_name, text=turn.text,
                              source_type="conversation", source_id=conv.id, turn_index=turn.index,
                              activity_id=conv.activity_id, duration=len(turn.text.split()) / 2.5))
            continue
        metrics = turn.metrics or {}
        reasons = [i.get("code") for i in (turn.quality or {}).get("issues", []) if i.get("severity") == "blocking"]
        units.append(Unit(
            uid=uid, role="user", speaker_name="You", text=turn.text, source_type="conversation", source_id=conv.id,
            turn_index=turn.index, start=metrics.get("speech_start"), end=metrics.get("speech_end"),
            media_id=turn.audio_media_id, activity_id=conv.activity_id, excluded=bool(turn.excluded) or not turn.text,
            exclusion_reason=(reasons[0] if reasons else ("unclear" if turn.excluded else None)),
            duration=float(metrics.get("duration") or 0.0),
        ))
    return units


def parse_client_metrics(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}
