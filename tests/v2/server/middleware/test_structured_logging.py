from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.server.middleware.structured_logging import (
    StructuredLoggingMiddleware,
)


def _ctx(name: str = "entity_list") -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    msg.arguments = {"id": 1}
    fctx = MagicMock()
    fctx.session_id = "s1"
    fctx.request_id = "r9"
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


@pytest.mark.asyncio
async def test_logs_enter_and_exit(caplog) -> None:
    mw = StructuredLoggingMiddleware()
    call_next = AsyncMock(return_value={"ok": True})
    with caplog.at_level(logging.INFO, logger="app.v2.server.middleware.structured_logging"):
        await mw.on_call_tool(_ctx(), call_next)
    messages = [r.message for r in caplog.records]
    assert any("call_tool.enter" in m for m in messages)
    assert any("call_tool.exit" in m for m in messages)


@pytest.mark.asyncio
async def test_logs_error(caplog) -> None:
    mw = StructuredLoggingMiddleware()
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with (
        caplog.at_level(logging.INFO, logger="app.v2.server.middleware.structured_logging"),
        pytest.raises(RuntimeError),
    ):
        await mw.on_call_tool(_ctx("x"), call_next)
    assert any("call_tool.error" in r.message for r in caplog.records)
