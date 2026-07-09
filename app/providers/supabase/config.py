from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SupabaseStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SUPABASE_")

    url: str = ""
    service_key: str = ""
