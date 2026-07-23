from __future__ import annotations

from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    return f"sqlite:///{(BACKEND_ROOT / 'state' / 'atlas.db').as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_prefix="ATLAS_",
        extra="ignore",
    )

    app_name: str = "London Flat Atlas API"
    app_env: Literal["development", "test", "production"] = "development"
    app_base_url: str = "http://127.0.0.1:4173"
    api_prefix: str = "/api"
    data_dir: Path = BACKEND_ROOT / "data"
    database_url: str = _default_database_url()
    allow_dev_entitlements: bool = False
    cors_origins: list[str] = ["http://127.0.0.1:4173"]

    pro_access_code: SecretStr | None = None
    pro_access_signing_secret: SecretStr | None = None
    pro_access_expires_at: datetime | None = None
    pro_access_rate_limit_requests: int = 5
    pro_access_rate_limit_window_seconds: int = 300

    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None

    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_monthly_price_id: str | None = None
    stripe_yearly_price_id: str | None = None

    data_rate_limit_requests: int = 180
    data_rate_limit_window_seconds: int = 60

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.app_env == "production" and self.allow_dev_entitlements:
            raise ValueError("Development entitlements must be disabled in production")
        oidc_values = (self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)
        if any(oidc_values) and not all(oidc_values):
            raise ValueError("OIDC issuer, audience, and JWKS URL must be configured together")
        stripe_values = (
            self.stripe_secret_key,
            self.stripe_webhook_secret,
            self.stripe_monthly_price_id,
            self.stripe_yearly_price_id,
        )
        if any(stripe_values) and not all(stripe_values):
            raise ValueError("All Stripe settings must be configured together")
        access_code_values = (
            self.pro_access_code,
            self.pro_access_signing_secret,
            self.pro_access_expires_at,
        )
        if any(access_code_values) and not all(access_code_values):
            raise ValueError("Pro access code, signing secret, and expiry must be configured together")
        if (
            self.pro_access_signing_secret is not None
            and len(self.pro_access_signing_secret.get_secret_value()) < 32
        ):
            raise ValueError("Pro access signing secret must be at least 32 characters")
        if (
            self.data_rate_limit_requests < 1
            or self.data_rate_limit_window_seconds < 1
            or self.pro_access_rate_limit_requests < 1
            or self.pro_access_rate_limit_window_seconds < 1
        ):
            raise ValueError("Rate-limit values must be positive")
        if self.pro_access_expires_at is not None:
            if self.pro_access_expires_at.tzinfo is None:
                raise ValueError("Pro access expiry must include a timezone")
        return self

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url)

    @property
    def billing_enabled(self) -> bool:
        return bool(
            self.stripe_secret_key
            and self.stripe_webhook_secret
            and self.stripe_monthly_price_id
            and self.stripe_yearly_price_id
        )

    @property
    def pro_access_enabled(self) -> bool:
        return bool(
            self.pro_access_code
            and self.pro_access_signing_secret
            and self.pro_access_expires_at
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
