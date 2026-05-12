from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastmcp.exceptions import (
    NotFoundError as FastMCPNotFoundError,
)
from fastmcp.exceptions import (
    PromptError,
    ResourceError,
    ToolError,
)
from fastmcp.server.middleware import MiddlewareContext
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from app.server.middleware.domain_error import DomainErrorMiddleware
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
    mw = DomainErrorMiddleware(mask_details=True)
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
    mw = DomainErrorMiddleware(mask_details=True)
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
    mw = DomainErrorMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert "boom" not in str(info.value)


@pytest.mark.asyncio
async def test_surfaces_unknown_when_unmasked() -> None:
    mw = DomainErrorMiddleware(mask_details=False)
    call_next = AsyncMock(side_effect=RuntimeError("boom"))
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert "boom" in str(info.value)


@pytest.mark.asyncio
async def test_tool_error_passthrough() -> None:
    mw = DomainErrorMiddleware(mask_details=True)
    original = ToolError("already a tool error")
    call_next = AsyncMock(side_effect=original)
    with pytest.raises(ToolError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert info.value is original


@pytest.mark.asyncio
async def test_mcp_error_passthrough() -> None:
    """Native ``@tool(timeout=N)`` raises ``McpError(code=-32000)`` — the
    middleware must propagate it unchanged so clients keep the protocol-
    level error code."""
    mw = DomainErrorMiddleware(mask_details=True)
    original = McpError(
        ErrorData(code=-32000, message="Tool 'slow_op' execution timed out after 30s")
    )
    call_next = AsyncMock(side_effect=original)
    with pytest.raises(McpError) as info:
        await mw.on_call_tool(_ctx(), call_next)
    assert info.value is original
    assert info.value.error.code == -32000
    assert "timed out" in info.value.error.message


# ── Resource / Prompt envelopes (manual smoke testing 2026-05-12) ─────


@pytest.mark.asyncio
async def test_resource_domain_error_wrapped_as_resource_error() -> None:
    """Regression: ``on_read_resource`` used to be unimplemented — domain
    ``NotFoundError`` from a resource handler bubbled to the generic
    Exception path and surfaced as ``"internal error: ..."``. Now it
    becomes a ``ResourceError("not found: ...")``.
    """
    mw = DomainErrorMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=NotFoundError("track", 9999))
    with pytest.raises(ResourceError) as info:
        await mw.on_read_resource(_ctx(), call_next)
    assert "not found" in str(info.value).lower()


@pytest.mark.asyncio
async def test_prompt_domain_error_wrapped_as_prompt_error() -> None:
    """Same as the resource case but for the prompt envelope."""
    mw = DomainErrorMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=ValidationError("bad arg"))
    with pytest.raises(PromptError) as info:
        await mw.on_get_prompt(_ctx(), call_next)
    assert "invalid" in str(info.value).lower()


@pytest.mark.asyncio
async def test_fastmcp_native_not_found_wrapped() -> None:
    """Regression: ``fastmcp.exceptions.NotFoundError`` (raised by the
    server when a prompt / resource name is unknown) is a different class
    from ``app.shared.errors.NotFoundError`` — the previous middleware
    didn't catch it, so ``get_prompt('typo')`` returned ``"internal
    error: Unknown prompt: 'typo'"`` instead of a clean ``not found``.
    """
    mw = DomainErrorMiddleware(mask_details=True)
    call_next = AsyncMock(side_effect=FastMCPNotFoundError("Unknown prompt: 'bogus'"))
    with pytest.raises(PromptError) as info:
        await mw.on_get_prompt(_ctx(), call_next)
    assert "not found" in str(info.value).lower()
    assert "bogus" in str(info.value)
