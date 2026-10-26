"""Health, metadata, auth, the current user, and voice reference."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.orm import Session

from ..core import AppServices
from ..deps import current_user, get_db, get_services, save_upload
from ..domain.recording_rules import rules_for
from ..models import User
from ..schemas import (
    DeviceAuthRequest,
    DeviceAuthResponse,
    Health,
    Me,
    MePatch,
    Meta,
    RecordingRules,
    VoiceEnrollmentResult,
    VoiceReferenceStatus,
)
from ..security import issue_token
from ..services import account, users, voice_reference
from ..services import meta as meta_service

router = APIRouter(prefix="/v1")


@router.get("/health", response_model=Health, tags=["meta"])
def health(svc: AppServices = Depends(get_services)) -> Health:
    return Health(status="ok", demo_mode=svc.demo_mode, version=svc.settings.version)


@router.get("/meta", response_model=Meta, tags=["meta"])
def meta(svc: AppServices = Depends(get_services), _: User = Depends(current_user)) -> Meta:
    return meta_service.build(svc)


@router.get("/meta/recording-rules", response_model=RecordingRules, tags=["meta"])
def recording_rules(region: str | None = None, _: User = Depends(current_user)) -> RecordingRules:
    return rules_for(region)


@router.post("/auth/device", response_model=DeviceAuthResponse, tags=["auth"])
def auth_device(body: DeviceAuthRequest, svc: AppServices = Depends(get_services),
                db: Session = Depends(get_db)) -> DeviceAuthResponse:
    user, is_new = users.get_or_create_by_device(db, body.device_id, body.platform, body.app_version)
    token = issue_token(svc.settings.secret_key, user.id, svc.settings.token_ttl_days)
    return DeviceAuthResponse(token=token, user_id=user.id, is_new=is_new)


@router.get("/me", response_model=Me, tags=["me"])
def get_me(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
           user: User = Depends(current_user)) -> Me:
    return users.build_me(svc, db, user)


@router.patch("/me", response_model=Me, tags=["me"])
def patch_me(body: MePatch, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
             user: User = Depends(current_user)) -> Me:
    users.apply_patch(user, body)
    db.flush()
    return users.build_me(svc, db, user)


@router.delete("/me", status_code=204, tags=["me"])
def delete_me(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
              user: User = Depends(current_user)) -> Response:
    account.delete_account(svc, db, user)
    return Response(status_code=204)


@router.get("/voice-reference", response_model=VoiceReferenceStatus, tags=["voice"])
def get_voice_reference(db: Session = Depends(get_db), user: User = Depends(current_user)) -> VoiceReferenceStatus:
    return users.voice_reference_status(db, user)


@router.post("/voice-reference", response_model=VoiceEnrollmentResult, tags=["voice"])
def post_voice_reference(
    audio: UploadFile = File(...),
    consent_version: str = Form(...),
    consent_accepted: bool = Form(...),
    svc: AppServices = Depends(get_services),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> VoiceEnrollmentResult:
    upload = save_upload(audio, 20 * 1024 * 1024)
    try:
        return voice_reference.enroll(svc, db, user, upload.path, consent_version, consent_accepted)
    finally:
        upload.cleanup()


@router.delete("/voice-reference", status_code=204, tags=["voice"])
def delete_voice_reference(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                           user: User = Depends(current_user)) -> Response:
    voice_reference.delete(svc, db, user)
    return Response(status_code=204)
