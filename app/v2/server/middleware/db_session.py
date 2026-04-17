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

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.repositories.unit_of_work import UnitOfWork

log = logging.getLogger(__name__)


class DbSessionMiddleware(Middleware):
    async def on_call_tool(
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
            log.debug("no db_session_factory — tool runs without UoW")
            return await call_next(context)

        session = factory()
        uow = UnitOfWork(session)
        fctx.state["uow"] = uow
        try:
            result = await call_next(context)
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()
            return result
        finally:
            fctx.state.pop("uow", None)
            await session.close()
