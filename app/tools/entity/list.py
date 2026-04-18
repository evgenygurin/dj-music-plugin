"""entity_list — polymorphic list-with-filter tool via EntityRegistry."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityListResult
from app.server.di import get_uow
from app.shared.filters import parse_django_filters

EntityName = Literal[
    "track",
    "playlist",
    "set",
    "set_version",
    "audio_file",
    "track_features",
    "transition",
    "transition_history",
    "track_feedback",
    "track_affinity",
    "scoring_profile",
]


@tool(
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, and "
        "field projection. Use schema://entities/{entity} to discover available "
        "filters/presets."
    ),
)
async def entity_list(
    entity: Annotated[EntityName, Field(description="Entity type name")],
    filters: Annotated[
        dict[str, Any] | None,
        Field(description='Django-style: {"bpm__gte": 120, "mood__in": ["peak_time"]}'),
    ] = None,
    search: Annotated[
        str | None, Field(description="Free-text search over searchable_fields")
    ] = None,
    fields: Annotated[
        list[str] | str | None,
        Field(description='Field list or preset name: "id" | "ref" | "summary" | "full"'),
    ] = None,
    sort: Annotated[list[str] | None, Field(description="e.g. ['bpm__desc', 'id']")] = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 50,
    cursor: str | None = None,
    with_total: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> EntityListResult:
    config = EntityRegistry.get(entity)
    if "list" not in config.allowed_ops:
        raise ValueError(f"list not allowed on entity {entity!r}")

    where = dict(filters or {})
    if search and config.searchable_fields:
        # Simple search: icontains over the first searchable field.
        where[f"{config.searchable_fields[0]}__icontains"] = search
    # Validate fields against whitelist via parse_django_filters.
    parse_django_filters(
        config.model,
        where,
        allowed_fields=set(config.filterable_fields) | set(config.searchable_fields),
    )
    sort_spec: list[str] = []
    for s in list(sort or []):
        base = s.removesuffix("__desc").removesuffix("__asc")
        if base not in config.sortable_fields:
            raise ValueError(f"cannot sort {entity} by {base!r}")
        # Normalize __desc/__asc to BaseRepository.filter's _desc/_asc.
        if s.endswith("__desc"):
            sort_spec.append(f"{base}_desc")
        elif s.endswith("__asc"):
            sort_spec.append(f"{base}_asc")
        else:
            sort_spec.append(s)

    repo = getattr(uow, config.repo_attr)
    page = await repo.filter(
        where=where,
        order=sort_spec,
        limit=limit,
        cursor=cursor,
        with_total=with_total,
    )

    items = [config.view_schema.model_validate(row).model_dump() for row in page.items]
    total = page.total if with_total else None
    return EntityListResult(entity=entity, items=items, total=total, next_cursor=page.next_cursor)
