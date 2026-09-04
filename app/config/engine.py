"""Universal engine rollout settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.engine.mode import EngineMode, EngineSelection


class EngineSettings(BaseSettings):
    """Feature flags controlling universal engine and renderer rollout."""

    model_config = SettingsConfigDict(env_prefix="DJ_", extra="ignore")

    engine: EngineMode = EngineMode.LEGACY
    renderer: str = "legacy"

    def selection(self) -> EngineSelection:
        """Return the validated rollout selection consumed by application code."""
        return EngineSelection.from_values(self.engine.value, self.renderer)
