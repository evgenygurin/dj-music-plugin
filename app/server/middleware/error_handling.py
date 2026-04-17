"""Outermost middleware: map domain errors to MCP ToolError.

Unknown exceptions are wrapped with a generic message in production
(``mask_details=True``) or surfaced verbatim in dev.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.shared.errors import (
    ConflictError,
    DJMusicError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)

log = logging.getLogger(__name__)


class ErrorHandlingMiddleware(Middleware):
    """Translate exceptions to ``ToolError`` with stable messages."""

    def __init__(self, *, mask_details: bool | None = None) -> None:
        if mask_details is None:
            from app.config import get_settings

            mask_details = not get_settings().mcp.debug
        self.mask_details = mask_details

    async def on_call_tool(
        self,
        context: MiddlewareContext,
        call_next: Callable[[MiddlewareContext], Awaitable[Any]],
    ) -> Any:
        try:
            return await call_next(context)
        except NotFoundError as exc:
            raise ToolError(f"not found: {exc}") from exc
        except ValidationError as exc:
            raise ToolError(f"invalid input: {exc}") from exc
        except ConflictError as exc:
            raise ToolError(f"conflict: {exc}") from exc
        except NotAllowedError as exc:
            raise ToolError(f"operation not allowed: {exc}") from exc
        except DJMusicError as exc:
            raise ToolError(str(exc)) from exc
        except ToolError:
            raise
        except Exception as exc:
            log.exception("unexpected error in tool")
            if self.mask_details:
                raise ToolError("internal error") from exc
            raise ToolError(f"internal error: {exc}") from exc
