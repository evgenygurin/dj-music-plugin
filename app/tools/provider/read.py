"""provider_read — generic GET against any registered provider."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.provider import ProviderRegistry
from app.schemas.provider_dto import ProviderReadResult
from app.server.di import get_provider_registry
from app.shared.types import JsonDictOrNone


@tool(
    name="provider_read",
    tags={"namespace:provider:read", "read"},
    annotations={"readOnlyHint": True, "openWorldHint": True, "idempotentHint": True},
    description=(
        "Read from external music platform. entity=track|album|playlist|artist_tracks|"
        "track_similar|track_batch|likes|dislikes|playlist_list."
    ),
)
async def provider_read(
    provider: Annotated[str, Field(description="Provider name (e.g., 'yandex')")],
    entity: Annotated[str, Field(description="Provider entity type")],
    id: Annotated[str | None, Field(description="Entity ID (optional for list ops)")] = None,
    params: Annotated[
        JsonDictOrNone, Field(description="Extra params (offset, limit, etc.)")
    ] = None,
    registry: ProviderRegistry = Depends(get_provider_registry),
    ctx: Context = CurrentContext(),
) -> ProviderReadResult:
    adapter = registry.get(provider)
    data = await adapter.read(entity, id=id, params=params or {})
    return ProviderReadResult(provider=provider, entity=entity, data=data)
