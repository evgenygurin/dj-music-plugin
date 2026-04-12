"""Domain-to-MCP error mapping for tool adapters.

Services raise typed domain errors (``NotFoundError``, ``ValidationError``,
``ConflictError``) from :mod:`app.core.errors`. The MCP transport layer
expects FastMCP-native exception types so they reach the client with the
correct JSON-RPC error code instead of a generic
``-32603 Internal error`` envelope.

Why this is non-trivial:

1. ``fastmcp.server.server.FastMCP._call_tool`` (lines 986-1010) only
   re-raises subclasses of ``FastMCPError`` and Pydantic
   ``ValidationError`` *unmodified*. Anything else gets wrapped as
   ``ToolError("Error calling tool 'X'")`` when ``mask_error_details=True``,
   which destroys the original message before it leaves the tool layer.
2. The outer ``ErrorHandlingMiddleware._transform_error`` then maps
   only a fixed set of types to clean MCP error codes:

   * ``fastmcp.exceptions.NotFoundError`` / ``FileNotFoundError`` /
     ``KeyError`` → ``-32001 Not found``
   * ``ValueError`` / ``TypeError``               → ``-32602 Invalid params``
   * ``PermissionError``                          → ``-32000 Permission denied``
   * ``TimeoutError``                             → ``-32000 Request timeout``
   * everything else (incl. bare ``ToolError``)   → ``-32603 Internal error``

So we translate each domain exception to the *exact* type both layers
already understand:

| Domain error           | Raised as                       | Final MCP code         |
|------------------------|---------------------------------|------------------------|
| ``NotFoundError``      | ``fastmcp.exceptions.NotFoundError`` | ``-32001 Not found``   |
| ``ValidationError``    | ``ValueError``                  | ``-32602 Invalid params`` |
| ``ConflictError``      | ``ToolError`` (best available)  | ``-32603 Internal error: Conflict: …`` |

Conflicts are rare; until upstream FastMCP supports a richer
business-error contract, the "Internal error" envelope is acceptable
for them.

Usage::

    from dj_music.tools._shared import map_domain_errors

    @tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
    @map_domain_errors
    async def quick_set_review(set_id: int, svc: ...) -> dict: ...

    # or inline:
    async def tool_body():
        async with domain_errors_as_tool_error():
            ...
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, TypeVar

from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
from fastmcp.exceptions import ToolError
from mcp import McpError

from dj_music.core.errors import ConflictError, NotFoundError, ValidationError

R = TypeVar("R")


@asynccontextmanager
async def domain_errors_as_tool_error() -> AsyncIterator[None]:
    """Translate domain exceptions to FastMCP-native error types.

    See module docstring for the mapping table and rationale.
    """
    try:
        yield
    except (McpError, FastMCPNotFoundError, ToolError):
        raise
    except NotFoundError as exc:
        raise FastMCPNotFoundError(str(exc)) from exc
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    except ConflictError as exc:
        raise ToolError(f"Conflict: {exc}") from exc


def map_domain_errors[R](fn: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    """Decorator: translate domain exceptions to FastMCP-native error types.

    Applied to ``@tool`` functions that call services which raise
    :class:`~app.core.errors.NotFoundError`, :class:`ValidationError` or
    :class:`ConflictError`. Preserves the wrapped function's signature
    and metadata so FastMCP's schema introspection stays intact.
    """

    @wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> R:
        async with domain_errors_as_tool_error():
            return await fn(*args, **kwargs)

    return wrapper
