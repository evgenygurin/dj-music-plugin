"""entity_aggregate — count / distinct / histogram / min_max / sum / avg."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.registry.entity import EntityRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import AggregateResult
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
Operation = Literal["count", "distinct", "histogram", "min_max", "sum", "avg"]


@tool(
    name="entity_aggregate",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "Compute summary statistics: count, distinct, histogram, min_max, sum, avg. "
        "Optional group_by + filters. Use for dashboards without fetching rows."
    ),
)
async def entity_aggregate(
    entity: Annotated[EntityName, Field(description="Entity type")],
    operation: Annotated[Operation, Field(description="Aggregate function")],
    field: Annotated[
        str | None, Field(description="Required for sum/avg/min_max/histogram")
    ] = None,
    group_by: Annotated[str | None, Field(description="Group column")] = None,
    filters: Annotated[dict[str, Any] | None, Field(description="Django-style filters")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> AggregateResult:
    config = EntityRegistry.get(entity)
    if "aggregate" not in config.allowed_ops:
        raise ValueError(f"aggregate not allowed on {entity!r}")

    where = parse_django_filters(
        filters or {},
        allowed=config.filterable_fields,
        searchable=config.searchable_fields,
        search=None,
    )

    repo = getattr(uow, config.repo_attr)
    value = await repo.aggregate(operation=operation, field=field, group_by=group_by, where=where)
    return AggregateResult(
        entity=entity,
        operation=operation,
        field=field,
        group_by=group_by,
        value=value,
    )
