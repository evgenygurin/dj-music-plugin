"""Domain-to-MCP error mapping for tool adapters.

Services raise typed domain errors (``NotFoundError``, ``ValidationError``,
``ConflictError``) from :mod:`app.core.errors`. MCP clients expect a
:class:`fastmcp.exceptions.ToolError`.

Rather than litter every tool body with ``try/except`` blocks — and hide
the intent behind boilerplate — this module exposes a single decorator
and context manager that transparently re-raise domain errors as
``ToolError`` instances with a stable, human-readable message.

Usage::

    from app.mcp.tools._shared import map_domain_errors

    @tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
    @map_domain_errors
    async def quick_set_review(set_id: int, svc: ...) -> dict: ...

    # or inline:
    async def tool_body():
        async with domain_errors_as_tool_error():
            ...

The decorator catches :class:`NotFoundError`, :class:`ValidationError`
and :class:`ConflictError`. ``ToolError`` itself passes through
untouched, so tools can still raise it directly for input validation.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, TypeVar

from fastmcp.exceptions import ToolError

from app.core.errors import ConflictError, NotFoundError, ValidationError

R = TypeVar("R")


@asynccontextmanager
async def domain_errors_as_tool_error() -> AsyncIterator[None]:
    """Context manager: translate domain exceptions to :class:`ToolError`."""
    try:
        yield
    except ToolError:
        raise
    except NotFoundError as exc:
        raise ToolError(str(exc)) from exc
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc
    except ConflictError as exc:
        raise ToolError(str(exc)) from exc


def map_domain_errors[R](fn: Callable[..., Awaitable[R]]) -> Callable[..., Awaitable[R]]:
    """Decorator: translate domain exceptions to :class:`ToolError`.

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
