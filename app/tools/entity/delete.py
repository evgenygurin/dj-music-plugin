"""entity_delete — polymorphic hard delete."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityDeleteResult
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
    name="entity_delete",
    tags={"namespace:crud:destructive", "write", "destructive"},
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
    },
    description="Delete an entity by ID. Cascades to related rows per FK definitions.",
    meta={"timeout_s": 120.0},
    timeout=120.0,
)
async def entity_delete(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> EntityDeleteResult:
    config = EntityRegistry.get(entity)
    if "delete" not in config.allowed_ops:
        raise ValueError(f"delete not allowed on {entity!r}")

    if config.delete_handler is not None:
        await config.delete_handler(ctx, uow, {"id": id}, registry)
    else:
        repo = getattr(uow, config.repo_attr)
        await repo.delete(id)

    return EntityDeleteResult(entity=entity, id=id, deleted=True)
