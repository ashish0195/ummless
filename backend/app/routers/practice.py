"""Conversations (AI voice engine), assessments and recordings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from ..core import AppServices
from ..deps import current_user, get_db, get_services, save_upload
from ..errors import validation
from ..models import User
from ..schemas import (
    AssessmentCreate,
    AssessmentList,
    AssessmentOut,
    ConversationCreate,
    ConversationOut,
    FinishResult,
    RecordingConsent,
    RecordingList,
    RecordingOut,
    SpeakerConfirmation,
    Transcript,
    TurnResult,
)
from ..services import assessments, conversations, daily, group, recordings, spar, users
from ..services import course as course_service

router = APIRouter(prefix="/v1")


# ------------------------------------------------------------------ conversations


@router.post("/conversations", response_model=ConversationOut, tags=["conversations"])
def create_conversation(body: ConversationCreate, svc: AppServices = Depends(get_services),
                        db: Session = Depends(get_db), user: User = Depends(current_user)) -> ConversationOut:
    if body.kind == "mission":
        users.require_analysis_consent(user)
        if not body.mission_id:
            raise validation("mission_id is required.")
        mission = course_service._mission(body.mission_id)
        course_service.ensure_unlocked(db, user, mission)
        conv = conversations.create_mission_conversation(svc, db, user, body.mission_id, body.quick,
                                                         users.language(user), body.difficulty)
    elif body.kind == "daily":
        conv = daily.create_conversation(svc, db, user, body.daily_date)
    elif body.kind == "group":
        conv = group.create(svc, db, user, body)
    else:
        conv = spar.create(svc, db, user, body)
    return conversations.conversation_out(svc, db, conv)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut, tags=["conversations"])
def get_conversation(conversation_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                     user: User = Depends(current_user)) -> ConversationOut:
    return conversations.conversation_out(svc, db, conversations.get_owned(db, user, conversation_id))


@router.post("/conversations/{conversation_id}/turns", response_model=TurnResult, tags=["conversations"])
def post_turn(
    conversation_id: str,
    audio: UploadFile = File(...),
    elapsed_seconds: float | None = Form(None),
    client_metrics: str | None = Form(None),
    svc: AppServices = Depends(get_services),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> TurnResult:
    users.require_analysis_consent(user)
    conv = conversations.get_owned(db, user, conversation_id)
    upload = save_upload(audio, svc.settings.max_upload_bytes)
    try:
        return conversations.submit_turn(svc, db, user, conv, upload.path, elapsed_seconds,
                                         conversations.parse_client_metrics(client_metrics))
    finally:
        upload.cleanup()


@router.post("/conversations/{conversation_id}/finish", response_model=FinishResult, tags=["conversations"])
def finish_conversation(conversation_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                        user: User = Depends(current_user)) -> FinishResult:
    conv = conversations.get_owned(db, user, conversation_id)
    return conversations.finish(svc, db, user, conv)


# ------------------------------------------------------------------ assessments


@router.post("/assessments", response_model=AssessmentOut, tags=["assessments"])
def create_assessment(body: AssessmentCreate, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                      user: User = Depends(current_user)) -> AssessmentOut:
    return assessments.to_out(svc, assessments.create(svc, db, user, body))


@router.get("/assessments", response_model=AssessmentList, tags=["assessments"])
def list_assessments(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                     user: User = Depends(current_user)) -> AssessmentList:
    return AssessmentList(items=[assessments.to_out(svc, a) for a in assessments.list_for(db, user)])


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut, tags=["assessments"])
def get_assessment(assessment_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                   user: User = Depends(current_user)) -> AssessmentOut:
    return assessments.to_out(svc, assessments.get_owned(db, user, assessment_id))


@router.post("/assessments/{assessment_id}/activities/{activity_id}/start", response_model=ConversationOut,
             tags=["assessments"])
def start_activity(assessment_id: str, activity_id: str, svc: AppServices = Depends(get_services),
                   db: Session = Depends(get_db), user: User = Depends(current_user)) -> ConversationOut:
    users.require_analysis_consent(user)
    assessment = assessments.get_owned(db, user, assessment_id)
    return assessments.start_activity(svc, db, user, assessment, activity_id)


@router.post("/assessments/{assessment_id}/activities/{activity_id}/skip", response_model=AssessmentOut,
             tags=["assessments"])
def skip_activity(assessment_id: str, activity_id: str, svc: AppServices = Depends(get_services),
                  db: Session = Depends(get_db), user: User = Depends(current_user)) -> AssessmentOut:
    assessment = assessments.get_owned(db, user, assessment_id)
    assessments.skip_activity(db, assessment, activity_id)
    return assessments.to_out(svc, assessment)


@router.post("/assessments/{assessment_id}/finalize", response_model=AssessmentOut, tags=["assessments"])
def finalize_assessment(assessment_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                        user: User = Depends(current_user)) -> AssessmentOut:
    assessment = assessments.get_owned(db, user, assessment_id)
    assessments.finalize(svc, db, user, assessment)
    return assessments.to_out(svc, assessment)


# ------------------------------------------------------------------ recordings


@router.post("/recordings", response_model=RecordingOut, tags=["recordings"])
def create_recording(
    audio: UploadFile = File(...),
    source: str = Form("upload"),
    title: str | None = Form(None),
    consent: str = Form(...),
    svc: AppServices = Depends(get_services),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> RecordingOut:
    if source not in ("upload", "live"):
        raise validation("source must be 'upload' or 'live'.")
    try:
        consent_body = RecordingConsent.model_validate_json(consent)
    except ValueError as exc:
        raise validation("consent must be a JSON object with attested and consent_version.") from exc
    users.require_analysis_consent(user)
    upload = save_upload(audio, svc.settings.max_upload_bytes)
    try:
        recording = recordings.create(svc, db, user, upload.path, upload.filename, source, title, consent_body)
    finally:
        upload.cleanup()
    return recordings.to_out(svc, recording)


@router.get("/recordings", response_model=RecordingList, tags=["recordings"])
def list_recordings(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                    user: User = Depends(current_user)) -> RecordingList:
    return RecordingList(items=[recordings.to_out(svc, r) for r in recordings.list_for(db, user)])


@router.get("/recordings/{recording_id}", response_model=RecordingOut, tags=["recordings"])
def get_recording(recording_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                  user: User = Depends(current_user)) -> RecordingOut:
    return recordings.to_out(svc, recordings.get_owned(db, user, recording_id))


@router.post("/recordings/{recording_id}/speaker-confirmation", response_model=RecordingOut, tags=["recordings"])
def confirm_speaker(recording_id: str, body: SpeakerConfirmation, svc: AppServices = Depends(get_services),
                    db: Session = Depends(get_db), user: User = Depends(current_user)) -> RecordingOut:
    recording = recordings.get_owned(db, user, recording_id)
    recordings.confirm_speaker(svc, db, user, recording, body)
    return recordings.to_out(svc, recording)


@router.post("/recordings/{recording_id}/retry", response_model=RecordingOut, tags=["recordings"])
def retry_recording(recording_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                    user: User = Depends(current_user)) -> RecordingOut:
    recording = recordings.get_owned(db, user, recording_id)
    recordings.retry(svc, db, recording)
    return recordings.to_out(svc, recording)


@router.get("/recordings/{recording_id}/transcript", response_model=Transcript, tags=["recordings"])
def recording_transcript(recording_id: str, db: Session = Depends(get_db),
                         user: User = Depends(current_user)) -> Transcript:
    return recordings.transcript(recordings.get_owned(db, user, recording_id))


@router.delete("/recordings/{recording_id}", status_code=204, tags=["recordings"])
def delete_recording(recording_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                     user: User = Depends(current_user)) -> Response:
    recordings.delete_recording(svc, db, recordings.get_owned(db, user, recording_id))
    return Response(status_code=204)
