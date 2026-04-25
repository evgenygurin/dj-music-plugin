from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp.server.middleware import MiddlewareContext

from app.repositories.unit_of_work import UnitOfWork
from app.server.middleware.db_session import DbSessionMiddleware

from .conftest import make_async_ctx


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
    mc = make_async_ctx(tool_name="entity_list")
    mc.fastmcp_context.request_context = SimpleNamespace(
        lifespan_context={"db_session_factory": factory}
    )
    return mc, mc.fastmcp_context


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


@pytest.mark.asyncio
async def test_uow_reachable_when_session_unavailable() -> None:
    """REST/in-process: set_state raises RuntimeError; UoW must still reach DI.

    FastMCP's Context has no ``.state`` attribute outside an active session, so
    the middleware stashes the UoW on a module-level ContextVar (async-task
    local). DI's get_uow reads it as the third fallback. Without this, tools
    see "UnitOfWork not initialized" and every call returns 500.
    """
    from app.server.middleware.db_session import read_stateless_uow

    session = _FakeSession()

    async def _raises(*_a: object, **_kw: object) -> None:
        raise RuntimeError("session_id is not available because no session exists")

    fctx = MagicMock()
    fctx.set_state = _raises
    fctx.delete_state = _raises
    fctx.request_context = SimpleNamespace(
        lifespan_context={"db_session_factory": lambda: session}
    )
    msg = MagicMock()
    msg.name = "entity_aggregate"
    mc = MiddlewareContext(message=msg, fastmcp_context=fctx)

    mw = DbSessionMiddleware()
    seen: dict = {}

    async def handler(_c):
        # Simulates what app/server/di.get_uow does as third fallback.
        seen["uow"] = read_stateless_uow()
        return "ok"

    result = await mw.on_call_tool(mc, handler)

    assert result == "ok"
    assert isinstance(seen["uow"], UnitOfWork)
    assert session.committed and session.closed
    assert read_stateless_uow() is None  # ContextVar reset in finally
