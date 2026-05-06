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
``JSONAwarePromptsAsTools`` is drop-in for ``PromptsAsTools`` with two
deviations:

1. ``arguments`` accepts EITHER a native dict OR a JSON-encoded string
   (``JsonDictOrNone`` BeforeValidator) — fixes Claude Code's
   stringifying stdio shim.
2. ``get_prompt`` returns a native ``dict[str, Any]`` (not
   ``json.dumps``-encoded ``str``) so FastMCP populates
   ``structuredContent`` with the native shape. Clients see
   ``{"messages": [...]}`` directly instead of
   ``{"result": "<escaped JSON>"}``.

``list_prompts`` is preserved unchanged via ``super()``.
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
        ) -> dict[str, Any]:
            ctx = get_context()
            # Audit iter 45 (T-43): the MCP protocol's
            # ``GetPromptRequestParams.arguments`` is typed as
            # ``dict[str, str]`` — every value MUST be a string.
            # Callers that pass natively-typed values
            # (``{"from_track_id": 146}``) used to crash with::
            #
            #   2 validation errors for GetPromptRequestParams
            #   arguments.from_track_id
            #     Input should be a valid string ...
            #
            # The list_prompts description hints at this with
            # "Provide as a JSON string matching the schema integer"
            # but most clients (including Claude Code) pass native
            # ints. Coerce here so the client can pass either form.
            coerced = _stringify_prompt_args(arguments or {})
            result = await ctx.fastmcp.render_prompt(name, arguments=coerced)
            return _format_prompt_result(result)

        return Tool.from_function(fn=get_prompt)


def _stringify_prompt_args(args: dict[str, Any]) -> dict[str, str]:
    """Coerce every value in a prompt-arguments dict to a string.

    The MCP wire format requires ``dict[str, str]``; Pydantic / JSON
    primitives are converted via ``json.dumps`` for non-strings so
    the prompt body, which usually does its own ``json.loads`` /
    casting, sees a stable JSON-serialised form. Strings pass
    through unchanged. None values are dropped (treated as
    not-supplied) — matches MCP semantics.
    """
    out: dict[str, str] = {}
    for k, v in args.items():
        if v is None:
            continue
        if isinstance(v, str):
            out[k] = v
        else:
            out[k] = json.dumps(v)
    return out


def _format_prompt_result(result: Any) -> dict[str, Any]:
    """Format ``PromptResult`` as a native dict ``{"messages": [...]}``.

    Returning a ``dict`` (instead of a ``json.dumps``-encoded string)
    lets FastMCP populate ``structuredContent`` with the native shape,
    so MCP clients see ``{"messages": [...]}`` directly instead of
    ``{"result": "<escaped JSON>"}`` — symmetric with how every other
    v1 dispatcher (e.g. ``entity_list``) returns Pydantic models.
    """
    messages = []
    for msg in result.messages:
        if isinstance(msg.content, TextContent):
            content: Any = msg.content.text
        else:
            content = msg.content.model_dump(mode="json", exclude_none=True)
        messages.append({"role": msg.role, "content": content})
    return {"messages": messages}
