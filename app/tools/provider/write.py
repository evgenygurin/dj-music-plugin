"""provider_write — generic mutation against any registered provider."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.provider import ProviderRegistry
from app.schemas.provider_dto import ProviderWriteResult
from app.server.di import get_provider_registry
from app.shared.types import JsonDict


@tool(
    name="provider_write",
    tags={"namespace:provider:write", "write"},
    annotations={"readOnlyHint": False, "openWorldHint": True, "idempotentHint": False},
    description=(
        "Mutate external platform. entity=playlist|likes|generation. operation=add_tracks|"
        "remove_tracks|create|rename|delete|add|remove|cancel|download."
    ),
    meta={"timeout_s": 120.0},
    timeout=120.0,
)
async def provider_write(
    provider: Annotated[str, Field(description="Provider name")],
    entity: Annotated[str, Field(description="Provider entity type")],
    operation: Annotated[str, Field(description="Operation verb")],
    params: Annotated[JsonDict, Field(description="Operation payload (shape depends on op)")],
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> ProviderWriteResult:
    adapter = registry.get(provider)
    data = await adapter.write(entity, operation=operation, params=params)
    return ProviderWriteResult(provider=provider, entity=entity, operation=operation, data=data)
