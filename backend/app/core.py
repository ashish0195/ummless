"""Process-wide services shared by request handlers and background jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from .ai.provider import AIProvider
from .config import Settings
from .ratelimit import RateLimiter
from .storage import Storage

if TYPE_CHECKING:  # pragma: no cover
    from .jobs import JobRunner


@dataclass
class AppServices:
    settings: Settings
    session_factory: sessionmaker[Session]
    storage: Storage
    ai: AIProvider
    limiter: RateLimiter = field(default_factory=RateLimiter)
    jobs: JobRunner | None = None

    @property
    def demo_mode(self) -> bool:
        return self.ai.demo
