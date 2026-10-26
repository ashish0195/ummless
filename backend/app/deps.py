"""FastAPI dependencies: services, DB session, authenticated user, upload handling."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator

from fastapi import Depends, Request, UploadFile
from sqlalchemy.orm import Session

from .core import AppServices
from .errors import APIError
from .models import User
from .security import verify_token
from .timeutil import as_utc, utcnow


def get_services(request: Request) -> AppServices:
    return request.app.state.services


def get_db(svc: AppServices = Depends(get_services)) -> Iterator[Session]:
    session = svc.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


def current_user(request: Request, svc: AppServices = Depends(get_services), db: Session = Depends(get_db)) -> User:
    token = bearer_token(request)
    claims = verify_token(svc.settings.secret_key, token) if token else None
    if claims is None:
        raise APIError(401, "unauthorized", "Please sign in again.")
    user = db.get(User, claims.user_id)
    if user is None:
        raise APIError(401, "unauthorized", "This account no longer exists.")
    now = utcnow()
    if user.last_active_at is None or (now - as_utc(user.last_active_at)).total_seconds() > 300:
        user.last_active_at = now
    return user


class SavedUpload:
    """An uploaded file spooled to a temp path, with size enforcement."""

    def __init__(self, path: str, filename: str | None, directory: str):
        self.path = path
        self.filename = filename
        self._directory = directory

    def cleanup(self) -> None:
        shutil.rmtree(self._directory, ignore_errors=True)


def save_upload(upload: UploadFile, max_bytes: int) -> SavedUpload:
    directory = tempfile.mkdtemp(prefix="comlogue-upload-")
    suffix = os.path.splitext(upload.filename or "")[1][:6] or ".bin"
    path = os.path.join(directory, f"upload{suffix}")
    written = 0
    with open(path, "wb") as handle:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                handle.close()
                shutil.rmtree(directory, ignore_errors=True)
                raise APIError(413, "file_too_large", f"That file is too large (max {max_bytes // (1024 * 1024)} MB).")
            handle.write(chunk)
    if written == 0:
        shutil.rmtree(directory, ignore_errors=True)
        raise APIError(422, "validation_error", "The uploaded file is empty.")
    return SavedUpload(path, upload.filename, directory)
