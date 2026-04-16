"""Lifespan-backed external dependency factories."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from app.audio.analyzers import AnalyzerRegistry
from app.clients.ym.client import YandexMusicClient
from app.core.utils.cache import TransitionCache
from app.providers.protocol import MusicProvider
from app.providers.registry import ProviderRegistry


def _get_context() -> Any:
    dependencies = import_module("app.controllers.dependencies")
    return dependencies.get_context()


def get_provider_registry() -> ProviderRegistry:
    """Get the music provider registry from lifespan context."""
    ctx = _get_context()
    registry: ProviderRegistry = ctx.lifespan_context["provider_registry"]
    return registry


def get_music_provider() -> MusicProvider:
    """Get the default music provider (convenience shortcut)."""
    return get_provider_registry().default


def get_ym_client() -> YandexMusicClient:
    """Get raw YM client from lifespan context (legacy, prefer get_music_provider)."""
    ctx = _get_context()
    client: YandexMusicClient = ctx.lifespan_context["ym_client"]
    return client


def get_analyzer_registry() -> AnalyzerRegistry:
    """Get analyzer registry from lifespan context."""
    ctx = _get_context()
    registry: AnalyzerRegistry = ctx.lifespan_context["analyzer_registry"]
    return registry


def get_transition_cache() -> TransitionCache:
    """Get in-memory transition cache from lifespan context."""
    ctx = _get_context()
    cache: TransitionCache = ctx.lifespan_context["transition_cache"]
    return cache
