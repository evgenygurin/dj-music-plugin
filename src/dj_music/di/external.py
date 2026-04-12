"""Lifespan-backed external dependency factories."""

from __future__ import annotations

from importlib import import_module

from dj_music.audio.analyzers import AnalyzerRegistry
from dj_music.core.utils.cache import TransitionCache
from dj_music.ym.client import YandexMusicClient


def _get_context():  # type: ignore[no-untyped-def]
    dependencies = import_module("dj_music.di")
    return dependencies.get_context()


def get_ym_client() -> YandexMusicClient:
    """Get YM client from lifespan context."""
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
