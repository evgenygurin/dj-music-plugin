from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.timing import DetailedTimingMiddleware


def _ctx(tool: str = "t") -> MiddlewareContext:
    msg = MagicMock()
    msg.name = tool
    return MiddlewareContext(message=msg, fastmcp_context=None)


@pytest.mark.asyncio
async def test_records_duration_on_success() -> None:
    observed: list[tuple[str, float, bool]] = []

    def recorder(name: str, duration: float, ok: bool) -> None:
        observed.append((name, duration, ok))

    mw = DetailedTimingMiddleware(record=recorder)

    async def slow(_ctx):
        await asyncio.sleep(0.01)
        return "ok"

    await mw.on_call_tool(_ctx("entity_list"), slow)
    assert len(observed) == 1
    name, dur, ok = observed[0]
    assert name == "entity_list"
    assert dur >= 0.005
    assert ok is True


@pytest.mark.asyncio
async def test_records_duration_on_failure() -> None:
    observed: list[tuple[str, float, bool]] = []
    mw = DetailedTimingMiddleware(record=lambda n, d, ok: observed.append((n, d, ok)))
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(_ctx("x"), call_next)
    assert observed[0][2] is False
