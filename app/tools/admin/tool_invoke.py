"""tool_invoke — dispatcher that calls any other tool by name.

Exists as an escape hatch for clients that cache the tool list on
startup (e.g. Claude Code): even when a previously-hidden tool becomes
visible mid-session, the client will not see it until the next full
list_tools sync. ``tool_invoke`` stays visible at all times, so the
client can always reach any backend tool via this indirection.

Returns whatever the target tool returns. ``arguments`` is a
``JsonDict`` — it accepts both a native dict and a JSON string, since
some transports (Claude Code) wire dict params as strings.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.shared.types import JsonDictOrNone


@tool(
    name="tool_invoke",
    tags={"namespace:admin"},
    annotations={"readOnlyHint": False, "openWorldHint": True, "idempotentHint": False},
    description=(
        "Invoke another tool by name. Use when the host client has an outdated "
        "tool list (e.g. after unlock_namespace) and cannot address the tool "
        "directly."
    ),
    timeout=30.0,
)
async def tool_invoke(
    name: Annotated[str, Field(description="Target tool name, e.g. 'provider_write'")],
    arguments: Annotated[
        JsonDictOrNone, Field(description="Keyword arguments passed to the target tool")
    ] = None,
    ctx: Context = CurrentContext(),
) -> dict[str, Any]:
    # Block self-dispatch: recursive tool_invoke → tool_invoke would spin
    # until stack exhaustion / tool timeout, a trivial DoS for one worker.
    if name == "tool_invoke":
        raise ValueError("tool_invoke cannot dispatch to itself")

    server = getattr(ctx, "fastmcp", None) or ctx.fastmcp_context.fastmcp
    tool_obj = await server.get_tool(name)
    if tool_obj is None:
        raise ValueError(f"tool {name!r} is not registered")
    result = await tool_obj.run(arguments or {})
    # Return the raw structured payload so the caller sees the same shape
    # as a direct call.
    payload: Any = getattr(result, "structured_content", None)
    if payload is None:
        payload = getattr(result, "data", None)
    if payload is None:
        payload = getattr(result, "content", None)
    return {"tool": name, "data": payload}
