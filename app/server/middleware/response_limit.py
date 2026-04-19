"""Guard against oversized tool responses.

Large payloads poison LLM context. Oversized results are reported as a
``ToolError`` so the MCP envelope stays well-typed — returning a bare
``dict`` here broke the FastMCP response adapter (``'dict' object has no
attribute 'to_mcp_result'``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


class ResponseLimitingMiddleware(Middleware):
    def __init__(self, *, max_bytes: int | None = None) -> None:
        if max_bytes is None:
            from app.config import get_settings

            max_bytes = get_settings().mcp.response_max_bytes
        self.max_bytes = max_bytes

    def _size(self, value: Any) -> int:
        if isinstance(value, str):
            return len(value.encode())
        try:
            return len(json.dumps(value, default=str).encode())
        except TypeError:
            return len(repr(value).encode())

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        result = await call_next(context)
        size = self._size(result)
        if size <= self.max_bytes:
            return result
        tool = getattr(context.message, "name", "<unknown>")
        log.warning(
            "response oversized tool=%s bytes=%d limit=%d",
            tool,
            size,
            self.max_bytes,
        )
        if isinstance(result, str):
            return result[: self.max_bytes] + "\n…(truncated)"
        raise ToolError(
            f"{tool} response exceeded response_max_bytes "
            f"({size} > {self.max_bytes}); narrow filters or paginate",
        )
