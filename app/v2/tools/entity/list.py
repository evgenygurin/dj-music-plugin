"""entity_list — polymorphic list-with-filter tool via EntityRegistry."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityListResult
from app.v2.server.di import get_uow
from app.v2.shared.filters import parse_django_filters

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

    where = parse_django_filters(
        filters or {},
        allowed=config.filterable_fields,
        searchable=config.searchable_fields,
        search=search,
    )
    sort_spec = list(sort) if sort else []
    for s in sort_spec:
        base = s.removesuffix("__desc").removesuffix("__asc")
        if base not in config.sortable_fields:
            raise ValueError(f"cannot sort {entity} by {base!r}")

    preset = fields if isinstance(fields, str) else None
    if preset is not None:
        if preset not in config.field_presets:
            raise ValueError(f"unknown preset {preset!r} for {entity}")
        load_only = config.field_presets[preset]
    else:
        load_only = fields if isinstance(fields, list) else None

    repo = getattr(uow, config.repo_attr)
    page = await repo.filter(
        where=where,
        order=sort_spec,
        limit=limit,
        cursor=cursor,
        load_only=load_only if load_only != "*" else None,
    )

    items = [config.view_schema.model_validate(row).model_dump() for row in page.items]
    total = page.total if with_total else None
    return EntityListResult(entity=entity, items=items, total=total, next_cursor=page.next_cursor)
