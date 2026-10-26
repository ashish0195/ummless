"""Consistent error envelope: `{"error": {"code": "...", "message": "..."}}`."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("comlogue.errors")


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def not_found(what: str = "Resource") -> APIError:
    return APIError(404, "not_found", f"{what} not found.")


def conflict(message: str) -> APIError:
    return APIError(409, "conflict", message)


def validation(message: str) -> APIError:
    return APIError(422, "validation_error", message)


def subscription_required(message: str = "This is part of Comlogue Pro.") -> APIError:
    return APIError(402, "subscription_required", message)


def consent_required() -> APIError:
    return APIError(
        403,
        "consent_required",
        "Please review and accept how Comlogue analyzes your voice before recording.",
    )


class AIUnavailableError(Exception):
    """Raised when the AI provider failed after retries and model fallbacks."""


def ai_unavailable(detail: str | None = None) -> APIError:
    message = "Our AI coach is temporarily unavailable. Your audio wasn't lost — please try again."
    if detail:
        log.warning("AI unavailable: %s", detail)
    return APIError(503, "ai_unavailable", message)


_STATUS_CODES = {
    400: "validation_error",
    401: "unauthorized",
    402: "subscription_required",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "file_too_large",
    415: "unsupported_media",
    422: "validation_error",
    429: "rate_limited",
    503: "ai_unavailable",
}


def _envelope(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return _envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(AIUnavailableError)
    async def _ai_error(_: Request, exc: AIUnavailableError) -> JSONResponse:
        err = ai_unavailable(str(exc))
        return _envelope(err.status, err.code, err.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        detail = first.get("msg", "Invalid request.")
        message = f"{location}: {detail}" if location else detail
        return _envelope(422, "validation_error", message)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "internal")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _envelope(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error", exc_info=exc)
        return _envelope(500, "internal", "Something went wrong on our side. Please try again.")
