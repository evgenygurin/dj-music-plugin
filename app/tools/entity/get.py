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
from app.shared.errors import NotFoundError, ValidationError
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

    # Validate include_relations against the entity's declared relations
    # map — previously typos were silently ignored (no eager-load, no
    # error), which surprised callers expecting symmetric strictness with
    # ``fields`` (which raises "unknown preset" on typo).
    if include_relations:
        allowed = set(config.relations.keys())
        unknown = [r for r in include_relations if r not in allowed]
        if unknown:
            raise ValidationError(
                f"unknown relation(s) {unknown!r} for entity {entity!r}; "
                f"declared relations: {sorted(allowed) or 'none'}"
            )

    repo = getattr(uow, config.repo_attr)
    row = await repo.get(id)
    if row is None:
        raise NotFoundError(entity, id)

    view = config.view_schema.model_validate(row)
    data = view.model_dump()
    # Audit iter 46 (T-44): some Views declare derived fields
    # (item_count, version_count) the dispatcher cannot read off the
    # ORM row directly. Optional enricher hook fills them in.
    if config.view_enricher is not None:
        data = await config.view_enricher(uow, row, data)
    projection = resolve_field_projection(fields, config)
    if projection is not None:
        data = {k: v for k, v in data.items() if k in projection}
    # Relations attach AFTER projection so ``fields="summary"`` doesn't
    # strip what the caller explicitly asked to include. Prior to v1.6.1
    # the parameter was validated but never loaded — a silent no-op.
    if include_relations:
        for rel in include_relations:
            loader = config.relation_loaders.get(rel)
            if loader is None:
                raise ValidationError(
                    f"relation {rel!r} is declared on entity {entity!r} but has "
                    "no registered loader — registry drift, report a bug"
                )
            data[rel] = await loader(uow, row)
    return EntityGetResult(entity=entity, id=id, data=data)
