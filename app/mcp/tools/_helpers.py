"""Shared helpers for MCP tool implementations."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastmcp.exceptions import ToolError


async def resolve_entity(
    *,
    id: int | None,
    query: str | None,
    entity_name: str = "Entity",
    get_by_id: Callable[..., Coroutine[Any, Any, Any]],
    search_by_query: Callable[..., Coroutine[Any, Any, Any]],
) -> Any:
    """Resolve an entity by ID or text query.

    Args:
        id: Numeric entity ID (preferred).
        query: Text search fallback.
        entity_name: Human-readable name for error messages.
        get_by_id: Async callable(id) -> entity | None.
        search_by_query: Async callable(query) -> entity | None.

    Returns:
        The resolved entity.

    Raises:
        ToolError: If neither id/query provided or entity not found.
    """
    if id is None and query is None:
        raise ToolError(f"Provide {entity_name.lower()} id or query")

    if id is not None:
        entity = await get_by_id(id)
    else:
        entity = await search_by_query(query)

    if entity is None:
        raise ToolError(f"{entity_name} not found: {id or query}")

    return entity


async def resolve_track_id(
    *,
    id: int | None,
    query: str | None,
    svc: Any,
) -> int:
    """Resolve a track to its ID by id or query.

    Uses TrackService.search() for query resolution.

    Returns:
        The track ID (int).

    Raises:
        ToolError: If neither provided or track not found.
    """
    if id is None and query is None:
        raise ToolError("Provide track id or query")

    if id is not None:
        return id

    results = await svc.search(query, limit=1)
    if not results:
        raise ToolError(f"Track not found: {query}")
    return results[0].id


def validate_id_or_query(
    id: int | None,
    query: str | None,
    entity_name: str = "entity",
) -> None:
    """Validate that at least one of id or query is provided.

    Raises:
        ToolError: If neither id nor query is provided.
    """
    if id is None and query is None:
        raise ToolError(f"Provide {entity_name} id or query")
