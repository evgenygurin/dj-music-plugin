"""unlock_namespace — per-session namespace activation."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.schemas.tool_responses import UnlockNamespaceResult

NAMESPACES = frozenset(
    {
        "crud:destructive",
        "provider:write",
        "sync",
        "all",
    }
)

NAMESPACE_TAGS = {
    "crud:destructive": ["namespace:crud:destructive"],
    "provider:write": ["namespace:provider:write"],
    "sync": ["namespace:sync"],
    "all": [
        "namespace:crud:destructive",
        "namespace:provider:write",
        "namespace:sync",
    ],
}


@tool(
    name="unlock_namespace",
    tags={"namespace:admin", "admin"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
    description=(
        "Per-session activation of hidden tool namespaces. "
        "Namespaces: crud:destructive, provider:write, sync, or 'all'."
    ),
)
async def unlock_namespace(
    namespace: Annotated[
        Literal["crud:destructive", "provider:write", "sync", "all"],
        Field(description="Namespace to toggle"),
    ],
    action: Annotated[
        Literal["unlock", "lock", "status"], Field(description="What to do")
    ] = "status",
    ctx: Context = CurrentContext(),  # noqa: B008
) -> UnlockNamespaceResult:
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown namespace: {namespace}")

    tags_for_ns = set(NAMESPACE_TAGS[namespace])

    if action == "unlock":
        ctx.enable_components(tags=tags_for_ns)
    elif action == "lock":
        ctx.disable_components(tags=tags_for_ns)

    enabled_tools: list[str] = []
    try:
        tools = await ctx.list_tools()
        for t in tools:
            tag_set = set(getattr(t, "tags", ()) or ())
            if tag_set & tags_for_ns:
                enabled_tools.append(t.name)
    except Exception:
        pass

    return UnlockNamespaceResult(namespace=namespace, status=action, enabled_tools=enabled_tools)
