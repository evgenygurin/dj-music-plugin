"""Count provider API calls + LLM sampling tokens per tool call.

Tools / handlers / adapters bump counters on ``ctx.fastmcp_context.state["cost"]``;
middleware resets counters at call start and emits totals at end.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


def _default_sink(event: dict[str, Any]) -> None:
    log.info("mcp_cost", extra={"mcp_extra": event})


class CostTrackingMiddleware(Middleware):
    def __init__(self, *, sink: Callable[[dict[str, Any]], None] = _default_sink) -> None:
        self._sink = sink

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = getattr(context, "fastmcp_context", None)
        if fctx is None:
            return await call_next(context)
        try:
            await fctx.set_state("cost", {"provider_calls": 0, "llm_tokens": 0})
        except RuntimeError:
            # Stateless context (in-process callers): set_state internally builds
            # a key from session_id, which raises when there is no MCP session.
            # Cost tracking is per-call observability — silently skip.
            return await call_next(context)
        try:
            return await call_next(context)
        finally:
            totals = await fctx.get_state("cost") or {"provider_calls": 0, "llm_tokens": 0}
            self._sink(
                {
                    "tool": getattr(context.message, "name", "<unknown>"),
                    "provider_calls": totals.get("provider_calls", 0),
                    "llm_tokens": totals.get("llm_tokens", 0),
                }
            )
