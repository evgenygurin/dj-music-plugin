"""entity_list — polymorphic list-with-filter tool via EntityRegistry."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.registry.entity import EntityRegistry, resolve_field_projection
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityListResult
from app.server.di import get_uow
from app.shared.errors import ValidationError
from app.shared.filters import normalize_bare_fields
from app.shared.types import JsonDictOrNone, JsonStrListOrNone

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
    name="entity_list",
    tags={"namespace:crud:read", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": True},
    description=(
        "List entities of a given type with filtering, sorting, pagination, and "
        "field projection. Use schema://entities/{entity} to discover available "
        "filters/presets."
    ),
    meta={"timeout_s": 30.0},
    timeout=30.0,
)
async def entity_list(
    entity: Annotated[EntityName, Field(description="Entity type name")],
    filters: Annotated[
        JsonDictOrNone,
        Field(description='Django-style: {"bpm__gte": 120, "mood__in": ["peak_time"]}'),
    ] = None,
    search: Annotated[
        str | None, Field(description="Free-text search over searchable_fields")
    ] = None,
    fields: Annotated[
        list[str] | str | None,
        Field(
            description=(
                "Field list (native, JSON-encoded, or CSV) or preset name: "
                '"id" | "ref" | "summary" | "full". '
                "Defaults to the entity's default_preset."
            )
        ),
    ] = None,
    sort: Annotated[JsonStrListOrNone, Field(description="e.g. ['bpm__desc', 'id']")] = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 50,
    cursor: str | None = None,
    with_total: bool = False,
    uow: UnitOfWork = Depends(get_uow),
    ctx: Context = CurrentContext(),
) -> EntityListResult:
    config = EntityRegistry.get(entity)
    if "list" not in config.allowed_ops:
        raise ValueError(f"list not allowed on entity {entity!r}")

    where = dict(filters or {})
    if search:
        if not config.searchable_fields:
            # Reject rather than silently ignore the term — the caller
            # believes they filtered but would get the full list back
            # (false contract, probe 2026-07-03).
            raise ValidationError(
                f"entity {entity!r} does not support free-text search "
                f"(no searchable fields); use `filters=` with a lookup instead"
            )
        # Simple search: icontains over the first searchable field.
        where[f"{config.searchable_fields[0]}__icontains"] = search

    # Preserve bare-field equality shorthand (``{"id": 1}`` → ``{"id__eq": 1}``)
    # so Pydantic filter-schema validation matches what parse_filter used to
    # accept via split_lookup. Without this step callers using the old
    # shorthand get a hard ValidationError.
    where = normalize_bare_fields(where)

    # Validate filter shape against the entity's Pydantic Filter schema —
    # this is the single source of truth surfaced via schema://entities/{entity}.
    # Extra keys fail ``extra="forbid"``; unknown operators fail at type coercion.
    # The raw ``where`` dict continues to the repository, which maps keys onto
    # SQLAlchemy columns via ``parse_django_filters``.
    try:
        config.filter_schema.model_validate(where)
    except PydanticValidationError as exc:
        raise ValidationError(
            f"invalid filter for entity {entity!r}: {exc.errors(include_url=False)[:3]}",
            details={"entity": entity, "filter": where},
        ) from exc

    sort_spec: list[str] = []
    for s in list(sort or []):
        base = s.removesuffix("__desc").removesuffix("__asc")
        if base not in config.sortable_fields:
            raise ValueError(f"cannot sort {entity} by {base!r}")
        # Normalize __desc/__asc to BaseRepository.filter's _desc/_asc.
        if s.endswith("__desc"):
            sort_spec.append(f"{base}_desc")
        elif s.endswith("__asc"):
            sort_spec.append(f"{base}_asc")
        else:
            sort_spec.append(s)

    repo = getattr(uow, config.repo_attr)
    page = await repo.filter(
        where=where,
        order=sort_spec,
        limit=limit,
        cursor=cursor,
        with_total=with_total,
    )

    projection = resolve_field_projection(fields, config)
    rows = list(page.items)
    items: list[dict] = []  # type: ignore[type-arg]
    for row in rows:
        view = config.view_schema.model_validate(row).model_dump()
        items.append(view)
    if config.list_view_enricher is not None:
        items = await config.list_view_enricher(uow, rows, items, projection)
    elif config.view_enricher is not None:
        # Audit iter 46 (T-44): per-row enrichment for derived View
        # fields (item_count, version_count). N+1 query is still acceptable
        # for entities that already use it (Playlist, Set; both small
        # populations). Larger entities should register a list-level
        # enricher instead.
        enriched: list[dict] = []  # type: ignore[type-arg]
        for row, view in zip(rows, items, strict=True):
            enriched.append(await config.view_enricher(uow, row, view))
        items = enriched
    if projection is not None:
        projected: list[dict] = []  # type: ignore[type-arg]
        for view in items:
            view = {k: v for k, v in view.items() if k in projection}
            projected.append(view)
        items = projected
    total = page.total if with_total else None
    return EntityListResult(entity=entity, items=items, total=total, next_cursor=page.next_cursor)
