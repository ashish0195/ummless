from __future__ import annotations

import os
import re
from typing import Any

import pytest

os.environ.setdefault("ENVIRONMENT", "test")

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

FORBIDDEN_KEYS = {"overall_score", "overall", "total_score", "score"}
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
LOOKS_LIKE_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def assert_contract(value: Any, path: str = "$") -> None:
    """Contract rules that hold for EVERY response: no overall score, timestamps without fractions."""
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in FORBIDDEN_KEYS, f"forbidden key {key!r} at {path}"
            assert_contract(item, f"{path}.{key}")
        if value.get("status") in ("not_enough_evidence", "not_assessed") and "level" in value:
            assert value["level"] is None, f"missing evidence must not carry a level at {path}"
            assert value.get("confidence") is None, f"missing evidence must not carry confidence at {path}"
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_contract(item, f"{path}[{index}]")
    elif isinstance(value, str) and LOOKS_LIKE_TIMESTAMP.match(value):
        assert TIMESTAMP_RE.match(value), f"bad timestamp {value!r} at {path}"


class ContractClient(TestClient):
    def request(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        response = super().request(*args, **kwargs)
        if response.headers.get("content-type", "").startswith("application/json") and response.content:
            assert_contract(response.json())
        return response


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite:///{tmp_path}/test.db",
        media_dir=str(tmp_path / "media"),
        jobs_inline=True,
        ai_provider="mock",
        openai_api_key=None,
        secret_key="test-secret",
        allow_dev_entitlements=True,
        rate_limit_ai_per_hour=10_000,
        rate_limit_uploads_per_hour=10_000,
    )


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings)
    with ContractClient(app) as test_client:
        yield test_client


@pytest.fixture
def audio_dir(tmp_path):
    path = tmp_path / "audio"
    path.mkdir()
    return path
