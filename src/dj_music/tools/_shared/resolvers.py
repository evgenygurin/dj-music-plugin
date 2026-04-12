"""Entity resolution for MCP tools.

Centralises the ``(id | query) → entity`` pattern that used to live in
three different helpers (``resolve_entity``, ``resolve_track_id``,
``validate_id_or_query``) with inconsistent behaviour.

Design notes
------------
- Resolution is a **Strategy**: lookup by numeric id takes precedence,
  free-text query is the fallback.
- Failures raise :class:`fastmcp.exceptions.ToolError` directly so that
  tool bodies do not have to translate domain exceptions at every call
  site. The wire message stays stable (``"<entity> not found: <ref>"``,
  ``"provide <entity> id or query"``) so LLM clients receive the same
  text they did before the refactor.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.exceptions import ToolError


def ensure_reference(
    entity_id: int | None,
    query: str | None,
    *,
    entity_name: str = "entity",
) -> None:
    """Validate that at least one reference form was provided.

    Replaces the old ``validate_id_or_query`` helper.
    """
    if entity_id is None and not query:
        raise ToolError(f"Provide {entity_name} id or query")


async def resolve_entity[EntityT](
    *,
    entity_id: int | None,
    query: str | None,
    entity_name: str,
    get_by_id: Callable[[int], Awaitable[EntityT | None]],
    search_by_query: Callable[[str], Awaitable[EntityT | None]],
) -> EntityT:
    """Resolve an entity by numeric id or free-text query.

    Parameters
    ----------
    entity_id:
        Preferred form — numeric primary key.
    query:
        Fallback — free-text that ``search_by_query`` interprets.
    entity_name:
        Human-readable noun used in error messages (``"track"`` /
        ``"playlist"``).
    get_by_id:
        Async callable that returns the entity or ``None``.
    search_by_query:
        Async callable that returns the best match or ``None``.

    Returns
    -------
    EntityT
        The resolved entity (never ``None``).

    Raises
    ------
    ToolError
        If neither reference form was supplied, or if the lookup
        returned ``None``.
    """
    ensure_reference(entity_id, query, entity_name=entity_name)

    entity: EntityT | None
    if entity_id is not None:
        entity = await get_by_id(entity_id)
        reference: Any = entity_id
    else:
        assert query is not None  # ensured by ensure_reference
        entity = await search_by_query(query)
        reference = query

    if entity is None:
        raise ToolError(f"{entity_name} not found: {reference}")

    return entity


async def resolve_track_id(
    *,
    entity_id: int | None,
    query: str | None,
    search: Callable[[str, int], Awaitable[list[Any]]],
) -> int:
    """Resolve a track reference to its numeric id.

    ``search`` is typically ``TrackService.search`` — a callable taking
    ``(query, limit)`` and returning a list of track-like objects that
    expose an ``id`` attribute.
    """
    ensure_reference(entity_id, query, entity_name="track")
    if entity_id is not None:
        return entity_id

    assert query is not None
    results = await search(query, 1)
    if not results:
        raise ToolError(f"track not found: {query}")
    return int(results[0].id)
