"""entity_get — fetch a single entity by primary key."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry, resolve_field_projection
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityGetResult
from app.server.di import get_uow
from app.shared.errors import NotFoundError
from app.shared.types import JsonStrListOrNone

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
    name="entity_get",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Fetch a single entity by ID with optional field projection or relation inclusion."
    ),
    meta={"timeout_s": 30.0},
    timeout=30.0,
)
async def entity_get(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    fields: Annotated[
        list[str] | str | None,
        Field(description="Field list, JSON-encoded list, CSV, or preset name"),
    ] = None,
    include_relations: Annotated[
        JsonStrListOrNone, Field(description="Relations to eager-load")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> EntityGetResult:
    config = EntityRegistry.get(entity)
    if "get" not in config.allowed_ops:
        raise ValueError(f"get not allowed on entity {entity!r}")

    repo = getattr(uow, config.repo_attr)
    row = await repo.get(id)
    if row is None:
        raise NotFoundError(entity, id)

    view = config.view_schema.model_validate(row)
    projection = resolve_field_projection(fields, config)
    data = view.model_dump(include=projection) if projection is not None else view.model_dump()
    return EntityGetResult(entity=entity, id=id, data=data)
