"""Warn when a client calls a tool at a deprecated version.

Tools marked ``@tool(version="1.0")`` are kept for transition while the
same-named ``version="2.0"`` rolls out. This middleware fires a structured
log so telemetry can track callers still on v1.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)

DEPRECATED_VERSIONS = frozenset({"1.0"})


def _default_emit(message: str) -> None:
    log.warning("deprecation: %s", message, extra={"mcp_extra": {"deprecated": True}})


class DeprecationWarningMiddleware(Middleware):
    def __init__(self, *, emit: Callable[[str], None] = _default_emit) -> None:
        self._emit = emit

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        fctx = getattr(context, "fastmcp_context", None)
        name = getattr(context.message, "name", "<unknown>")
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                version = getattr(tool, "version", None)
            except Exception:
                version = None
            if version in DEPRECATED_VERSIONS:
                self._emit(f"tool '{name}' version={version} is deprecated")
        return await call_next(context)
