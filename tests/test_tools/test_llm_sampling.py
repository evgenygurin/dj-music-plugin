"""Unit tests for MCP sampling helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.controllers.tools._shared.llm_sampling import (
    format_sampling_failure_message,
    format_sampling_unavailable_note,
    resolve_sampling_params,
    sample_structured,
)
from app.core.constants import MCP_SAMPLING_API_KEY_ENV_NAME


def test_resolve_sampling_params_uses_settings_when_none() -> None:
    mt, tp = resolve_sampling_params()
    assert mt >= 1
    assert 0.0 <= tp <= 2.0


def test_resolve_sampling_params_respects_overrides() -> None:
    mt, tp = resolve_sampling_params(max_tokens=123, temperature=0.1)
    assert mt == 123
    assert tp == 0.1


def test_settings_sampling_narrative_max_tokens_ge_default_queries() -> None:
    """Narrative arc uses a higher cap than default ``sampling_max_tokens``."""
    from app.config import settings

    assert settings.sampling_narrative_max_tokens >= settings.sampling_max_tokens


def test_format_sampling_failure_message_names_env() -> None:
    text = format_sampling_failure_message(ValueError("boom"))
    assert MCP_SAMPLING_API_KEY_ENV_NAME in text
    assert "boom" in text
    assert "client" in text.lower()


def test_format_sampling_unavailable_note_includes_message() -> None:
    note = format_sampling_unavailable_note(
        ValueError("Client does not support sampling with tools.")
    )
    assert "ValueError" in note
    assert "sampling" in note and "tools" in note


def test_format_sampling_unavailable_note_truncates() -> None:
    long_msg = "x" * 500
    note = format_sampling_unavailable_note(ValueError(long_msg), max_len=80)
    assert len(note) == 80
    assert note.endswith("...")


@pytest.mark.asyncio
async def test_sample_structured_forwards_defaults() -> None:
    """Delegates to ctx.sample with max_tokens, temperature, model_preferences."""
    from pydantic import BaseModel

    from app.config import settings

    class _M(BaseModel):
        x: int

    ctx = MagicMock()
    ctx.sample = AsyncMock()

    await sample_structured(ctx, "hi", result_type=_M)

    ctx.sample.assert_awaited_once()
    call_kw = ctx.sample.await_args.kwargs
    assert "max_tokens" in call_kw
    assert "temperature" in call_kw
    assert call_kw["result_type"] is _M
    assert call_kw.get("model_preferences") == settings.sampling_model
