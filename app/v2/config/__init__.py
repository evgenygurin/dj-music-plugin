"""Settings facade — aggregates per-domain Settings classes.

Usage:
    from app.v2.config import get_settings

    settings = get_settings()
    print(settings.transition.weight_bpm)

All per-domain classes read from environment independently (each has its own
``env_prefix``). Facade is cached via ``lru_cache`` — call
``reset_settings_cache()`` in tests if env changes between calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.v2.config.audio import AudioSettings
from app.v2.config.database import DatabaseSettings
from app.v2.config.delivery import DeliverySettings
from app.v2.config.discovery import DiscoverySettings
from app.v2.config.mcp import MCPSettings
from app.v2.config.optimization import OptimizationSettings
from app.v2.config.transition import TransitionSettings
from app.v2.config.yandex import YandexSettings

__all__ = [
    "AudioSettings",
    "DatabaseSettings",
    "DeliverySettings",
    "DiscoverySettings",
    "MCPSettings",
    "OptimizationSettings",
    "Settings",
    "TransitionSettings",
    "YandexSettings",
    "get_settings",
    "reset_settings_cache",
]


@dataclass(frozen=True, slots=True)
class Settings:
    """Aggregate of per-domain Settings. Construct with ``get_settings()``."""

    database: DatabaseSettings
    yandex: YandexSettings
    audio: AudioSettings
    transition: TransitionSettings
    optimization: OptimizationSettings
    discovery: DiscoverySettings
    delivery: DeliverySettings
    mcp: MCPSettings

    def __init__(self) -> None:
        object.__setattr__(self, "database", DatabaseSettings())
        object.__setattr__(self, "yandex", YandexSettings())
        object.__setattr__(self, "audio", AudioSettings())
        object.__setattr__(self, "transition", TransitionSettings())
        object.__setattr__(self, "optimization", OptimizationSettings())
        object.__setattr__(self, "discovery", DiscoverySettings())
        object.__setattr__(self, "delivery", DeliverySettings())
        object.__setattr__(self, "mcp", MCPSettings())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached process-wide Settings instance."""
    return Settings()


def reset_settings_cache() -> None:
    """Clear the cached Settings. Use in tests after env mutation."""
    get_settings.cache_clear()
