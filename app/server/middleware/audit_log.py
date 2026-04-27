"""Audit log for mutation tool calls.

Skips read-only tools (annotations.readOnlyHint). Records name + args hash +
outcome. Payload hashes (sha256) are cheap to store and audit-safe.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


def _default_sink(event: dict[str, Any]) -> None:
    log.info("mcp_audit", extra={"mcp_extra": event})


def _hash_args(args: Any) -> str:
    try:
        payload = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        payload = repr(args)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class AuditLogMiddleware(Middleware):
    def __init__(self, *, sink: Callable[[dict[str, Any]], None] = _default_sink) -> None:
        self._sink = sink

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        args = getattr(context.message, "arguments", {}) or {}

        readonly = False
        fctx = getattr(context, "fastmcp_context", None)
        if fctx is not None:
            try:
                tool = await fctx.fastmcp.get_tool(name)
                readonly = bool(getattr(getattr(tool, "annotations", None), "readOnlyHint", False))
            except Exception:
                readonly = False

        if readonly:
            return await call_next(context)

        started_at = time.time()
        try:
            result = await call_next(context)
        except Exception as exc:
            self._sink(
                {
                    "tool": name,
                    "args_hash": _hash_args(args),
                    "status": "error",
                    "error": type(exc).__name__,
                    "t": started_at,
                }
            )
            raise
        self._sink(
            {
                "tool": name,
                "args_hash": _hash_args(args),
                "status": "ok",
                "t": started_at,
            }
        )
        return result
