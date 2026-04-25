"""Open a UnitOfWork per tool call.

- Reads ``db_session_factory`` from the lifespan context.
- Creates a fresh SQLAlchemy ``AsyncSession`` and wraps it in ``UnitOfWork``.
- Stashes the UoW on ``ctx.fastmcp_context.state["uow"]``.
- Tools consume it via ``Depends(get_uow)`` (see ``app/v2/server/di.py``).
- Commits on success, rolls back on exception, always closes the session.

Replaces the legacy ``get_db_session()`` DI helper — transaction boundary is
now exactly one tool call, enforced from the middleware layer.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


# Stateless-context fallback for DI — set when fctx.set_state cannot be used
# (REST/in-process where there is no MCP session). DI reads it as last resort.
# ContextVar is async-task-local, so concurrent tool calls do not collide.
_stateless_uow: ContextVar[UnitOfWork | None] = ContextVar("_stateless_uow", default=None)


def read_stateless_uow() -> UnitOfWork | None:
    """Public accessor for the stateless UoW fallback. Read by app.server.di."""
    return _stateless_uow.get()


class DbSessionMiddleware(Middleware):
    async def _wrap(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = context.fastmcp_context
        if fctx is None:
            return await call_next(context)

        factory = None
        rc = getattr(fctx, "request_context", None)
        if rc is not None:
            lc = getattr(rc, "lifespan_context", None) or {}
            factory = lc.get("db_session_factory") if isinstance(lc, dict) else None
        if factory is None:
            # REST/in-process callers do not enter the MCP lifespan, so the
            # factory is missing. Bootstrap directly from the process-wide
            # singleton — avoids requiring REST to wrap MCP's lifespan.
            try:
                from app.db.session import get_session_factory

                factory = get_session_factory()
            except Exception:
                log.warning("could not bootstrap db_session_factory; UoW DI will fail")
                return await call_next(context)

        session = factory()
        uow = UnitOfWork(session)
        token = None
        try:
            await fctx.set_state("uow", uow, serializable=False)
        except RuntimeError:
            # Stateless context (REST/in-process): no MCP session id available,
            # so set_state cannot scope a key. Stash on a ContextVar that DI
            # reads as a third fallback after get_state and state.get.
            token = _stateless_uow.set(uow)
        try:
            result = await call_next(context)
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()
            return result
        finally:
            if token is not None:
                _stateless_uow.reset(token)
            else:
                with contextlib.suppress(RuntimeError):
                    await fctx.delete_state("uow")
            await session.close()

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        return await self._wrap(context, call_next)

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        return await self._wrap(context, call_next)
