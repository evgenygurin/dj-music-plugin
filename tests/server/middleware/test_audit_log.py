from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.audit_log import AuditLogMiddleware


def _ctx(name: str, readonly: bool) -> MiddlewareContext:
    msg = MagicMock()
    msg.name = name
    msg.arguments = {"id": 42}
    fctx = MagicMock()
    tool = MagicMock()
    tool.annotations = MagicMock()
    tool.annotations.readOnlyHint = readonly
    fctx.fastmcp.get_tool = AsyncMock(return_value=tool)
    return MiddlewareContext(message=msg, fastmcp_context=fctx)


@pytest.mark.asyncio
async def test_logs_mutation_tool() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(return_value={"created_id": 7})
    await mw.on_call_tool(_ctx("entity_create", readonly=False), call_next)
    assert len(events) == 1
    ev = events[0]
    assert ev["tool"] == "entity_create"
    assert "args_hash" in ev
    assert ev["status"] == "ok"


@pytest.mark.asyncio
async def test_skips_readonly_tool() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(return_value={"items": []})
    await mw.on_call_tool(_ctx("entity_list", readonly=True), call_next)
    assert events == []


@pytest.mark.asyncio
async def test_records_failure() -> None:
    events: list[dict] = []
    mw = AuditLogMiddleware(sink=events.append)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx("entity_delete", readonly=False), call_next)
    assert events[0]["status"] == "error"
