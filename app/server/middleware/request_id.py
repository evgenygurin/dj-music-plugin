"""Inject a request_id into contextvars for structured tracing."""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.shared.logger import set_request_id


class RequestIdMiddleware(Middleware):
    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        rid = set_request_id()
        fctx = getattr(context, "fastmcp_context", None)
        if fctx is not None:
            with contextlib.suppress(RuntimeError):
                await fctx.set_state("request_id", rid, serializable=True)
        try:
            return await call_next(context)
        finally:
            set_request_id("")

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        set_request_id()
        try:
            return await call_next(context)
        finally:
            set_request_id("")

    async def on_get_prompt(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        set_request_id()
        try:
            return await call_next(context)
        finally:
            set_request_id("")
