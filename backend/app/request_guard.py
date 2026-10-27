"""Reject oversized or unauthenticated uploads before any of the body is read.

FastAPI parses a multipart form, spooling every file part to disk, before route dependencies run, so the size
check in `save_upload` and the token check in `current_user` come too late to protect the disk. This ASGI
middleware checks the bearer token for multipart requests and caps every request body up front: by
Content-Length when it's given, and by counting bytes as they arrive (chunked bodies, or a Content-Length that
lies).
"""

from __future__ import annotations

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .security import verify_token

# Room for the form fields and boundaries around the audio file itself.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024
# JSON bodies are small (the largest is a signed App Store transaction, a few KB).
MAX_JSON_BYTES = 1024 * 1024


def _too_large(limit: int) -> str:
    return f"That request is too large (max {limit // (1024 * 1024)} MB)."


class RequestGuard:
    def __init__(self, app: ASGIApp, *, secret_key: str, max_upload_bytes: int):
        self.app = app
        self.secret_key = secret_key
        self.max_multipart_bytes = max_upload_bytes + MULTIPART_OVERHEAD_BYTES

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        multipart = headers.get("content-type", "").lower().startswith("multipart/")
        limit = self.max_multipart_bytes if multipart else MAX_JSON_BYTES

        if multipart:
            authorization = headers.get("authorization", "")
            token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
            if not token or verify_token(self.secret_key, token) is None:
                await _reject(scope, receive, send, 401, "unauthorized", "Please sign in again.")
                return
        length = headers.get("content-length")
        if length is not None:
            if not length.isdigit():
                await _reject(scope, receive, send, 400, "validation_error", "Invalid Content-Length.")
                return
            if int(length) > limit:
                await _reject(scope, receive, send, 413, "file_too_large", _too_large(limit))
                return

        received = 0

        async def counted_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI re-raises HTTPException from body parsing, and the app renders it as 413.
                    raise HTTPException(413, _too_large(limit))
            return message

        await self.app(scope, counted_receive, send)


async def _reject(scope: Scope, receive: Receive, send: Send, status: int, code: str, message: str) -> None:
    response = JSONResponse(status_code=status, content={"error": {"code": code, "message": message}},
                            headers={"Connection": "close"})
    await response(scope, receive, send)
