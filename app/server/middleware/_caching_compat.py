"""Compat shim for FastMCP 3.4.2 ``ResponseCachingMiddleware``.

Upstream's ``ResponseCachingMiddleware`` handlers invoke
``call_next(context=context)`` by **keyword**
(``fastmcp/server/middleware/caching.py``), but the chain builder
``FastMCP._run_middleware`` wraps each link as ``wrapped(ctx, ...)`` which only
accepts the context **positionally**. So every cached call (tool / prompt /
resource) raises ``TypeError: FastMCP._run_middleware.<locals>.wrapped() got an
unexpected keyword argument 'context'``. ``ResponseCachingMiddleware`` is the
only built-in middleware that uses the keyword form (every other one calls
``call_next(context)`` positionally), so this is an isolated upstream mismatch.

This subclass wraps ``call_next`` in a thin adapter that accepts the ``context``
keyword and forwards it positionally, then delegates to the upstream handler —
caching semantics (key, ttl, get/put) are untouched. It is named
``ResponseCachingMiddleware`` so ``ALL_MIDDLEWARE`` class names (and
``tests/server/test_ordering.py`` / ``test_build.py``) stay unchanged.

Remove once the upstream keyword/positional mismatch is fixed (FastMCP > 3.4.2).
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.middleware.caching import (
    ResponseCachingMiddleware as _UpstreamResponseCachingMiddleware,
)


def _accept_context_kw(call_next: Any) -> Any:
    """Adapt ``call_next`` so a ``call_next(context=...)`` keyword call resolves.

    The upstream caching handlers call ``call_next(context=context)``; the chain
    link they receive (``server._run_middleware.wrapped``) only accepts the
    context positionally. This adapter accepts it either way and forwards
    positionally.
    """

    async def adapted(context: Any) -> Any:
        return await call_next(context)

    return adapted


class ResponseCachingMiddleware(_UpstreamResponseCachingMiddleware):
    """``ResponseCachingMiddleware`` with the keyword-``call_next`` shim applied
    to every handler that uses the keyword form upstream."""

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        return await super().on_call_tool(context, _accept_context_kw(call_next))

    async def on_get_prompt(self, context: Any, call_next: Any) -> Any:
        return await super().on_get_prompt(context, _accept_context_kw(call_next))

    async def on_read_resource(self, context: Any, call_next: Any) -> Any:
        return await super().on_read_resource(context, _accept_context_kw(call_next))

    async def on_list_tools(self, context: Any, call_next: Any) -> Any:
        return await super().on_list_tools(context, _accept_context_kw(call_next))

    async def on_list_resources(self, context: Any, call_next: Any) -> Any:
        return await super().on_list_resources(context, _accept_context_kw(call_next))

    async def on_list_prompts(self, context: Any, call_next: Any) -> Any:
        return await super().on_list_prompts(context, _accept_context_kw(call_next))
