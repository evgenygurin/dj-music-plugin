"""JSON-aware override of FastMCP's ``PromptsAsTools.get_prompt``.

Background
----------
FastMCP's stock ``PromptsAsTools._make_get_prompt_tool`` types the
``arguments`` parameter as ``dict[str, Any] | None`` without a
``BeforeValidator``. Some MCP transports (notably Claude Code's stdio
shim) stringify complex args, sending ``'{"playlist_id": 5}'`` instead
of a native dict. Pydantic then crashes with::

    Input should be a valid dictionary [type=dict_type,
        input_value='{"playlist_id": 5}', input_type=str]

This is the same root cause covered by ``app/shared/types.py:JsonDict``
for our own tools. ``JSONAwareResourcesAsTools`` solved it for the
resource side; this module mirrors the fix for prompts.

Behaviour
---------
``JSONAwarePromptsAsTools`` is drop-in for ``PromptsAsTools`` — it only
overrides ``_make_get_prompt_tool`` so the ``arguments`` parameter
accepts EITHER a native dict OR a JSON-encoded string. ``list_prompts``
is preserved unchanged via ``super()``.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastmcp.server.dependencies import get_context
from fastmcp.server.transforms import PromptsAsTools
from fastmcp.tools.base import Tool
from mcp.types import TextContent

from app.shared.types import JsonDictOrNone


class JSONAwarePromptsAsTools(PromptsAsTools):
    """Same as ``PromptsAsTools`` but ``get_prompt(arguments=...)``
    accepts a JSON-encoded string transparently.
    """

    def _make_get_prompt_tool(self) -> Tool:
        async def get_prompt(
            name: Annotated[str, "The name of the prompt to get"],
            arguments: Annotated[
                JsonDictOrNone,
                "Optional arguments for the prompt (dict or JSON-encoded string)",
            ] = None,
        ) -> str:
            ctx = get_context()
            result = await ctx.fastmcp.render_prompt(name, arguments=arguments or {})
            return _format_prompt_result(result)

        return Tool.from_function(fn=get_prompt)


def _format_prompt_result(result: Any) -> str:
    """Format ``PromptResult`` for tool output (JSON with messages array)."""
    messages = []
    for msg in result.messages:
        if isinstance(msg.content, TextContent):
            content: Any = msg.content.text
        else:
            content = msg.content.model_dump(mode="json", exclude_none=True)
        messages.append({"role": msg.role, "content": content})
    return json.dumps({"messages": messages}, indent=2)
