"""Comlogue API — application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .ai.factory import build_provider
from .config import Settings, get_settings
from .core import AppServices
from .db import Base, make_engine, make_session_factory
from .errors import install_error_handlers
from .jobs import JobRunner
from .migrations import add_missing_columns
from .models import Assessment, DailyAttempt, MissionAttempt, Recording, SparReport
from .push import build_sender
from .request_guard import RequestGuard
from .routers import core as core_router
from .routers import growth as growth_router
from .routers import habit as habit_router
from .routers import practice as practice_router
from .services import assessments, course, daily, recordings, spar
from .services.notifications import NotificationScheduler
from .storage import LocalStorage

log = logging.getLogger("comlogue")


def _recover_jobs(svc: AppServices) -> None:
    """Re-enqueue work that was in flight when the process stopped."""
    assert svc.jobs is not None
    with svc.session_factory() as db:
        pending = [
            *[("assessment.finalize", a.id) for a in db.scalars(select(Assessment).where(Assessment.status == "processing"))],
            *[("recording.process", r.id) for r in db.scalars(select(Recording).where(Recording.status == "processing"))],
            *[("recording.assess", r.id) for r in db.scalars(select(Recording).where(Recording.status == "assessing"))],
            *[("mission.feedback", a.id) for a in db.scalars(select(MissionAttempt).where(MissionAttempt.status == "processing"))],
            *[("daily.feedback", a.id) for a in db.scalars(select(DailyAttempt).where(DailyAttempt.status == "processing"))],
            *[("spar.report", s.conversation_id) for s in db.scalars(select(SparReport).where(SparReport.status == "processing"))],
        ]
    for kind, ref_id in pending:
        log.info("Recovering job %s(%s)", kind, ref_id)
        svc.jobs.submit(kind, ref_id)


def build_services(settings: Settings) -> AppServices:
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    add_missing_columns(engine)
    services = AppServices(
        settings=settings,
        session_factory=make_session_factory(engine),
        storage=LocalStorage(settings.media_dir),
        ai=build_provider(settings),
        push=build_sender(settings),
    )
    runner = JobRunner(services, inline=settings.jobs_inline, workers=settings.job_workers)
    runner.register("assessment.finalize", assessments.run_finalize_job)
    runner.register("recording.process", recordings.run_process_job)
    runner.register("recording.assess", recordings.run_assess_job)
    runner.register("mission.feedback", course.run_feedback_job)
    runner.register("daily.feedback", daily.run_feedback_job)
    runner.register("spar.report", spar.run_report_job)
    services.jobs = runner
    return services


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    services = build_services(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _recover_jobs(services)
        scheduler = None
        if settings.scheduler_enabled:
            scheduler = NotificationScheduler(services, settings.notifications_tick_seconds)
            scheduler.start()
        yield
        if scheduler is not None:
            scheduler.stop()
        if services.jobs is not None:
            services.jobs.shutdown()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Backend for Comlogue, an AI communication coach. Evidence-based, partial profiles; no overall score. "
            "See docs/API.md for the contract."
        ),
        lifespan=lifespan,
    )
    app.state.services = services
    app.add_middleware(RequestGuard, secret_key=settings.secret_key, max_upload_bytes=settings.max_upload_bytes)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                           allow_headers=["*"])
    install_error_handlers(app)
    app.include_router(core_router.router)
    app.include_router(practice_router.router)
    app.include_router(growth_router.router)
    app.include_router(habit_router.router)
    return app


_default_app: FastAPI | None = None


def __getattr__(name: str) -> FastAPI:
    """`uvicorn app.main:app` — the default app is created lazily, so importing this module has no side effects."""
    global _default_app
    if name == "app":
        if _default_app is None:
            _default_app = create_app()
        return _default_app
    raise AttributeError(name)
