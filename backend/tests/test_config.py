from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import PLACEHOLDER_SECRETS, Settings


@pytest.mark.parametrize("secret", [*sorted(PLACEHOLDER_SECRETS), "too-short"])
def test_production_refuses_a_published_or_short_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", secret_key=secret)


def test_production_accepts_a_long_secret_and_development_allows_the_default() -> None:
    assert Settings(environment="production", secret_key="9f" * 32).environment == "production"
    assert Settings(environment="development", secret_key="dev-insecure-secret-change-me").environment == "development"
