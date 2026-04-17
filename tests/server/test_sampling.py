"""Tests for Anthropic sampling fallback (Task 22)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.server.sampling import build_sampling_handler


def test_returns_none_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("DJ_ANTHROPIC_API_KEY", raising=False)
    assert build_sampling_handler() is None


def test_returns_callable_when_api_key_set(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ANTHROPIC_API_KEY", "sk-test")
    with patch("app.server.sampling.AsyncAnthropic", return_value=MagicMock()):
        handler = build_sampling_handler()
        assert handler is not None
        assert callable(handler)


def test_returns_none_when_sdk_missing(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ANTHROPIC_API_KEY", "sk-test")
    with patch("app.server.sampling.AsyncAnthropic", None):
        assert build_sampling_handler() is None


@pytest.mark.asyncio
async def test_handler_delegates_to_anthropic(monkeypatch) -> None:
    monkeypatch.setenv("DJ_ANTHROPIC_API_KEY", "sk-test")

    fake_client = MagicMock()
    fake_message = MagicMock()
    fake_message.content = [SimpleNamespace(text="result")]
    fake_message.usage = SimpleNamespace(input_tokens=10, output_tokens=5)
    fake_client.messages.create = AsyncMock(return_value=fake_message)

    with patch("app.server.sampling.AsyncAnthropic", return_value=fake_client):
        handler = build_sampling_handler()
        assert handler is not None

        state: dict = {}
        ctx = SimpleNamespace(fastmcp_context=SimpleNamespace(state=state))
        out = await handler(
            messages=[SimpleNamespace(content=SimpleNamespace(text="hello"))],
            params=SimpleNamespace(system_prompt="sys", max_tokens=100, temperature=0.2),
            context=ctx,
        )
        assert "result" in str(out)
        assert state["cost"]["llm_tokens"] == 15
        fake_client.messages.create.assert_awaited_once()
