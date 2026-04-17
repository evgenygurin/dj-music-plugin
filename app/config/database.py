"""Database connection settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection (Supabase PostgreSQL in prod, SQLite in tests)."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="Async DB connection URL. Supports postgresql+asyncpg or sqlite+aiosqlite.",
    )
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_pool_pre_ping: bool = Field(default=True)
    db_echo: bool = Field(default=False, description="Log all SQL statements.")
    db_statement_cache_size: int = Field(
        default=0,
        description="asyncpg statement cache size. 0 disables cache (pgbouncer workaround).",
    )
