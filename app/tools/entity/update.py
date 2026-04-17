"""entity_update — polymorphic partial update with optional handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityUpdateResult
from app.server.di import get_provider_registry, get_uow

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
    name="entity_update",
    tags={"namespace:crud:destructive", "write"},
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    },
    description=(
        "Update an entity. Track_features has a reanalyze handler that re-runs "
        "the audio pipeline at a higher level."
    ),
)
async def entity_update(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    data: Annotated[dict[str, Any], Field(description="Partial update payload")],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> EntityUpdateResult:
    config = EntityRegistry.get(entity)
    if "update" not in config.allowed_ops:
        raise ValueError(f"update not allowed on {entity!r}")

    if config.update_handler is not None:
        merged = {**data, "id": id}
        result = await config.update_handler(ctx, uow, merged, registry)  # type: ignore[misc]
        return EntityUpdateResult(entity=entity, id=id, data=result)

    validated = config.update_schema.model_validate(data)
    repo = getattr(uow, config.repo_attr)
    row = await repo.update(id, **validated.model_dump(exclude_unset=True))
    view = config.view_schema.model_validate(row).model_dump()
    return EntityUpdateResult(entity=entity, id=id, data=view)
