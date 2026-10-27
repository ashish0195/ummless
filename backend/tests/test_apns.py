"""APNs sender against a fake HTTP transport: headers, payload, provider-token caching and error handling.

The signing key is generated per test run; nothing real is used or stored.
"""

from __future__ import annotations

import json

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app import push
from app.config import Settings
from app.push import ApnsSender, NullSender, PushMessage, build_sender, collapse_id


@pytest.fixture(scope="module")
def keys() -> tuple[str, ec.EllipticCurvePublicKey]:
    private = ec.generate_private_key(ec.SECP256R1())
    pem = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    return pem, private.public_key()


def _settings(pem: str, **overrides) -> Settings:
    return Settings(environment="test", apns_key_id="KEY1234567", apns_team_id="TEAM123456", apns_private_key=pem,
                    **overrides)


def _message(**overrides) -> PushMessage:
    fields = {"token": "ab" * 32, "environment": "production", "title": "Your 1-minute practice is ready",
              "body": "Today: Explain your job to a 10-year-old.", "badge": 2, "thread_id": "nudge",
              "collapse_id": "nudge:2026-11-01:1", "interruption_level": "active", "deep_link": "comlogue://daily",
              "notification_id": "ntf_1", "expires_at": 1_800_000_000}
    fields.update(overrides)
    return PushMessage(**fields)


class FakeAPNs:
    def __init__(self, replies: list[tuple[int, dict | None]] | None = None):
        self.requests: list[httpx.Request] = []
        self.replies = list(replies or [])

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.replies.pop(0) if self.replies else (200, None)
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)


def test_build_sender_needs_all_apns_settings(keys):
    pem, _ = keys
    assert isinstance(build_sender(Settings(environment="test")), NullSender)
    assert isinstance(build_sender(Settings(environment="test", apns_key_id="K", apns_team_id="T")), NullSender)
    assert _settings(pem).apns_configured
    with pytest.raises(ValueError):
        ApnsSender(Settings(environment="test"))


def test_request_headers_payload_and_signed_provider_token(keys):
    pem, public = keys
    fake = FakeAPNs()
    sender = ApnsSender(_settings(pem), transport=httpx.MockTransport(fake))
    result = sender.send(_message())
    assert result.ok and result.status == 200
    request = fake.requests[0]
    assert str(request.url) == f"https://api.push.apple.com/3/device/{'ab' * 32}"
    headers = request.headers
    assert headers["apns-topic"] == "com.comlogue.app" and headers["apns-push-type"] == "alert"
    assert headers["apns-priority"] == "10" and headers["apns-collapse-id"] == "nudge:2026-11-01:1"
    assert headers["apns-expiration"] == "1800000000"
    scheme, token = headers["authorization"].split(" ")
    assert scheme == "bearer"
    assert jwt.get_unverified_header(token) == {"alg": "ES256", "kid": "KEY1234567", "typ": "JWT"}
    claims = jwt.decode(token, public, algorithms=["ES256"])
    assert claims["iss"] == "TEAM123456" and isinstance(claims["iat"], int)
    assert json.loads(request.content) == {
        "aps": {"alert": {"title": "Your 1-minute practice is ready", "body": "Today: Explain your job to a 10-year-old."},
                "sound": "default", "badge": 2, "thread-id": "nudge", "interruption-level": "active"},
        "deep_link": "comlogue://daily", "notification_id": "ntf_1",
    }


def test_sandbox_host_passive_priority_and_long_collapse_ids(keys):
    pem, _ = keys
    fake = FakeAPNs()
    sender = ApnsSender(_settings(pem, apns_bundle_id="com.example.test"), transport=httpx.MockTransport(fake))
    long_key = "recording:rec_0123456789abcdef:complete:2026-11-04T12:00:00Z:extra-long-suffix"
    sender.send(_message(environment="sandbox", interruption_level="passive", collapse_id=long_key))
    request = fake.requests[0]
    assert request.url.host == "api.sandbox.push.apple.com"
    assert request.headers["apns-priority"] == "5" and request.headers["apns-topic"] == "com.example.test"
    assert request.headers["apns-collapse-id"] == collapse_id(long_key)
    assert len(request.headers["apns-collapse-id"].encode()) <= 64 and collapse_id("short") == "short"


def test_provider_token_is_cached_and_refreshed_after_40_minutes(keys, monkeypatch):
    pem, _ = keys
    clock = {"now": 1_800_000_000.0}
    monkeypatch.setattr(push.time, "time", lambda: clock["now"])
    fake = FakeAPNs()
    sender = ApnsSender(_settings(pem), transport=httpx.MockTransport(fake))
    sender.send(_message())
    clock["now"] += 39 * 60
    sender.send(_message())
    clock["now"] += 2 * 60
    sender.send(_message())
    tokens = [r.headers["authorization"] for r in fake.requests]
    assert tokens[0] == tokens[1] != tokens[2]


def test_expired_provider_token_is_refreshed_once_and_retried(keys, monkeypatch):
    pem, _ = keys
    clock = {"now": 1_800_000_000.0}
    monkeypatch.setattr(push.time, "time", lambda: clock["now"])
    fake = FakeAPNs([(403, {"reason": "ExpiredProviderToken"}), (200, None)])
    sender = ApnsSender(_settings(pem), transport=httpx.MockTransport(fake))
    sender.provider_token()
    clock["now"] += 5  # a fresh token has a new iat
    assert sender.send(_message()).ok
    assert len(fake.requests) == 2
    assert fake.requests[0].headers["authorization"] != fake.requests[1].headers["authorization"]


@pytest.mark.parametrize(("status", "reason", "invalid", "retryable"), [
    (410, "Unregistered", True, False),
    (400, "BadDeviceToken", True, False),
    (400, "DeviceTokenNotForTopic", True, False),
    (429, "TooManyRequests", False, True),
    (500, "InternalServerError", False, True),
    (503, "ServiceUnavailable", False, True),
    (400, "PayloadTooLarge", False, False),
    (403, "InvalidProviderToken", False, False),  # still refused after a refresh: a configuration problem
])
def test_error_responses(keys, status, reason, invalid, retryable):
    pem, _ = keys
    fake = FakeAPNs([(status, {"reason": reason})] * 2)
    result = ApnsSender(_settings(pem), transport=httpx.MockTransport(fake)).send(_message())
    assert not result.ok and result.status == status and result.reason == reason
    assert result.invalid_token is invalid and result.retryable is retryable


def test_network_errors_are_retryable(keys):
    pem, _ = keys

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = ApnsSender(_settings(pem), transport=httpx.MockTransport(broken)).send(_message())
    assert not result.ok and result.retryable and not result.invalid_token


def test_key_can_be_read_from_a_file(keys, tmp_path):
    pem, public = keys
    path = tmp_path / "AuthKey.p8"
    path.write_text(pem)
    fake = FakeAPNs()
    sender = ApnsSender(Settings(environment="test", apns_key_id="K", apns_team_id="T", apns_private_key_path=str(path)),
                        transport=httpx.MockTransport(fake))
    assert sender.send(_message()).ok
    token = fake.requests[0].headers["authorization"].split(" ")[1]
    assert jwt.decode(token, public, algorithms=["ES256"])["iss"] == "T"
