from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import PLACEHOLDER_SECRETS, Settings


@pytest.mark.parametrize("secret", [*sorted(PLACEHOLDER_SECRETS), "too-short"])
def test_production_refuses_a_published_or_short_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", secret_key=secret)


def test_production_accepts_a_long_secret_and_development_allows_the_default() -> None:
    assert Settings(environment="production", secret_key="9f" * 32, openai_api_key="sk-test").environment == "production"
    assert Settings(environment="development", secret_key="dev-insecure-secret-change-me").environment == "development"


@pytest.mark.parametrize("key", [None, "", "   "])
def test_production_refuses_to_quietly_run_the_demo_provider(key: str | None) -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(environment="production", secret_key="9f" * 32, openai_api_key=key)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(environment="production", secret_key="9f" * 32, openai_api_key=key, ai_provider="openai")
    demo = Settings(environment="production", secret_key="9f" * 32, openai_api_key=key, ai_provider="mock")
    assert demo.demo_mode
    assert Settings(environment="development", openai_api_key=key).demo_mode


def test_production_verifies_purchases_against_the_bundled_apple_root() -> None:
    settings = Settings(environment="production", secret_key="9f" * 32, openai_api_key="sk-test")
    assert settings.app_store_verification_required
    assert not Settings(environment="development").app_store_verification_required
    with pytest.raises(ValidationError, match="APP_STORE_ROOT_CERTIFICATES"):
        Settings(environment="production", secret_key="9f" * 32, openai_api_key="sk-test",
                 app_store_root_certificates=["/nonexistent/root.cer"])


def test_startup_errors_never_print_the_secret_key() -> None:
    secret = "9f" * 16 + "c0ffee" * 6
    with pytest.raises(ValidationError) as error:
        Settings(environment="production", secret_key=secret, openai_api_key=None)
    assert secret[-12:] not in str(error.value)
