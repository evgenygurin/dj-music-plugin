"""Unit tests for domain-error → FastMCP-native error mapping.

Mapping contract (see ``app/controllers/tools/_shared/errors.py`` module docstring):

| Domain error        | Raised as                            | MCP code            |
|---------------------|--------------------------------------|---------------------|
| ``NotFoundError``   | ``fastmcp.exceptions.NotFoundError`` | -32001 Not found    |
| ``ValidationError`` | ``ValueError``                       | -32602 Invalid params |
| ``ConflictError``   | ``ToolError`` (Conflict: …)          | -32603 Internal error |
"""

from __future__ import annotations

import pytest
from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
from fastmcp.exceptions import ToolError

from dj_music.tools._shared.errors import (
    domain_errors_as_tool_error,
    map_domain_errors,
)
from dj_music.core.errors import ConflictError, NotFoundError, ValidationError


async def test_not_found_mapped_to_fastmcp_not_found() -> None:
    @map_domain_errors
    async def _tool() -> None:
        raise NotFoundError("Track", 42)

    with pytest.raises(FastMCPNotFoundError, match="Track not found: 42"):
        await _tool()


async def test_validation_error_mapped_to_value_error() -> None:
    @map_domain_errors
    async def _tool() -> None:
        raise ValidationError("bpm out of range", field="bpm", value=500)

    with pytest.raises(ValueError, match="bpm out of range"):
        await _tool()


async def test_conflict_error_mapped_to_tool_error() -> None:
    @map_domain_errors
    async def _tool() -> None:
        raise ConflictError("duplicate playlist name")

    with pytest.raises(ToolError, match="Conflict: duplicate playlist name"):
        await _tool()


async def test_tool_error_passes_through_unchanged() -> None:
    sentinel = ToolError("explicit tool failure")

    @map_domain_errors
    async def _tool() -> None:
        raise sentinel

    with pytest.raises(ToolError) as exc_info:
        await _tool()
    assert exc_info.value is sentinel


async def test_other_exceptions_not_caught() -> None:
    @map_domain_errors
    async def _tool() -> None:
        raise RuntimeError("unrelated")

    with pytest.raises(RuntimeError, match="unrelated"):
        await _tool()


async def test_preserves_return_value() -> None:
    @map_domain_errors
    async def _tool(x: int) -> int:
        return x * 2

    assert await _tool(5) == 10


async def test_preserves_function_metadata() -> None:
    @map_domain_errors
    async def my_tool(x: int) -> int:
        """Docstring preserved."""
        return x

    assert my_tool.__name__ == "my_tool"
    assert my_tool.__doc__ == "Docstring preserved."


async def test_context_manager_form() -> None:
    async with domain_errors_as_tool_error():
        pass  # no raise

    with pytest.raises(FastMCPNotFoundError, match="Set not found: 7"):
        async with domain_errors_as_tool_error():
            raise NotFoundError("Set", 7)
