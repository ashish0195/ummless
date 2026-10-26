"""Application settings, loaded from environment variables (and an optional `.env` file).

Every knob that product, legal or ops may want to change without a code change lives here.
List-valued settings accept either JSON (`["a","b"]`) or a comma-separated string (`a,b`).
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

StrList = Annotated[list[str], NoDecode]

# Published in this repository, so they can never sign production tokens.
PLACEHOLDER_SECRETS = {"dev-insecure-secret-change-me", "change-me-to-a-long-random-string"}


def _split_list(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            return json.loads(stripped)
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- service ---
    app_name: str = "Comlogue API"
    version: str = "1.0.0"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = "dev-insecure-secret-change-me"
    database_url: str = "sqlite:///./data/comlogue.db"
    media_dir: str = "./data/media"
    cors_origins: StrList = []

    # --- AI provider ---
    # "auto" uses OpenAI when OPENAI_API_KEY is set, otherwise the offline demo provider.
    ai_provider: Literal["auto", "openai", "mock"] = "auto"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_organization: str | None = None
    openai_project: str | None = None
    openai_timeout_seconds: float = 120.0
    openai_max_retries: int = 2
    # Models are tried in order; the first one the account can use is remembered per process.
    assessment_models: StrList = ["gpt-6.1-sol", "gpt-6-sol", "gpt-5.5"]
    assessment_reasoning_effort: str = "medium"
    conversation_models: StrList = ["gpt-6-luna", "gpt-5.4-mini", "gpt-5-mini"]
    conversation_reasoning_effort: str = "low"
    transcription_models: StrList = ["gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
    diarization_models: StrList = ["gpt-4o-transcribe-diarize"]
    tts_models: StrList = ["gpt-4o-mini-tts"]
    tts_enabled: bool = True
    # Run a diarization pass on every AI-roleplay turn to detect background voices.
    turn_background_check: bool = True

    # --- jobs ---
    jobs_inline: bool = False
    job_workers: int = 4

    # --- auth & media ---
    token_ttl_days: int = 365
    media_url_ttl_seconds: int = 6 * 3600

    # --- billing ---
    allow_dev_entitlements: bool | None = None  # None ⇒ allowed outside production
    app_store_bundle_id: str | None = "com.comlogue.app"
    app_store_product_ids: StrList = ["comlogue.pro.monthly", "comlogue.pro.yearly"]
    # TODO(launch): verify App Store JWS signatures against Apple's root certificates
    # (app-store-server-library). Until then, purchases are recorded as unverified.
    app_store_require_verification: bool = False

    # --- product limits ---
    max_upload_mb: int = 100
    max_recording_minutes: int = 60
    max_turn_seconds: int = 600
    free_spar_per_week: int = 1
    free_talks: int = 1
    rate_limit_ai_per_hour: int = 150
    rate_limit_uploads_per_hour: int = 30

    # --- pricing (a hypothesis for the pilot; shown before purchase) ---
    price_monthly_usd: float = 14.99
    price_yearly_usd: float = 95.99
    trial_days: int = 7
    monthly_product_id: str = "comlogue.pro.monthly"
    yearly_product_id: str = "comlogue.pro.yearly"

    @field_validator(
        "cors_origins",
        "assessment_models",
        "conversation_models",
        "transcription_models",
        "diarization_models",
        "tts_models",
        "app_store_product_ids",
        mode="before",
    )
    @classmethod
    def _lists(cls, value: Any) -> Any:
        return _split_list(value)

    @model_validator(mode="after")
    def _production_secret(self) -> Settings:
        # Anyone who knows the signing key can forge any user's token, so refuse to start with a weak one.
        if self.environment == "production" and (len(self.secret_key) < 32 or self.secret_key in PLACEHOLDER_SECRETS):
            raise ValueError("SECRET_KEY must be a long random string in production, e.g. `openssl rand -hex 32`.")
        return self

    @property
    def resolved_ai_provider(self) -> Literal["openai", "mock"]:
        if self.ai_provider == "auto":
            return "openai" if self.openai_api_key else "mock"
        return self.ai_provider

    @property
    def demo_mode(self) -> bool:
        return self.resolved_ai_provider == "mock"

    @property
    def dev_entitlements_allowed(self) -> bool:
        if self.allow_dev_entitlements is None:
            return self.environment != "production"
        return self.allow_dev_entitlements

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
