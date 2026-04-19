"""entity_create — polymorphic create with optional custom handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityCreateResult
from app.server.di import (
    get_audio_pipeline,
    get_provider_registry,
    get_transition_scorer,
    get_uow,
)
from app.shared.types import JsonDict
from app.tools.entity._dispatch import call_handler

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
    name="entity_create",
    tags={"namespace:crud:write", "write"},
    annotations={"readOnlyHint": False, "idempotentHint": False, "openWorldHint": True},
    description=(
        "Create an entity. Some entities have custom handlers with side-effects: "
        "track=import from provider, audio_file=download, track_features=run analysis, "
        "set_version=build + compute transitions."
    ),
)
async def entity_create(
    entity: Annotated[EntityName, Field(description="Entity type")],
    data: Annotated[
        JsonDict,
        Field(description="Payload — shape depends on entity (see schema://entities/{entity})"),
    ],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    pipeline: Any = Depends(get_audio_pipeline),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> EntityCreateResult:
    config = EntityRegistry.get(entity)
    if "create" not in config.allowed_ops:
        raise ValueError(f"create not allowed on {entity!r}")

    if config.create_handler is not None:
        # Dispatch inspects the handler's 4th parameter name and passes the
        # matching service (registry / pipeline / scorer). Previously we
        # always passed the ProviderRegistry, which silently mis-typed the
        # analyze / persist handlers and crashed on their first service call.
        result = await call_handler(
            config.create_handler,
            ctx=ctx,
            uow=uow,
            data=data,
            registry=registry,
            pipeline=pipeline,
            scorer=scorer,
        )
        return EntityCreateResult(entity=entity, data=result, meta={"via": "handler"})

    # Default path: validate + straight insert.
    validated = config.create_schema.model_validate(data)
    repo = getattr(uow, config.repo_attr)
    row = await repo.create(**validated.model_dump())
    view = config.view_schema.model_validate(row).model_dump()
    return EntityCreateResult(entity=entity, data=view, meta={"via": "default"})
