"""Limit concurrent tool calls to prevent resource exhaustion.

The stdio MCP transport dispatches every tool call to its own asyncio
task inside a shared task group. When the client fires N parallel calls
(e.g. ``entity_create(track_features)`` for 6 tracks), N handlers run
concurrently. Each holds a DB connection for the entire duration of the
call (opened by ``DbSessionMiddleware``). With ``pool_size=5`` a 6th
call hangs forever on ``asyncpg``'s pool wait.

This middleware serialises all tool calls through an ``asyncio.Semaphore``,
capping in-flight concurrency. Read-only ``entity_get`` / ``entity_list``
calls are exempted — they are fast and hold connections briefly.

Default max_concurrency matches the DB pool_size so one queue slot maps
to one pool connection, leaving other consumers (providers, prompts,
resources) unaffected.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

_READ_ONLY_TOOLS = frozenset(
    {
        "entity_get",
        "entity_list",
        "entity_aggregate",
        "provider_read",
        "provider_search",
        "transition_score_pool",
        "sequence_optimize",
        "ui_library_audit",
        "ui_library_dashboard",
        "ui_camelot_wheel",
        "ui_score_pool_matrix",
        "ui_set_view",
        "ui_transition_score",
    }
)


class ConcurrencyLimiterMiddleware(Middleware):
    def __init__(self, max_concurrency: int = 10) -> None:
        self._sem = asyncio.Semaphore(max_concurrency)

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        if name in _READ_ONLY_TOOLS:
            return await call_next(context)
        async with self._sem:
            return await call_next(context)
