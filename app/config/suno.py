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
    api_base_url: str = Field(default="https://api.sunoapi.org")
    browser_base_url: str = Field(default="https://studio-api-prod.suno.com")
    upload_base_url: str = Field(
        default="https://sunoapiorg.redpandaai.co",
        description="File-upload host for sunoapi.org file-upload-api endpoints.",
    )
    callback_url: str = Field(
        default="",
        description="Default callBackUrl injected into async sunoapi.org task creates. "
        "Empty is fine for the DJ poll-based flow (callbacks optional).",
    )
    generate_path: str = Field(default="")
    status_path: str = Field(default="")
    cancel_path: str = Field(default="")
    download_path: str = Field(
        default="",
        description="Optional endpoint path for audio bytes; supports {id}.",
    )
    captcha_check_path: str = Field(default="/api/c/check")
    account_path: str = Field(
        default="",
        description="Account/billing endpoint for provider_read(entity='account'). "
        "Empty disables the live balance lookup.",
    )
    auth_header: str = Field(default="Authorization")
    auth_scheme: str = Field(default="Bearer")
    clerk_url: str = Field(default="https://auth.suno.com")
    clerk_api_version: str = Field(default="2025-11-10")
    clerk_js_version: str = Field(default="5.117.0")
    payload_mode: str = Field(
        default="auto",
        description='Generation payload mode: "auto", "suno_web", "sunoapi", or "generic".',
    )
    model: str = Field(
        default="chirp-auk-turbo",
        description="Suno model key. SunoAPI uses V4/V4_5/V4_5PLUS/V4_5ALL/V5/V5_5; "
        "Suno web-session mode may use mv keys such as chirp-auk-turbo.",
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
        return self.base_url or self.api_base_url

    @property
    def effective_generate_path(self) -> str:
        if self.generate_path:
            return self.generate_path
        return "/api/generate/v2-web/" if self.use_session_auth else "/api/v1/generate"

    @property
    def effective_status_path(self) -> str:
        if self.status_path:
            return self.status_path
        if self.use_session_auth:
            return "/api/feed/v2/?ids={id}"
        return "/api/v1/generate/record-info?taskId={id}"

    @property
    def effective_cancel_path(self) -> str:
        if self.cancel_path:
            return self.cancel_path
        return "/api/generate/cancel/{id}" if self.use_session_auth else ""

    @property
    def effective_account_path(self) -> str:
        if self.account_path:
            return self.account_path
        return "/api/billing/info/" if self.use_session_auth else "/api/v1/generate/credit"

    @property
    def effective_payload_mode(self) -> str:
        if self.payload_mode != "auto":
            return self.payload_mode
        return "suno_web" if self.use_session_auth else "sunoapi"

    @property
    def enabled(self) -> bool:
        if self.use_session_auth:
            if self.cookie_header:
                return True
            if (self.client_token or self.bearer_token) and self.device_id:
                return True
            return Path(self.storage_state_path).expanduser().exists()
        return bool(self.api_key)
