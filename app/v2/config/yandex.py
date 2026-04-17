"""Yandex Music provider settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class YandexSettings(BaseSettings):
    """Yandex Music OAuth + API tuning."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_YM_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    token: str = Field(default="", description="OAuth token; if empty, provider is unavailable.")
    user_id: int = Field(default=0, ge=0)
    base_url: str = Field(default="https://api.music.yandex.net")
    rate_limit_delay_s: float = Field(default=1.5, ge=0.0, le=30.0)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    library_path: str = Field(default="", description="Local path for downloaded audio files.")
