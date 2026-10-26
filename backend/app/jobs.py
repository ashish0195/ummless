"""Background job runner.

In-process thread pool. Job state lives in the database (status fields on the rows being processed), so
on startup any item left in a processing state is re-enqueued — restart-safe without a broker. For
multi-instance deployments, swap this for a queue (RQ/Celery/Arq) behind the same `submit` interface.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .core import AppServices

log = logging.getLogger("comlogue.jobs")

JobHandler = Callable[["AppServices", str], None]


class JobRunner:
    def __init__(self, services: AppServices, *, inline: bool, workers: int):
        self.services = services
        self.inline = inline
        self._handlers: dict[str, JobHandler] = {}
        self._executor = None if inline else ThreadPoolExecutor(max_workers=workers, thread_name_prefix="job")
        self._active: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def register(self, kind: str, handler: JobHandler) -> None:
        self._handlers[kind] = handler

    def submit(self, kind: str, ref_id: str) -> None:
        key = (kind, ref_id)
        with self._lock:
            if key in self._active:
                return
            self._active.add(key)
        if self._executor is None:
            self._run(kind, ref_id)
        else:
            self._executor.submit(self._run, kind, ref_id)

    def _run(self, kind: str, ref_id: str) -> None:
        handler = self._handlers.get(kind)
        try:
            if handler is None:
                log.error("No handler for job %s", kind)
                return
            handler(self.services, ref_id)
        except Exception:  # noqa: BLE001 - handlers record their own failures; this is the last resort
            log.exception("Job %s(%s) crashed", kind, ref_id)
        finally:
            with self._lock:
                self._active.discard((kind, ref_id))

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
