from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.server.middleware.db_session import DbSessionMiddleware


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


def _ctx_with_factory(factory):
    fctx = MagicMock()
    fctx.state = {}
    fctx.request_context = SimpleNamespace(lifespan_context={"db_session_factory": factory})
    msg = MagicMock()
    msg.name = "entity_list"
    mc = MiddlewareContext(message=msg, fastmcp_context=fctx)
    return mc, fctx


@pytest.mark.asyncio
async def test_sets_uow_on_state_and_commits_on_success() -> None:
    session = _FakeSession()
    ctx, _ = _ctx_with_factory(lambda: session)
    mw = DbSessionMiddleware()
    seen: dict = {}

    async def handler(c):
        seen["uow"] = c.fastmcp_context.state["uow"]
        return "ok"

    await mw.on_call_tool(ctx, handler)
    assert isinstance(seen["uow"], UnitOfWork)
    assert session.committed and not session.rolled_back
    assert session.closed


@pytest.mark.asyncio
async def test_rolls_back_on_error() -> None:
    session = _FakeSession()
    ctx, _ = _ctx_with_factory(lambda: session)
    mw = DbSessionMiddleware()
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await mw.on_call_tool(ctx, handler)
    assert session.rolled_back and not session.committed
    assert session.closed


@pytest.mark.asyncio
async def test_skips_when_no_factory_available() -> None:
    msg = MagicMock()
    msg.name = "t"
    mc = MiddlewareContext(message=msg, fastmcp_context=None)
    mw = DbSessionMiddleware()
    handler = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(mc, handler) == "ok"
