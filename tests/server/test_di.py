"""Depends() factories read from ctx.fastmcp_context.state."""

from __future__ import annotations

from types import SimpleNamespace
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


def _ctx_with_state(state: dict) -> object:
    fastmcp_ctx = SimpleNamespace(state=state)
    return SimpleNamespace(fastmcp_context=fastmcp_ctx)


def test_get_uow_returns_state_slot() -> None:
    uow = MagicMock(spec=UnitOfWork)
    ctx = _ctx_with_state({"uow": uow})
    assert get_uow(ctx) is uow


def test_get_uow_raises_when_missing() -> None:
    ctx = _ctx_with_state({})
    with pytest.raises(RuntimeError, match="UnitOfWork not initialized"):
        get_uow(ctx)


def test_get_provider_registry_returns_state_slot() -> None:
    reg = MagicMock(spec=ProviderRegistry)
    ctx = _ctx_with_state({"provider_registry": reg})
    assert get_provider_registry(ctx) is reg


def test_get_provider_registry_raises_when_missing() -> None:
    ctx = _ctx_with_state({})
    with pytest.raises(RuntimeError, match="ProviderRegistry not initialized"):
        get_provider_registry(ctx)


def test_get_analyzer_registry_returns_state_slot() -> None:
    reg = object()
    ctx = _ctx_with_state({"analyzer_registry": reg})
    assert get_analyzer_registry(ctx) is reg


def test_get_audio_pipeline_returns_state_slot() -> None:
    pipeline = object()
    ctx = _ctx_with_state({"audio_pipeline": pipeline})
    assert get_audio_pipeline(ctx) is pipeline


def test_get_session_store_returns_state_slot() -> None:
    store = object()
    ctx = _ctx_with_state({"session_store": store})
    assert get_session_store(ctx) is store
