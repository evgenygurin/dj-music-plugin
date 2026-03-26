"""Set CRUD tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling SetService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool

from app.mcp.dependencies import get_set_service
from app.services.set_service import SetService

# ── 7. list_sets ────────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_sets(
    template: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """List DJ sets with optional template filter and cursor pagination."""
    return await svc.list_sets(template=template, limit=limit, cursor=cursor)


# ── 8. get_set ──────────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_set(
    id: int | None = None,
    query: str | None = None,
    view: str = "summary",
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Get set details by id or query. view: summary|tracks|transitions|full."""
    if id is None and query is None:
        raise ToolError("Provide set id or query")
    return await svc.get_set(id=id, query=query, view=view)


# ── 9. manage_set ───────────────────────────────────


@tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_set(
    action: str,
    data: Any = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Manage DJ sets. Actions: create, update, delete, add/remove constraint, add feedback."""
    from app.core.parsing import ensure_dict

    data = ensure_dict(data)
    return await svc.manage_set(action=action, data=data)
