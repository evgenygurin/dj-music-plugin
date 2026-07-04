"""Outermost middleware: map domain exceptions to MCP wire-level errors.

Translates ``NotFoundError``, ``ValidationError``, ``ConflictError``,
``NotAllowedError``, and generic ``DJMusicError`` raised by repositories,
handlers, and domain logic into the matching FastMCP envelope type
(``ToolError`` for tools, ``ResourceError`` for resources, ``PromptError``
for prompts) with stable human-readable messages.

Unknown exceptions are wrapped with a generic message in production
(``mask_details=True``) or surfaced verbatim in dev.

``McpError`` (FastMCP native signal type, e.g. from ``@tool(timeout=N)``
which raises code ``-32000``) is re-raised unchanged so clients keep
the protocol-level error code and timeout-specific handling.

Distinct from ``fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware``
(which focuses on exception logging and tracebacks — not domain mapping).
Renamed from ``ErrorHandlingMiddleware`` in v1.0.4 to avoid the name
collision with the built-in.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import (
    NotFoundError as FastMCPNotFoundError,
)
from fastmcp.exceptions import (
    PromptError,
    ResourceError,
    ToolError,
)
from fastmcp.server.middleware import Middleware, MiddlewareContext
from mcp.shared.exceptions import McpError
from sqlalchemy.exc import DBAPIError

from app.shared.errors import (
    ConflictError,
    DJMusicError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger(__name__)


class DomainErrorMiddleware(Middleware):
    """Translate domain exceptions to the matching FastMCP error envelope."""

    def __init__(self, *, mask_details: bool | None = None) -> None:
        if mask_details is None:
            from app.config import get_settings

            mask_details = not get_settings().mcp.debug
        self.mask_details = mask_details

    async def _dispatch(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
        *,
        envelope: type[ToolError | ResourceError | PromptError],
        what: str,
    ) -> Any:
        try:
            return await call_next(context)
        except NotFoundError as exc:
            raise envelope(f"not found: {exc}") from exc
        except ValidationError as exc:
            raise envelope(f"invalid input: {exc}") from exc
        except ConflictError as exc:
            raise envelope(f"conflict: {exc}") from exc
        except NotAllowedError as exc:
            raise envelope(f"operation not allowed: {exc}") from exc
        except DJMusicError as exc:
            raise envelope(str(exc)) from exc
        except FastMCPNotFoundError as exc:
            # Distinct from ``app.shared.errors.NotFoundError`` — this fires
            # when the FastMCP server can't find a registered prompt /
            # resource by name (e.g. ``get_prompt('typo')``). Without this
            # branch the generic Exception handler wraps it as
            # ``"internal error: Unknown prompt: ..."`` which masks the
            # actionable detail.
            raise envelope(f"not found: {exc}") from exc
        except (ToolError, ResourceError, PromptError):
            raise
        except McpError:
            # Preserve FastMCP / MCP protocol-level errors verbatim.
            # Native ``@tool(timeout=N)`` raises ``McpError(code=-32000)`` —
            # rewriting it as a generic envelope would drop both the timeout
            # signal and its diagnostic message.
            raise
        except DBAPIError as exc:
            log.exception("database error in %s", what)
            orig = str(getattr(exc, "orig", "")).lower()
            if getattr(exc, "connection_invalidated", False) or "connection" in orig:
                raise envelope("database connection lost; retry the request") from exc
            raise envelope("database error") from exc
        except Exception as exc:
            log.exception("unexpected error in %s", what)
            if self.mask_details:
                raise envelope("internal error") from exc
            raise envelope(f"internal error: {exc}") from exc

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        return await self._dispatch(context, call_next, envelope=ToolError, what="tool")

    async def on_read_resource(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        return await self._dispatch(context, call_next, envelope=ResourceError, what="resource")

    async def on_get_prompt(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        return await self._dispatch(context, call_next, envelope=PromptError, what="prompt")
