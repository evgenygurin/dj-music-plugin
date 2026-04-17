"""Composed lifespan: db | provider | audio | cache."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.server.lifespan import (
    audio_lifespan,
    build_server_lifespan,
    cache_lifespan,
    db_lifespan,
    provider_lifespan,
    session_store_lifespan,
)


@pytest.mark.asyncio
async def test_db_lifespan_yields_engine_and_factory() -> None:
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    fake_factory = MagicMock()
    with (
        patch("app.server.lifespan.build_engine", return_value=fake_engine),
        patch(
            "app.server.lifespan.build_session_factory",
            return_value=fake_factory,
        ),
    ):
        async with db_lifespan(MagicMock()) as ctx:
            assert ctx["db_engine"] is fake_engine
            assert ctx["db_session_factory"] is fake_factory


@pytest.mark.asyncio
async def test_provider_lifespan_registers_yandex() -> None:
    fake_adapter = MagicMock()
    fake_adapter.name = "yandex"
    fake_adapter.close = AsyncMock()
    with patch(
        "app.server.lifespan.build_yandex_adapter",
        return_value=fake_adapter,
    ):
        async with provider_lifespan(MagicMock()) as ctx:
            registry = ctx["provider_registry"]
            assert registry.default() is fake_adapter
        fake_adapter.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_audio_lifespan_yields_registry_and_pipeline() -> None:
    async with audio_lifespan(MagicMock()) as ctx:
        assert "analyzer_registry" in ctx
        assert "audio_pipeline" in ctx


@pytest.mark.asyncio
async def test_cache_lifespan_yields_transition_cache() -> None:
    async with cache_lifespan(MagicMock()) as ctx:
        assert "transition_cache" in ctx


@pytest.mark.asyncio
async def test_session_store_lifespan_yields_store() -> None:
    async with session_store_lifespan(MagicMock()) as ctx:
        assert "session_store" in ctx


@pytest.mark.asyncio
async def test_build_server_lifespan_merges_all_keys() -> None:
    lifespan = build_server_lifespan()
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    fake_adapter = MagicMock()
    fake_adapter.name = "yandex"
    fake_adapter.close = AsyncMock()
    with (
        patch("app.server.lifespan.build_engine", return_value=fake_engine),
        patch("app.server.lifespan.build_session_factory"),
        patch("app.server.lifespan.build_yandex_adapter", return_value=fake_adapter),
    ):
        async with lifespan(MagicMock()) as ctx:
            for key in (
                "db_engine",
                "db_session_factory",
                "provider_registry",
                "analyzer_registry",
                "audio_pipeline",
                "transition_cache",
                "session_store",
            ):
                assert key in ctx, f"lifespan missing key: {key}"
