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
