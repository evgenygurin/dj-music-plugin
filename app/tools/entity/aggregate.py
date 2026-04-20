"""entity_aggregate — count / distinct / histogram / min_max / sum / avg."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.registry.entity import EntityRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import AggregateResult
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.shared.filters import normalize_bare_fields
from app.shared.types import JsonDictOrNone

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
    timeout=30.0,
)
async def entity_aggregate(
    entity: Annotated[EntityName, Field(description="Entity type")],
    operation: Annotated[Operation, Field(description="Aggregate function")],
    field: Annotated[
        str | None, Field(description="Required for sum/avg/min_max/histogram")
    ] = None,
    group_by: Annotated[str | None, Field(description="Group column")] = None,
    filters: Annotated[JsonDictOrNone, Field(description="Django-style filters")] = None,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> AggregateResult:
    config = EntityRegistry.get(entity)
    if "aggregate" not in config.allowed_ops:
        raise ValueError(f"aggregate not allowed on {entity!r}")

    # Preserve bare-field equality shorthand — see entity_list for rationale.
    where = normalize_bare_fields(filters or {})

    # Validate filter shape against the entity's Pydantic Filter schema —
    # this is the single source of truth; avoids the registry/schema drift
    # where ``filterable_fields`` was narrower than the Pydantic model.
    try:
        config.filter_schema.model_validate(where)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"invalid filter for entity {entity!r}: {exc.errors(include_url=False)[:3]}",
            details={"entity": entity, "filter": where},
        ) from exc

    repo = getattr(uow, config.repo_attr)
    value = await repo.aggregate(operation=operation, field=field, group_by=group_by, where=where)
    return AggregateResult(
        entity=entity,
        operation=operation,
        field=field,
        group_by=group_by,
        value=value,
    )
