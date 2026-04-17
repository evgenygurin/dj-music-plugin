"""entity_get — fetch a single entity by primary key."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.v2.registry.entity import EntityRegistry
from app.v2.repositories.unit_of_work import UnitOfWork
from app.v2.schemas.tool_responses import EntityGetResult
from app.v2.server.di import get_uow
from app.v2.shared.errors import NotFoundError

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
)
async def entity_get(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    fields: Annotated[
        list[str] | str | None,
        Field(description="Field list or preset name"),
    ] = None,
    include_relations: Annotated[
        list[str] | None, Field(description="Relations to eager-load")
    ] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),  # noqa: B008
) -> EntityGetResult:
    config = EntityRegistry.get(entity)
    if "get" not in config.allowed_ops:
        raise ValueError(f"get not allowed on entity {entity!r}")

    repo = getattr(uow, config.repo_attr)

    load_only: list[str] | None = None
    if isinstance(fields, str):
        if fields not in config.field_presets:
            raise ValueError(f"unknown preset {fields!r}")
        preset = config.field_presets[fields]
        load_only = list(preset) if preset != "*" else None
    elif isinstance(fields, list):
        load_only = fields

    row = await repo.get(id, load_only=load_only)
    if row is None:
        raise NotFoundError(entity, id)

    data = config.view_schema.model_validate(row).model_dump()
    return EntityGetResult(entity=entity, id=id, data=data)
