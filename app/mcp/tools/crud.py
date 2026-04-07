"""Set CRUD tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling :class:`SetService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool

from app.core.parsing import ensure_dict
from app.mcp.dependencies import get_set_service
from app.mcp.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ensure_reference,
)
from app.services.set_service import SetService


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
async def list_sets(
    template: str | None = None,
    limit: int = 20,
    cursor: str | None = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """List DJ sets with optional template filter and cursor pagination."""
    return await svc.list_sets(template=template, limit=limit, cursor=cursor)


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_READ_ONLY)
async def get_set(
    id: int | None = None,
    query: str | None = None,
    view: str = "summary",
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Get set details by id or query.

    ``view`` ∈ ``{summary, tracks, transitions, full}``.
    """
    ensure_reference(id, query, entity_name="set")
    return await svc.get_set(id=id, query=query, view=view)


@tool(tags={ToolCategory.CORE.value}, annotations=ANNOTATIONS_WRITE)
async def manage_set(
    action: str,
    data: Any = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Manage DJ sets. Actions: ``create``, ``update``, ``delete``,
    ``add_constraint``, ``remove_constraint``, ``add_feedback``.
    """
    return await svc.manage_set(action=action, data=ensure_dict(data))
