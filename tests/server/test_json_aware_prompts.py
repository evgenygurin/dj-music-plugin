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
