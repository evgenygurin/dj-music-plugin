"""DI accessors read from the right slot on ctx.fastmcp_context."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.server.di import (
    get_analyzer_registry,
    get_audio_pipeline,
    get_provider_registry,
    get_session_store,
    get_uow,
)

from .conftest import make_di_ctx


@pytest.mark.asyncio
async def test_get_uow_returns_state_slot() -> None:
    uow = MagicMock(spec=UnitOfWork)
    ctx = make_di_ctx(state={"uow": uow})
    assert await get_uow(ctx) is uow


@pytest.mark.asyncio
async def test_get_uow_raises_when_missing() -> None:
    ctx = make_di_ctx(state={})
    with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
        await get_uow(ctx)


@pytest.mark.asyncio
async def test_get_provider_registry_returns_lifespan_slot() -> None:
    reg = MagicMock(spec=ProviderRegistry)
    ctx = make_di_ctx(lifespan={"provider_registry": reg})
    assert await get_provider_registry(ctx) is reg


@pytest.mark.asyncio
async def test_get_provider_registry_raises_when_missing() -> None:
    ctx = make_di_ctx(lifespan={})
    with pytest.raises(RuntimeError, match="ProviderRegistry not initialized"):
        await get_provider_registry(ctx)


@pytest.mark.asyncio
async def test_get_analyzer_registry_returns_lifespan_slot() -> None:
    reg = object()
    ctx = make_di_ctx(lifespan={"analyzer_registry": reg})
    assert await get_analyzer_registry(ctx) is reg


@pytest.mark.asyncio
async def test_get_audio_pipeline_returns_lifespan_slot() -> None:
    pipeline = object()
    ctx = make_di_ctx(lifespan={"audio_pipeline": pipeline})
    assert await get_audio_pipeline(ctx) is pipeline


@pytest.mark.asyncio
async def test_get_session_store_returns_lifespan_slot() -> None:
    store = object()
    ctx = make_di_ctx(lifespan={"session_store": store})
    assert await get_session_store(ctx) is store
