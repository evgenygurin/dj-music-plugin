"""Shared helpers for middleware unit tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from fastmcp.server.middleware import MiddlewareContext


def make_ctx(
    *,
    tool_name: str = "entity_list",
    arguments: dict[str, Any] | None = None,
    fastmcp_context: Any | None = ...,  # sentinel
) -> MiddlewareContext:
    """Build a MiddlewareContext (frozen dataclass) with a mock message."""
    msg = MagicMock()
    msg.name = tool_name
    msg.arguments = arguments if arguments is not None else {}
    if fastmcp_context is ...:
        fastmcp_context = MagicMock()
    return MiddlewareContext(message=msg, fastmcp_context=fastmcp_context)


def make_async_ctx(
    *,
    tool_name: str = "t",
    state: dict[str, Any] | None = None,
) -> MiddlewareContext:
    """MiddlewareContext with real async state thunks.

    Middleware under test calls ``await fctx.set_state(...)``; a plain
    MagicMock returns another MagicMock there (not a coroutine), which
    crashes with ``TypeError: object MagicMock can't be used in 'await'
    expression``. Install real async thunks that mutate an ordinary
    dict, so assertions like
    ``ctx.fastmcp_context.state["cost"]["llm_tokens"] += 1500`` still
    behave correctly.
    """
    state_dict: dict[str, Any] = {} if state is None else state

    async def _set(key: str, value: Any, *, serializable: bool = True) -> None:
        state_dict[key] = value

    async def _delete(key: str) -> None:
        state_dict.pop(key, None)

    async def _get(key: str, default: Any = None) -> Any:
        return state_dict.get(key, default)

    fctx = MagicMock()
    fctx.state = state_dict
    fctx.set_state = _set
    fctx.delete_state = _delete
    fctx.get_state = _get
    msg = MagicMock()
    msg.name = tool_name
    return MiddlewareContext(message=msg, fastmcp_context=fctx)
