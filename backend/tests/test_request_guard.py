"""Uploads are refused before their body is read: no token, too large, or a chunked body that keeps going."""

from __future__ import annotations

import json

import anyio
import pytest

from tests.helpers import signup

MB = 1024 * 1024
MULTIPART = "multipart/form-data; boundary=comlogue"


@pytest.fixture
def small_uploads(settings):
    settings.max_upload_mb = 1  # the multipart cap is this plus 1 MB of form overhead
    return settings


class Body:
    """A chunked request body that records how much of it the server pulled."""

    def __init__(self, total: int, chunk: int = 256 * 1024):
        self.total, self.chunk, self.sent = total, chunk, 0

    def __iter__(self):
        while self.sent < self.total:
            self.sent += self.chunk
            yield b"\0" * self.chunk


def test_upload_without_a_token_is_refused_before_the_body_is_read(small_uploads, client) -> None:
    body = Body(50 * MB)
    for headers in ({}, {"Authorization": "Bearer not-a-real-token"}):
        response = client.post("/v1/recordings", content=body, headers={"Content-Type": MULTIPART, **headers})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
    assert body.sent == 0


def test_upload_with_a_large_content_length_is_refused_up_front(small_uploads, client) -> None:
    headers = {**signup(client), "Content-Type": MULTIPART, "Content-Length": str(3 * MB)}
    response = client.post("/v1/recordings", content=b"\0" * (3 * MB), headers=headers)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def _post_chunked(app, headers: dict[str, str], *, total: int, chunk: int = 256 * 1024) -> tuple[int, dict, int]:
    """POST a chunked body straight over ASGI; returns (status, body, bytes the app pulled)."""
    pulled = 0
    messages: list[dict] = []

    async def receive() -> dict:
        nonlocal pulled
        if pulled >= total:
            return {"type": "http.disconnect"}
        part = (b'--comlogue\r\nContent-Disposition: form-data; name="audio"; filename="a.m4a"\r\n'
                b"Content-Type: audio/mp4\r\n\r\n") if pulled == 0 else b""
        pulled += chunk
        return {"type": "http.request", "body": part + b"\0" * chunk, "more_body": pulled < total}

    async def send(message: dict) -> None:
        messages.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": "/v1/recordings", "raw_path": b"/v1/recordings", "query_string": b"", "root_path": "",
             "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
             "client": ("127.0.0.1", 1), "server": ("testserver", 80)}
    anyio.run(app, scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(body), pulled


def test_chunked_upload_is_cut_off_at_the_cap(small_uploads, client) -> None:
    status, body, pulled = _post_chunked(client.app, {**signup(client), "Content-Type": MULTIPART}, total=20 * MB)
    assert status == 413 and body["error"]["code"] == "file_too_large"
    assert pulled <= 2 * MB + 256 * 1024


def test_json_bodies_are_capped(client) -> None:
    response = client.post("/v1/auth/device", content=b"{" + b" " * (2 * MB) + b"}",
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
