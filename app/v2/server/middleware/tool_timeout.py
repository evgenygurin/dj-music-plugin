"""Per-tool timeout driven by ``tool.meta['timeout_s']``.

Falls back to ``default_timeout`` when a tool does not declare one. Wraps
``asyncio.wait_for`` — cancelled coroutines become ``ToolError("tool X
timed out after Ys")``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.v2.config import get_settings


class ToolCallTimeoutMiddleware(Middleware):
    def __init__(self, *, default_timeout: float | None = None) -> None:
        if default_timeout is None:
            default_timeout = get_settings().mcp.default_tool_timeout_s
        self.default_timeout = default_timeout

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        timeout = self.default_timeout
        fctx = context.fastmcp_context
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                meta = getattr(tool, "meta", None) or {}
                if "timeout_s" in meta:
                    timeout = float(meta["timeout_s"])
            except Exception:
                pass
        try:
            return await asyncio.wait_for(call_next(context), timeout=timeout)
        except TimeoutError as exc:
            raise ToolError(f"tool '{name}' timed out after {timeout}s") from exc
