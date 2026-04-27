"""Regression tests for ``JSONAwarePromptsAsTools``.

The stock FastMCP ``PromptsAsTools._make_get_prompt_tool`` types
``arguments`` as ``dict[str, Any] | None`` without any
``BeforeValidator``. Some MCP transports (Claude Code's stdio shim, in
particular) stringify complex args, sending ``'{"a": 1}'`` instead of a
native dict. Pydantic then crashes with ``Input should be a valid
dictionary [type=dict_type]``. Our override accepts EITHER form
transparently via ``app/shared/types.py:JsonDictOrNone``.
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client, FastMCP

from app.server.json_aware_prompts import JSONAwarePromptsAsTools


def _make_server() -> FastMCP:
    mcp = FastMCP("test-json-aware-prompts")

    @mcp.prompt
    def echo_prompt(name: str, count: str = "1") -> str:
        return f"hi {name} x{count}"

    mcp.add_transform(JSONAwarePromptsAsTools(mcp))
    return mcp


@pytest.mark.asyncio
async def test_get_prompt_accepts_native_dict() -> None:
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt",
            {"name": "echo_prompt", "arguments": {"name": "world", "count": "3"}},
        )
        payload = json.loads(result.data)
        assert "hi world x3" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_get_prompt_accepts_json_string() -> None:
    """Regression: stringified-args transport (Claude Code stdio shim).

    Previously raised ``Input should be a valid dictionary
    [type=dict_type]`` because the stock ``PromptsAsTools.get_prompt``
    accepted only native dicts.
    """
    mcp = _make_server()
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt",
            {
                "name": "echo_prompt",
                "arguments": '{"name": "stringified", "count": "7"}',
            },
        )
        payload = json.loads(result.data)
        assert "hi stringified x7" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_get_prompt_accepts_omitted_arguments_for_no_arg_prompt() -> None:
    """A prompt without arguments should render with no ``arguments`` field."""
    mcp = FastMCP("test-no-arg-prompt")

    @mcp.prompt
    def no_args_prompt() -> str:
        return "static body"

    mcp.add_transform(JSONAwarePromptsAsTools(mcp))

    async with Client(mcp) as client:
        result = await client.call_tool("get_prompt", {"name": "no_args_prompt"})
        payload = json.loads(result.data)
        assert "static body" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_get_prompt_accepts_native_int_values() -> None:
    """Audit iter 45 (T-43): MCP wire format requires
    ``dict[str, str]`` arguments. Native int / float / bool values
    used to crash with::

        2 validation errors for GetPromptRequestParams
        arguments.from_track_id
          Input should be a valid string

    The override now coerces every value to a string before passing
    it to ``render_prompt``.
    """
    mcp = FastMCP("test-int-coerce")

    @mcp.prompt
    def with_int_arg(track_id: str, count: str = "1") -> str:
        # Prompt body sees stringified values per MCP spec.
        return f"track={track_id} count={count}"

    mcp.add_transform(JSONAwarePromptsAsTools(mcp))

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt",
            {"name": "with_int_arg", "arguments": {"track_id": 146, "count": 5}},
        )
        payload = json.loads(result.data)
        # Both ints survived as-is on the way through (json.dumps(146) == "146").
        assert "track=146 count=5" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_get_prompt_drops_none_values() -> None:
    """``None`` is treated as not-supplied — MCP spec semantics."""
    mcp = FastMCP("test-none-arg")

    @mcp.prompt
    def with_optional(name: str, optional: str = "default") -> str:
        return f"name={name} optional={optional}"

    mcp.add_transform(JSONAwarePromptsAsTools(mcp))

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt",
            {"name": "with_optional", "arguments": {"name": "x", "optional": None}},
        )
        payload = json.loads(result.data)
        # ``optional`` was None → dropped → default applied.
        assert "name=x optional=default" in payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_get_prompt_accepts_native_bool_values() -> None:
    """Booleans coerce to ``"true"`` / ``"false"`` (json.dumps form)."""
    mcp = FastMCP("test-bool-arg")

    @mcp.prompt
    def with_bool(flag: str) -> str:
        return f"flag={flag}"

    mcp.add_transform(JSONAwarePromptsAsTools(mcp))

    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_prompt",
            {"name": "with_bool", "arguments": {"flag": True}},
        )
        payload = json.loads(result.data)
        assert "flag=true" in payload["messages"][0]["content"]
