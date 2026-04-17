from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.deprecation_warning import (
    DeprecationWarningMiddleware,
)


def _ctx(tool_name: str, version: str | None) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = tool_name
    fctx = MagicMock()
    tool = MagicMock()
    tool.version = version
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


@pytest.mark.asyncio
async def test_warns_on_version_1_0() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("old_tool", "1.0"), call_next)
    assert warnings
    assert "old_tool" in warnings[0]


@pytest.mark.asyncio
async def test_no_warning_on_current_version() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("new_tool", "2.0"), call_next)
    assert warnings == []


@pytest.mark.asyncio
async def test_no_warning_when_unversioned() -> None:
    warnings: list[str] = []
    mw = DeprecationWarningMiddleware(emit=lambda m: warnings.append(m))
    call_next = AsyncMock(return_value="ok")
    await mw.on_call_tool(_ctx("plain", None), call_next)
    assert warnings == []
