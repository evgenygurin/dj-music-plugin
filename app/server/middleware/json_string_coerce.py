"""Server-side coercion of stringified array/object tool args.

Some MCP transports (notably Claude Code's stdio shim) JSON-stringify
``list``/``dict`` arguments before sending. Per-param ``BeforeValidator``
helpers (``app/shared/types.py:JsonIntList`` / ``JsonStrListOrNone`` /
``JsonDictOrNone``) already solve this on a tool-by-tool basis but
require explicit opt-in; any new tool with ``Annotated[list[int], ...]``
or ``Annotated[dict[str, Any], ...]`` is broken on the Claude Code
transport unless the author remembered the helper.

This middleware is the opt-out variant: any tool whose ``inputSchema``
declares an arg as ``type: array`` or ``type: object`` (including via
``anyOf``) will have a stringified payload parsed back to a native
dict/list before Pydantic validation runs. Existing tools keep their
``Json*`` helpers as belt-and-suspenders - coercing twice is idempotent.

Closes the v1.0.10-v1.0.13 bug class at the architecture level.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from mcp.types import CallToolRequestParams


def _arg_expects_complex(schema: dict[str, Any] | None) -> bool:
    """True if the parameter schema accepts ``array`` or ``object``."""
    if not isinstance(schema, dict):
        return False
    t = schema.get("type")
    if t in {"array", "object"}:
        return True
    for branch_key in ("anyOf", "oneOf", "allOf"):
        branches = schema.get(branch_key)
        if isinstance(branches, list):
            for b in branches:
                if _arg_expects_complex(b):
                    return True
    return False


def _coerce_args_against_schema(
    args: dict[str, Any], input_schema: dict[str, Any] | None
) -> dict[str, Any]:
    """Parse JSON-encoded strings for args whose schema expects array/object.

    - Native types pass through unchanged.
    - String args whose schema expects ``string`` are left alone (even if
      they happen to look like JSON).
    - Strings that don't start with ``[``/``{`` are left alone - avoids
      misinterpreting bare values like ``"7B"`` (Camelot) as JSON.
    - Invalid JSON is left as-is so Pydantic produces the clean error
      message instead of the middleware swallowing it.
    """
    if not isinstance(input_schema, dict):
        return args
    props = input_schema.get("properties")
    if not isinstance(props, dict):
        return args

    out = dict(args)
    for name, prop_schema in props.items():
        if name not in out:
            continue
        value = out[name]
        if not isinstance(value, str):
            continue
        if not _arg_expects_complex(prop_schema):
            continue
        s = value.strip()
        if not s or not (s.startswith("[") or s.startswith("{")):
            continue
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list | dict):
            out[name] = parsed
    return out


class JsonStringCoerceMiddleware(Middleware):
    """Coerces stringified array/object args at the MCP boundary.

    Runs at the outermost layer of the call_tool chain so every other
    middleware (audit log, response cache, DB session, …) sees already
    coerced args. Idempotent on native types - passes them through.
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        params = context.message
        if not isinstance(params.arguments, dict):
            return await call_next(context)

        # Look up the tool to read its input schema. ``fastmcp_context``
        # is None for non-server contexts (smoke tests); skip in that case.
        fmcp_ctx = context.fastmcp_context
        if fmcp_ctx is None:
            return await call_next(context)

        try:
            tool = await fmcp_ctx.fastmcp.get_tool(params.name)
        except Exception:
            tool = None
        if tool is None:
            return await call_next(context)

        input_schema = getattr(tool, "parameters", None)
        if isinstance(input_schema, dict):
            params.arguments = _coerce_args_against_schema(params.arguments, input_schema)
        return await call_next(context)
