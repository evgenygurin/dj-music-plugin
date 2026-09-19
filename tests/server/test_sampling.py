"""Tests for the OmniRoute sampling fallback."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.server.sampling import build_sampling_handler


def test_returns_none_when_api_key_missing(monkeypatch) -> None:
    monkeypatch.delenv("OMNIROUTE_API_KEY", raising=False)
    assert build_sampling_handler() is None


def test_returns_callable_when_api_key_set(monkeypatch) -> None:
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-test")
    handler = build_sampling_handler()
    assert handler is not None
    assert callable(handler)


@pytest.mark.asyncio
async def test_handler_delegates_to_omniroute(monkeypatch) -> None:
    monkeypatch.setenv("OMNIROUTE_API_KEY", "sk-test")

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {
        "choices": [{"message": {"content": "result"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=fake_response)

    with patch("app.server.sampling.httpx.AsyncClient", return_value=fake_client):
        handler = build_sampling_handler()
        assert handler is not None

        state: dict = {}
        ctx = SimpleNamespace(fastmcp_context=SimpleNamespace(state=state))
        out = await handler(
            messages=[SimpleNamespace(content=SimpleNamespace(text="hello"))],
            params=SimpleNamespace(system_prompt="sys", max_tokens=100, temperature=0.2),
            context=ctx,
        )

        assert out == "result"
        assert state["cost"]["llm_tokens"] == 15
        assert state["cost"]["provider_calls"] == 1
        fake_client.post.assert_awaited_once()
        request = fake_client.post.await_args
        assert request.args[0] == "/chat/completions"
        assert request.kwargs["json"]["model"] == "dj-free-fast"
