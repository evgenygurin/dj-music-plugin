"""Set CRUD tools — list, get, manage (3 tools, tag: core).

Thin wrappers calling :class:`SetService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_set_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    ensure_reference,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_dict
from app.services.set.facade import SetService

SetManageAction = Literal[
    "create", "update", "delete", "add_constraint", "remove_constraint", "add_feedback"
]
SetView = Literal["summary", "tracks", "transitions", "full"]


@tool(
    title="List Sets",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def list_sets(
    template: Annotated[str | None, Field(description="Filter sets by template name")] = None,
    limit: Annotated[int, Field(description="Page size", ge=1)] = 20,
    cursor: Annotated[
        str | None, Field(description="Pagination cursor from previous page")
    ] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Lists DJ sets with optional template filter and cursor pagination. Use when browsing the set catalog or fetching the next page of results."""
    return await svc.list_sets(template=template, limit=limit, cursor=cursor)


@tool(
    title="Get Set",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_set(
    id: Annotated[int | None, Field(description="Local set ID")] = None,
    query: Annotated[str | None, Field(description="Text query to resolve a set")] = None,
    view: Annotated[SetView, Field(description="Detail level")] = "summary",
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Returns one DJ set by local id or text query at the requested detail level. Use when inspecting a set before editing, exporting, or comparing versions."""
    ensure_reference(id, query, entity_name="set")
    return await svc.get_set(id=id, query=query, view=view)


@tool(
    title="Manage Set",
    tags={ToolCategory.CORE.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def manage_set(
    action: Annotated[SetManageAction, Field(description="Operation to perform")],
    data: Annotated[Any, Field(description="Action-specific payload dict")] = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
) -> dict[str, Any]:
    """Applies create, update, delete, constraint, or feedback changes to a set via one action and payload. Use when mutating set metadata or structure rather than read-only inspection."""
    return await svc.manage_set(action=action, data=ensure_dict(data))
