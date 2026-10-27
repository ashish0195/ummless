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
    # hide_input_in_errors: a startup error would otherwise print the settings it was given, SECRET_KEY included.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore",
                                      hide_input_in_errors=True)

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
    # "auto" uses OpenAI when OPENAI_API_KEY is set, otherwise the offline demo provider. Production refuses to
    # start without a key unless AI_PROVIDER=mock asks for a (clearly labelled) demo on purpose.
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
    # Purchases count only if their JWS chains to Apple's root. None ⇒ required in production only, so Xcode's
    # local StoreKit testing (signed by a local certificate) still works in development.
    app_store_require_verification: bool | None = None
    # Trusted roots (DER or PEM paths). Empty ⇒ the certificates bundled in app/certs/ (Apple Root CA - G3).
    app_store_root_certificates: StrList = []

    # --- product limits ---
    max_upload_mb: int = 100
    max_recording_minutes: int = 60
    max_turn_seconds: int = 600
    free_spar_per_week: int = 1
    free_talks: int = 1
    rate_limit_ai_per_hour: int = 150
    rate_limit_uploads_per_hour: int = 30

    # --- pricing (a hypothesis for the pilot; shown before purchase; the App Store's localized price wins) ---
    price_monthly_usd: float = 14.99
    price_yearly_usd: float = 95.99
    price_monthly_inr: float = 399
    price_yearly_inr: float = 2499
    trial_days: int = 7
    monthly_product_id: str = "comlogue.pro.monthly"
    yearly_product_id: str = "comlogue.pro.yearly"

    # --- support & grievance contacts (India's DPDP Act expects a published grievance contact) ---
    support_email: str = "support@comlogue.app"
    grievance_email: str = "grievance@comlogue.app"
    grievance_officer: str | None = None

    # --- notifications ---
    # The scheduler produces event-prep, check-in, nudge and weekly-reveal notifications and delivers pushes.
    # None ⇒ on everywhere except tests. Dedupe keys make ticks safe to run on several instances.
    notifications_scheduler_enabled: bool | None = None
    notifications_tick_seconds: int = 300
    # Apple Push Notification service (token auth). Without a key, notifications go to the in-app inbox only.
    apns_key_id: str | None = None
    apns_team_id: str | None = None
    apns_private_key: str | None = None  # contents of the .p8 file (PEM)
    apns_private_key_path: str | None = None  # or a path to it
    apns_bundle_id: str = "com.comlogue.app"

    @field_validator(
        "cors_origins",
        "assessment_models",
        "conversation_models",
        "transcription_models",
        "diarization_models",
        "tts_models",
        "app_store_product_ids",
        "app_store_root_certificates",
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

    @model_validator(mode="after")
    def _production_ai(self) -> Settings:
        # Without a key, "auto" would quietly serve simulated feedback to real users.
        if self.environment == "production" and self.ai_provider != "mock" and not (self.openai_api_key or "").strip():
            raise ValueError("OPENAI_API_KEY is required in production. To run a labelled demo on purpose, set "
                             "AI_PROVIDER=mock.")
        return self

    @model_validator(mode="after")
    def _production_billing(self) -> Settings:
        # Refuse to start rather than reject every purchase later.
        if self.environment == "production" and self.app_store_verification_required:
            from .services.app_store import load_root_certificates

            try:
                roots = load_root_certificates(self.app_store_root_certificates)
            except (OSError, ValueError) as exc:
                raise ValueError(f"APP_STORE_ROOT_CERTIFICATES couldn't be loaded: {exc}") from exc
            if not roots:
                raise ValueError("No App Store root certificate found (expected app/certs/AppleRootCA-G3.cer).")
        return self

    @property
    def resolved_ai_provider(self) -> Literal["openai", "mock"]:
        if self.ai_provider == "auto":
            return "openai" if (self.openai_api_key or "").strip() else "mock"
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
    def app_store_verification_required(self) -> bool:
        if self.app_store_require_verification is None:
            return self.environment == "production"
        return self.app_store_require_verification

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def scheduler_enabled(self) -> bool:
        if self.notifications_scheduler_enabled is None:
            return self.environment != "test"
        return self.notifications_scheduler_enabled

    @property
    def apns_configured(self) -> bool:
        return bool(self.apns_key_id and self.apns_team_id and (self.apns_private_key or self.apns_private_key_path))


@lru_cache
def get_settings() -> Settings:
    return Settings()
