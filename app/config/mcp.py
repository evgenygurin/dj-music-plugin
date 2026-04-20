"""MCP server runtime settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    """MCP-specific knobs: pagination, caching, retries, timeouts, rate limits."""

    model_config = SettingsConfigDict(
        env_prefix="DJ_MCP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    debug: bool = Field(default=False, description="Surface raw exception details to clients.")
    pagination_size: int = Field(default=100, ge=10, le=1000)
    response_cache_ttl_s: int = Field(default=60, ge=0, le=3600)
    # FastMCP's built-in ``ResponseCachingMiddleware`` expects integer TTL
    # seconds (``CallToolSettings.ttl: int``). Keeping this field an int avoids
    # silent truncation from float values like 0.5 → 0 (which would disable
    # caching). Sub-second TTL is not a real use case for our tool-call cache.
    response_cache_ttl: int = Field(default=60, ge=0, le=3600)
    response_cache_max: int = Field(default=1024, ge=1, le=100_000)
    response_size_limit_bytes: int = Field(default=400_000, ge=1000)
    response_max_bytes: int = Field(default=400_000, ge=1000)
    retry_max_attempts: int = Field(default=2, ge=0, le=5)
    retry_base_delay_s: float = Field(default=0.5, ge=0.0, le=10.0)
    sampling_budget_per_session: int = Field(default=10, ge=0, le=100)
    sampling_max_per_session: int = Field(default=10, ge=0, le=100)
    progress_throttle_hz: float = Field(default=1.0, ge=0.1, le=10.0)
    tool_timeout_default_s: float = Field(default=300.0, ge=1.0, le=3600.0)
    tool_timeout_heavy_s: float = Field(default=600.0, ge=1.0, le=3600.0)
    tool_timeout_batch_s: float = Field(default=600.0, ge=1.0, le=3600.0)
    code_mode_enabled: bool = Field(default=False, description="Experimental (FastMCP 3.1+).")
    log_payloads: bool = Field(
        default=False, description="Full request/response payloads in logs."
    )
