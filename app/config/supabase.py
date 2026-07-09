"""Supabase Storage settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseSettings(BaseSettings):
    """Supabase project connection (storage bucket access)."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_service_key: str = Field(default="", description="Supabase service_role key for storage writes")
