"""Suno generation provider settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SunoSettings(BaseSettings):
    """Suno web-session/API credentials + endpoint shape."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_SUNO_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    auth_mode: str = Field(
        default="session",
        description='Authentication mode: "session" or "api_key".',
    )
    api_key: str = Field(default="", description="Optional bearer/API token.")
    cookie_header: str = Field(default="", description="Suno web Cookie header.")
    client_token: str = Field(default="", description="Clerk __client token.")
    device_id: str = Field(default="", description="Suno device id.")
    bearer_token: str = Field(default="", description="Optional Clerk bearer JWT.")
    base_url: str = Field(default="", description="Authorized Suno-compatible REST base URL.")
    browser_base_url: str = Field(default="https://studio-api-prod.suno.com")
    generate_path: str = Field(default="/api/generate/v2-web/")
    status_path: str = Field(default="/api/feed/v2/?ids={id}")
    cancel_path: str = Field(default="/api/generate/cancel/{id}")
    download_path: str = Field(
        default="",
        description="Optional endpoint path for audio bytes; supports {id}.",
    )
    captcha_check_path: str = Field(default="/api/c/check")
    account_path: str = Field(
        default="/api/billing/info/",
        description="Account/billing endpoint for provider_read(entity='account'). "
        "Empty disables the live balance lookup.",
    )
    auth_header: str = Field(default="Authorization")
    auth_scheme: str = Field(default="Bearer")
    clerk_url: str = Field(default="https://auth.suno.com")
    clerk_api_version: str = Field(default="2025-11-10")
    clerk_js_version: str = Field(default="5.117.0")
    payload_mode: str = Field(
        default="suno_web",
        description='Generation payload mode: "suno_web" or "generic".',
    )
    model: str = Field(
        default="chirp-auk-turbo",
        description="Suno model key (mv). chirp-auk-turbo is the default free "
        "model; set a paid key (chirp-fenix=v5.5, chirp-crow=v5) if subscribed. "
        "An unset/empty value makes Suno default to a paid model → 403 on free.",
    )
    timeout_s: float = Field(default=120.0, ge=1.0, le=600.0)
    rate_limit_delay_s: float = Field(default=0.5, ge=0.0, le=30.0)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    download_dir: str = Field(default="/tmp/dj_suno")
    storage_state_path: str = Field(default="~/.suno/storage_state.json")

    @property
    def use_session_auth(self) -> bool:
        return self.auth_mode == "session" or bool(
            self.cookie_header or self.client_token or self.device_id or self.bearer_token
        )

    @property
    def effective_base_url(self) -> str:
        if self.use_session_auth:
            return self.base_url or self.browser_base_url
        return self.base_url

    @property
    def enabled(self) -> bool:
        if self.use_session_auth:
            if self.cookie_header:
                return True
            if (self.client_token or self.bearer_token) and self.device_id:
                return True
            return Path(self.storage_state_path).expanduser().exists()
        return bool(self.api_key and self.base_url)
