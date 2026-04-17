"""Cache results of read-only tool calls (TTL + LRU).

Key = (tool_name, json(arguments, sort_keys=True)). Read-only tools
(annotations.readOnlyHint) are expected to be pure functions of their inputs.
"""

from __future__ import annotations

import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

log = logging.getLogger(__name__)


def _key_for(name: str, args: Any) -> str:
    try:
        payload = json.dumps(args, sort_keys=True, default=str)
    except TypeError:
        payload = repr(args)
    return f"{name}|{payload}"


class ResponseCachingMiddleware(Middleware):
    def __init__(
        self,
        *,
        ttl_seconds: float | None = None,
        max_entries: int | None = None,
    ) -> None:
        if ttl_seconds is None or max_entries is None:
            from app.v2.config import get_settings

            s = get_settings().mcp
            if ttl_seconds is None:
                ttl_seconds = s.response_cache_ttl
            if max_entries is None:
                max_entries = s.response_cache_max
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _get(self, key: str) -> Any | None:
        hit = self._store.get(key)
        if hit is None:
            return None
        expires_at, value = hit
        if expires_at < time.monotonic():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def _put(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        name = getattr(context.message, "name", "<unknown>")
        fctx = getattr(context, "fastmcp_context", None)
        if fctx is None:
            return await call_next(context)
        try:
            tool = await fctx.fastmcp.get_tool(name)
        except Exception:
            return await call_next(context)
        readonly = bool(getattr(getattr(tool, "annotations", None), "readOnlyHint", False))
        if not readonly:
            return await call_next(context)

        args = getattr(context.message, "arguments", {}) or {}
        key = _key_for(name, args)
        cached = self._get(key)
        if cached is not None:
            return cached
        result = await call_next(context)
        self._put(key, result)
        return result
