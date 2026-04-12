"""Custom `run_tool` proxy that accepts `arguments` as dict OR JSON string.

FastMCP's built-in `BM25SearchTransform.call_tool` declares `arguments`
as `dict[str, Any] | None`. Some MCP clients (including Claude Code's
plugin harness) serialize the parameter to a JSON *string* before handing
it to the server, which then trips pydantic validation with:

    Input should be a valid dictionary [type=dict_type, input_value='{}', input_type=str]

This file replaces that proxy with a version that:

1. Accepts `arguments` as ``dict | str | None`` and parses JSON strings.
2. Advertises concrete ``examples`` in the JSON Schema so clients render a
   real call payload (e.g. ``{"limit": 10}``) instead of the Swagger
   placeholder ``{"additionalProp1": "string"}``.
3. Rejects calls to the search/proxy tools themselves, matching the
   upstream safety check.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from fastmcp.tools.tool import ToolResult
from pydantic import Field

from dj_music.tools._shared import ANNOTATIONS_WRITE, ToolCategory

# Names that must never be invoked through the proxy (they are the proxy
# itself or the companion search tool).
_FORBIDDEN_TARGETS: frozenset[str] = frozenset({"run_tool", "search_tools"})


@tool(
    name="run_tool",
    tags={ToolCategory.ADMIN.value},
    annotations=ANNOTATIONS_WRITE,
)
async def run_tool(
    name: Annotated[
        str,
        Field(
            description="Name of the tool to invoke (e.g. 'list_tracks').",
            examples=["list_tracks", "get_library_stats", "search"],
        ),
    ],
    arguments: Annotated[
        dict[str, Any] | str | None,
        Field(
            default=None,
            description=(
                "Arguments for the tool. Either a JSON object "
                "(preferred) or a JSON string; pass null or {} when "
                "the tool takes no parameters."
            ),
            examples=[
                {"limit": 10},
                {},
                {"query": "techno", "entity": "tracks", "limit": 5},
                {"id": 146},
            ],
        ),
    ] = None,
    ctx: Context = None,  # type: ignore[assignment]
) -> ToolResult:
    """Call a registered MCP tool by name.

    Use this to execute tools discovered via ``search_tools`` or when a
    client cannot reach a tool by its direct namespaced name.
    """
    if name in _FORBIDDEN_TARGETS:
        raise ToolError(f"'{name}' is a synthetic proxy and cannot be called via run_tool")

    parsed: dict[str, Any]
    if arguments is None:
        parsed = {}
    elif isinstance(arguments, str):
        stripped = arguments.strip()
        if not stripped:
            parsed = {}
        else:
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ToolError(
                    f"arguments must be valid JSON object when passed as string: {exc}"
                ) from exc
            if not isinstance(decoded, dict):
                raise ToolError(
                    f"arguments JSON must decode to an object, got {type(decoded).__name__}"
                )
            parsed = decoded
    elif isinstance(arguments, dict):
        parsed = arguments
    else:
        raise ToolError(
            "arguments must be a JSON object, JSON string, or null; "
            f"got {type(arguments).__name__}"
        )

    if ctx is None:
        raise ToolError("run_tool requires an active MCP context")

    # CRITICAL: pass ``run_middleware=False`` to the inner ``call_tool``.
    #
    # When middleware runs on the *inner* call, ``ErrorHandlingMiddleware``
    # transforms any tool error into an ``McpError`` (e.g. -32001 for
    # NotFound). ``McpError`` is NOT a subclass of ``FastMCPError``, so
    # the *outer* ``_call_tool('run_tool', ...)`` then catches it via
    # the bare ``except Exception`` branch and wraps it as
    # ``ToolError("Error calling tool 'run_tool'")``. The outer
    # middleware then re-maps that as a generic ``-32603 Internal error``
    # and the original error code + message are lost forever.
    #
    # Disabling middleware on the inner call keeps the exception in its
    # native FastMCP form (``FastMCPError`` subclass — including the
    # ``ToolError`` wrapper that masking adds, with ``__cause__`` pointing
    # at the real ``NotFoundError``). The outer ``_call_tool``'s
    # ``except FastMCPError: raise`` then passes it through unchanged,
    # and the *single* outer middleware run maps it via the ``__cause__``
    # chain to the correct MCP error code.
    from fastmcp.exceptions import FastMCPError
    from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError

    clean_exc: tuple[type[BaseException], ...] = (
        FastMCPError,
        FastMCPNotFoundError,
        FileNotFoundError,
        KeyError,
        ValueError,
        TypeError,
        PermissionError,
        TimeoutError,
    )

    try:
        return await ctx.fastmcp.call_tool(name, parsed, run_middleware=False)
    except clean_exc:
        raise
    except Exception as exc:
        message = str(exc)
        while message.startswith("Internal error: "):
            message = message[len("Internal error: ") :]
        raise ToolError(f"{name}: {message}") from exc
