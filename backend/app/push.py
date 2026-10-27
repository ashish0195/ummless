"""Push delivery. `NullSender` (inbox only) is the default; `ApnsSender` talks to Apple when APNS_* is configured.

APNs: HTTP/2 to api.push.apple.com (or the sandbox host, per device), token-based auth with an ES256 JWT signed
by the team's .p8 key. Apple wants the provider token refreshed at most every 20 minutes and at least every hour,
so it's cached for 40 minutes and refreshed early when APNs reports it expired.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import jwt

from .config import Settings

log = logging.getLogger("comlogue.push")

PRODUCTION_HOST = "https://api.push.apple.com"
SANDBOX_HOST = "https://api.sandbox.push.apple.com"
TOKEN_TTL_SECONDS = 40 * 60
INVALID_TOKEN_REASONS = {"BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered", "ExpiredToken"}
PROVIDER_TOKEN_REASONS = {"ExpiredProviderToken", "InvalidProviderToken", "MissingProviderToken"}


@dataclass
class PushMessage:
    token: str
    environment: str  # "sandbox" | "production"
    title: str
    body: str
    badge: int
    thread_id: str
    collapse_id: str
    interruption_level: str  # "active" | "passive" | "time-sensitive"
    deep_link: str
    notification_id: str
    expires_at: int = 0  # unix seconds; 0 = deliver now or never

    def payload(self) -> dict[str, Any]:
        return {
            "aps": {
                "alert": {"title": self.title, "body": self.body},
                "sound": "default",
                "badge": self.badge,
                "thread-id": self.thread_id,
                "interruption-level": self.interruption_level,
            },
            "deep_link": self.deep_link,
            "notification_id": self.notification_id,
        }


@dataclass
class PushResult:
    ok: bool
    status: int = 0
    reason: str | None = None
    retryable: bool = False
    invalid_token: bool = False


class PushSender(Protocol):
    enabled: bool

    def send(self, message: PushMessage) -> PushResult: ...


class NullSender:
    """No APNs configured: notifications live in the in-app inbox only."""

    enabled = False

    def send(self, message: PushMessage) -> PushResult:  # pragma: no cover - never called while disabled
        return PushResult(ok=False, reason="push disabled")


@dataclass
class RecordingSender:
    """Test double: records messages and replies with queued results (default: success)."""

    enabled: bool = True
    sent: list[PushMessage] = field(default_factory=list)
    responses: list[PushResult] = field(default_factory=list)

    def send(self, message: PushMessage) -> PushResult:
        self.sent.append(message)
        if self.responses:
            return self.responses.pop(0)
        return PushResult(ok=True, status=200)


def collapse_id(key: str) -> str:
    """APNs allows at most 64 bytes; long dedupe keys are hashed."""
    raw = key.encode("utf-8")
    return key if len(raw) <= 64 else hashlib.sha256(raw).hexdigest()[:64]


class ApnsSender:
    enabled = True

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        if not settings.apns_configured:
            raise ValueError("APNs is not configured")
        key = settings.apns_private_key
        if not key and settings.apns_private_key_path:
            with open(settings.apns_private_key_path, encoding="utf-8") as handle:
                key = handle.read()
        self._key = (key or "").replace("\\n", "\n")
        self._key_id = settings.apns_key_id or ""
        self._team_id = settings.apns_team_id or ""
        self._topic = settings.apns_bundle_id
        self._lock = threading.Lock()
        self._token: str | None = None
        self._token_at = 0.0
        self._client = httpx.Client(http2=transport is None, transport=transport, timeout=10.0)

    def provider_token(self, force: bool = False) -> str:
        with self._lock:
            now = time.time()
            if force or self._token is None or now - self._token_at > TOKEN_TTL_SECONDS:
                self._token = jwt.encode({"iss": self._team_id, "iat": int(now)}, self._key, algorithm="ES256",
                                         headers={"kid": self._key_id})
                self._token_at = now
            return self._token

    def _post(self, message: PushMessage, token: str) -> httpx.Response:
        host = SANDBOX_HOST if message.environment == "sandbox" else PRODUCTION_HOST
        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": self._topic,
            "apns-push-type": "alert",
            "apns-priority": "5" if message.interruption_level == "passive" else "10",
            "apns-collapse-id": collapse_id(message.collapse_id),
            "apns-expiration": str(message.expires_at),
        }
        body = json.dumps(message.payload(), ensure_ascii=False).encode("utf-8")
        return self._client.post(f"{host}/3/device/{message.token}", content=body, headers=headers)

    def send(self, message: PushMessage) -> PushResult:
        try:
            response = self._post(message, self.provider_token())
            reason = _reason(response)
            if response.status_code == 403 and reason in PROVIDER_TOKEN_REASONS:
                log.warning("APNs rejected the provider token (%s); refreshing it", reason)
                response = self._post(message, self.provider_token(force=True))
                reason = _reason(response)
        except httpx.HTTPError as exc:
            log.warning("APNs request failed: %s", exc)
            return PushResult(ok=False, reason=str(exc)[:120], retryable=True)
        status = response.status_code
        if status == 200:
            return PushResult(ok=True, status=status)
        if status == 410 or reason in INVALID_TOKEN_REASONS:
            return PushResult(ok=False, status=status, reason=reason, invalid_token=True)
        if status == 429 or status >= 500:
            return PushResult(ok=False, status=status, reason=reason, retryable=True)
        if status == 403:
            log.error("APNs refused the provider token after a refresh (%s): check APNS_KEY_ID/TEAM_ID/key", reason)
        return PushResult(ok=False, status=status, reason=reason)


def _reason(response: httpx.Response) -> str | None:
    try:
        return response.json().get("reason")
    except ValueError:
        return None


def build_sender(settings: Settings) -> PushSender:
    if settings.apns_configured:
        log.info("Push: APNs (topic %s)", settings.apns_bundle_id)
        return ApnsSender(settings)
    log.info("Push: not configured (APNS_KEY_ID/APNS_TEAM_ID/APNS_PRIVATE_KEY) — in-app inbox only")
    return NullSender()
