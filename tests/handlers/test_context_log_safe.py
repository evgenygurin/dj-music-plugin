"""Regression for ``app.handlers._context_log.safe_info``.

Background: ``ctx.info(msg)`` from ``FastMCP.server.Context`` requires
an active MCP session — internally calls
``ctx.session.send_log_message(...)``. The five entity-create / update
handlers (``track_import``, ``track_features_{analyze,reanalyze}``,
``audio_file_download``, ``set_version_build``) emit a single progress
log via ``await ctx.info(...)`` near the end of the happy path.

When the same handler runs through the REST proxy (no MCP session),
the call raised ``RuntimeError("session is not available because the
MCP session has not been established yet")`` — **after** the DB writes
had landed. The caller saw a "failed" tool call even though the work
completed (and even though re-trying would have made it worse).
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.handlers._context_log import safe_error, safe_info, safe_warning


@pytest.mark.asyncio
async def test_safe_info_delegates_when_session_live() -> None:
    ctx = MagicMock()
    ctx.info = AsyncMock()
    await safe_info(ctx, "hello")
    ctx.info.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_safe_info_falls_back_to_stdlib_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without an MCP session, ``ctx.info`` raises ``RuntimeError`` — the
    wrapper must catch it and route through the process logger so the
    message isn't silently dropped (and the surrounding handler keeps
    going)."""
    ctx = MagicMock()
    ctx.info = AsyncMock(
        side_effect=RuntimeError(
            "session is not available because the MCP session has not been established yet"
        )
    )
    with caplog.at_level(logging.INFO, logger="app.handlers._context_log"):
        await safe_info(ctx, "fallback-message")
    assert any("fallback-message" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_safe_warning_and_safe_error_have_same_fallback() -> None:
    """Symmetry: warning + error wrappers share the same safety guarantee
    (none of the handlers use them today but the helper is exported for
    future side-effect logs)."""
    ctx = MagicMock()
    ctx.warning = AsyncMock(side_effect=RuntimeError("no session"))
    ctx.error = AsyncMock(side_effect=RuntimeError("no session"))
    # Neither raises — that's the assertion.
    await safe_warning(ctx, "warn")
    await safe_error(ctx, "err")
