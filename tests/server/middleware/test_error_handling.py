from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext

from app.server.middleware.error_handling import ErrorHandlingMiddleware
from app.shared.errors import (
    ConflictError,
    NotAllowedError,
    NotFoundError,
    ValidationError,
)


def _ctx() -> MiddlewareContext:
    return MiddlewareContext.__new__(MiddlewareContext)


@pytest.mark.asyncio
async def test_passes_through_success() -> None:
    mw = ErrorHandlingMiddleware(mask_details=True)
    call_next = AsyncMock(return_value="ok")
    assert await mw.on_call_tool(_ctx(), call_next) == "ok"


@pytest.mark.parametrize(
    "exc_cls,message_substring",
    [
        (NotFoundError, "not found"),
        (ValidationError, "invalid"),
        (ConflictError, "conflict"),
        (NotAllowedError, "not allowed"),
    ],
)
@pytest.mark.asyncio
async def test_maps_domain_errors_to_tool_error(exc_cls: type, message_substring: str) -> None:
    mw = ErrorHandlingMiddleware(mask_details=True)
    if exc_cls is NotFoundError:
        exc = exc_cls("track", 42)
    elif exc_cls is ValidationError:
        exc = exc_cls("invalid input")
    elif exc_cls is NotAllowedError:
        exc = exc_cls(entity="track", operation="delete")
    else:
        exc = exc_cls("conflict happened")
    call_next = AsyncMock(side_effect=exc)
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert message_substring in str(info.value).lower()


@pytest.mark.asyncio
async def test_wraps_unknown_exception_masked() -> None:
    mw = ErrorHandlingMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert "boom" not in str(info.value)


@pytest.mark.asyncio
async def test_surfaces_unknown_when_unmasked() -> None:
    mw = ErrorHandlingMiddleware(mask_details=False)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert "boom" in str(info.value)


@pytest.mark.asyncio
async def test_tool_error_passthrough() -> None:
    mw = ErrorHandlingMiddleware(mask_details=True)
    original = ToolError("already a tool error")
    call_next = AsyncMock(side_effect=original)
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert info.value is original
