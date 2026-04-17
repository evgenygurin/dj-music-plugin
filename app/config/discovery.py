"""Discovery / expansion settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscoverySettings(BaseSettings):
    """Similar-track discovery + playlist expansion."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_DISCOVERY_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    similar_default_limit: int = Field(default=20, ge=1, le=200)
    expand_default_target: int = Field(default=500, ge=10, le=20_000)
    expand_max_bfs_depth: int = Field(default=5, ge=1, le=20)
    default_min_duration_ms: int = Field(default=120_000, ge=0)
    default_max_duration_ms: int = Field(default=900_000, ge=0)
    feedback_boost_factor: float = Field(default=1.5, ge=0.0, le=10.0)
    feedback_penalty_factor: float = Field(default=0.1, ge=0.0, le=1.0)
    prefetch_top_n: int = Field(default=3, ge=0, le=20)
    prefetch_max_l3: int = Field(default=2, ge=0, le=20)
