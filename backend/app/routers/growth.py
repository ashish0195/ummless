"""Profile, course & missions, spar, talks, events, progress, review, billing and media."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..core import AppServices
from ..deps import bearer_token, current_user, get_db, get_services
from ..errors import APIError, not_found
from ..models import Media, User
from ..schemas import (
    AppStoreTransaction,
    Course,
    DemoSeedRequest,
    DemoSeedResult,
    DevGrant,
    Entitlement,
    EventCreate,
    EventList,
    FeedbackReportCreate,
    FeedbackReportOut,
    FocusChange,
    MissionComplete,
    MissionOut,
    PersonaList,
    Profile,
    Progress,
    ReflectionCreate,
    ReflectionOut,
    SparReportOut,
    SparSessionList,
    Talk,
    TalkList,
    TrackChange,
    UpcomingEventOut,
    WeeklyReview,
)
from ..security import verify_media_signature, verify_token
from ..services import billing, demo_seed, events, feedback, profile, progress, review, spar, talks
from ..services import course as course_service
from ..services import media as media_service

router = APIRouter(prefix="/v1")


@router.get("/profile", response_model=Profile, tags=["profile"])
def get_profile(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                user: User = Depends(current_user)) -> Profile:
    return profile.build(svc, db, user)


# ------------------------------------------------------------------ course


@router.get("/course", response_model=Course, tags=["course"])
def get_course(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
               user: User = Depends(current_user)) -> Course:
    return course_service.build_course(svc, db, user)


@router.post("/course/track", response_model=Course, tags=["course"])
def change_track(body: TrackChange, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                 user: User = Depends(current_user)) -> Course:
    course_service.set_track(user, body.track)
    db.flush()
    return course_service.build_course(svc, db, user)


@router.post("/course/focus", response_model=Course, tags=["course"])
def change_focus(body: FocusChange, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                 user: User = Depends(current_user)) -> Course:
    course_service.set_focus(user, body.module_id)
    db.flush()
    return course_service.build_course(svc, db, user)


@router.get("/missions/{mission_id}", response_model=MissionOut, tags=["course"])
def get_mission(mission_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                user: User = Depends(current_user)) -> MissionOut:
    return course_service.mission_out(svc, db, user, mission_id)


@router.post("/missions/{mission_id}/complete", response_model=MissionOut, tags=["course"])
def complete_mission(mission_id: str, body: MissionComplete, svc: AppServices = Depends(get_services),
                     db: Session = Depends(get_db), user: User = Depends(current_user)) -> MissionOut:
    course_service.complete_mission(db, user, mission_id, body.takeaway)
    return course_service.mission_out(svc, db, user, mission_id)


@router.post("/missions/{mission_id}/reflections", response_model=ReflectionOut, tags=["course"])
def add_reflection(mission_id: str, body: ReflectionCreate, svc: AppServices = Depends(get_services),
                   db: Session = Depends(get_db), user: User = Depends(current_user)) -> ReflectionOut:
    return course_service.add_reflection(svc, db, user, mission_id, body)


# ------------------------------------------------------------------ spar, talks, events


@router.get("/spar/personas", response_model=PersonaList, tags=["spar"])
def get_personas(user: User = Depends(current_user)) -> PersonaList:
    return spar.personas(user)


@router.get("/spar/sessions", response_model=SparSessionList, tags=["spar"])
def get_spar_sessions(db: Session = Depends(get_db), user: User = Depends(current_user)) -> SparSessionList:
    return SparSessionList(items=spar.sessions(db, user))


@router.get("/spar/reports/{conversation_id}", response_model=SparReportOut, tags=["spar"])
def get_spar_report(conversation_id: str, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                    user: User = Depends(current_user)) -> SparReportOut:
    return spar.report_out(svc, db, user, conversation_id)


@router.get("/talks", response_model=TalkList, tags=["talks"])
def list_talks(svc: AppServices = Depends(get_services), _: User = Depends(current_user)) -> TalkList:
    return talks.list_talks(svc)


@router.get("/talks/{talk_id}", response_model=Talk, tags=["talks"])
def get_talk(talk_id: str, svc: AppServices = Depends(get_services), user: User = Depends(current_user)) -> Talk:
    return talks.talk_detail(svc, user, talk_id)


@router.get("/talks/{talk_id}/lines/{index}/audio", tags=["talks"], response_class=FileResponse)
def talk_line_audio(talk_id: str, index: int, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                    user: User = Depends(current_user)) -> FileResponse:
    media = talks.line_audio(svc, db, user, talk_id, index)
    return FileResponse(media_service.local_path(svc, media), media_type=media.content_type)


@router.get("/events", response_model=EventList, tags=["events"])
def list_events(db: Session = Depends(get_db), user: User = Depends(current_user)) -> EventList:
    return EventList(events=[events.to_out(e) for e in events.list_for(db, user)])


@router.post("/events", response_model=UpcomingEventOut, tags=["events"])
def create_event(body: EventCreate, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                 user: User = Depends(current_user)) -> UpcomingEventOut:
    return events.to_out(events.create(svc, db, user, body))


@router.post("/events/{event_id}/reflection", response_model=UpcomingEventOut, tags=["events"])
def reflect_on_event(event_id: str, body: ReflectionCreate, svc: AppServices = Depends(get_services),
                     db: Session = Depends(get_db), user: User = Depends(current_user)) -> UpcomingEventOut:
    """"How did it go?" after the day. The first one counts as a real-life practice session."""
    return events.to_out(events.reflect(svc, db, user, event_id, body))


@router.delete("/events/{event_id}", status_code=204, tags=["events"])
def delete_event(event_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Response:
    events.delete(db, user, event_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ progress & review


@router.get("/progress", response_model=Progress, tags=["progress"])
def get_progress(db: Session = Depends(get_db), user: User = Depends(current_user)) -> Progress:
    return progress.build(db, user)


@router.get("/review/weekly", response_model=WeeklyReview, tags=["progress"])
def get_weekly_review(svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
                      user: User = Depends(current_user)) -> WeeklyReview:
    return review.build(svc, db, user)


# ------------------------------------------------------------------ billing


@router.post("/billing/app-store", response_model=Entitlement, tags=["billing"])
def app_store(body: AppStoreTransaction, svc: AppServices = Depends(get_services),
              user: User = Depends(current_user)) -> Entitlement:
    return billing.apply_app_store_transaction(svc.settings, user, body.signed_transaction)


@router.post("/billing/dev-grant", response_model=Entitlement, tags=["billing"])
def dev_grant(body: DevGrant, svc: AppServices = Depends(get_services), user: User = Depends(current_user)) -> Entitlement:
    return billing.dev_grant(svc.settings, user, body.tier)


# ------------------------------------------------------------------ media


@router.get("/media/{media_id}", tags=["media"], response_class=FileResponse)
def get_media(media_id: str, request: Request, exp: int | None = None, sig: str | None = None,
              svc: AppServices = Depends(get_services), db: Session = Depends(get_db)) -> FileResponse:
    media = db.get(Media, media_id)
    if media is None:
        raise not_found("Media")
    allowed = exp is not None and sig is not None and verify_media_signature(svc.settings.secret_key, media_id, exp, sig)
    if not allowed:
        token = bearer_token(request)
        claims = verify_token(svc.settings.secret_key, token) if token else None
        if claims is None:
            raise APIError(401, "unauthorized", "This link has expired.")
        if media.user_id is not None and media.user_id != claims.user_id:
            raise not_found("Media")
    path = media_service.local_path(svc, media)
    if not svc.storage.exists(media.storage_key):
        raise not_found("Media")
    return FileResponse(path, media_type=media.content_type, headers={"Cache-Control": "private, max-age=3600"})


# ------------------------------------------------------------------ feedback reports & dev tools


@router.post("/feedback-reports", response_model=FeedbackReportOut, status_code=201, tags=["feedback"])
def create_feedback_report(body: FeedbackReportCreate, db: Session = Depends(get_db),
                           user: User = Depends(current_user)) -> FeedbackReportOut:
    """"This looks wrong" reports. Stored for review; they never change results."""
    return feedback.create(db, user, body)


@router.post("/dev/seed-demo", response_model=DemoSeedResult, tags=["dev"])
def seed_demo(body: DemoSeedRequest, svc: AppServices = Depends(get_services), db: Session = Depends(get_db),
              user: User = Depends(current_user)) -> DemoSeedResult:
    """Seed a rich demo state for the calling user (development and screenshots only)."""
    if not svc.settings.dev_entitlements_allowed:
        raise not_found("Endpoint")
    return demo_seed.seed(svc, db, user, body.pro, body.market)
