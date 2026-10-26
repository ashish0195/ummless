"""Bearer tokens and signed media URLs (HMAC-SHA256, no external dependencies)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(secret: str, message: str) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest())


@dataclass(frozen=True)
class TokenClaims:
    user_id: str
    issued_at: int
    expires_at: int


def issue_token(secret: str, user_id: str, ttl_days: int) -> str:
    now = int(time.time())
    payload = _b64(json.dumps({"uid": user_id, "iat": now, "exp": now + ttl_days * 86400}).encode())
    return f"{payload}.{_sign(secret, payload)}"


def verify_token(secret: str, token: str) -> TokenClaims | None:
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        return None
    try:
        data = json.loads(_unb64(payload))
        claims = TokenClaims(user_id=str(data["uid"]), issued_at=int(data["iat"]), expires_at=int(data["exp"]))
    except (ValueError, KeyError, TypeError):
        return None
    if claims.expires_at < int(time.time()):
        return None
    return claims


def sign_media(secret: str, media_id: str, ttl_seconds: int) -> tuple[int, str]:
    expires = int(time.time()) + ttl_seconds
    return expires, _sign(secret, f"media:{media_id}:{expires}")[:32]


def verify_media_signature(secret: str, media_id: str, expires: int, signature: str) -> bool:
    if expires < int(time.time()):
        return False
    expected = _sign(secret, f"media:{media_id}:{expires}")[:32]
    return hmac.compare_digest(expected, signature)
