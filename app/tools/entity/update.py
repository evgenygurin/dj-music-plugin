"""entity_update — polymorphic partial update with optional handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.domain.template.registry import list_template_names
from app.domain.transition.neural_mix import NeuralMixTransition
from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import EntityUpdateResult
from app.server.di import (
    get_audio_pipeline,
    get_provider_registry,
    get_transition_scorer,
    get_uow,
)
from app.shared.errors import ValidationError
from app.shared.types import JsonDict
from app.tools.entity._dispatch import call_handler
from app.tools.entity._fk_gate import validate_fk_constraints

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
        "the audio pipeline at a higher level. This is a heavy operation — clients "
        "should request background execution for track_features updates."
    ),
    meta={"timeout_s": 360.0},
    timeout=360.0,
    task=True,
)
async def entity_update(
    entity: Annotated[EntityName, Field(description="Entity type")],
    id: Annotated[int, Field(ge=1, description="Entity primary key")],
    data: Annotated[JsonDict, Field(description="Partial update payload")],
    uow: UnitOfWork = Depends(get_uow),
    registry: ProviderRegistry = Depends(get_provider_registry),
    pipeline: Any = Depends(get_audio_pipeline),
    scorer: Any = Depends(get_transition_scorer),
    ctx: Context = CurrentContext(),
) -> EntityUpdateResult:
    config = EntityRegistry.get(entity)
    if "update" not in config.allowed_ops:
        raise ValueError(f"update not allowed on {entity!r}")

    if config.update_handler is not None:
        merged = {**data, "id": id}
        # Handler receives the service matching its 4th parameter name
        # (registry / pipeline / scorer). Without this the reanalyze handler
        # used to get a ProviderRegistry instead of the AnalysisPipeline and
        # crash on ``pipeline.analyze_to_level(...)``.
        result = await call_handler(
            config.update_handler,
            ctx=ctx,
            uow=uow,
            data=merged,
            registry=registry,
            pipeline=pipeline,
            scorer=scorer,
        )
        return EntityUpdateResult(entity=entity, id=id, data=result)

    try:
        validated = config.update_schema.model_validate(data)
    except PydanticValidationError as exc:
        # Convert raw Pydantic errors into a domain ValidationError so
        # DomainErrorMiddleware emits "invalid input: ..." rather than the
        # generic "internal error" wrapper (which masks all detail in prod).
        raise ValidationError(
            f"invalid payload for entity {entity!r}: {exc.error_count()} "
            f"schema error(s); {exc.errors(include_url=False)}",
            details={"errors": exc.errors(include_url=False)},
        ) from exc
    # Audit iter 26 (T-26): mirror the entity_create template_name
    # check on update path. ``set.template_name`` accepts free-form
    # strings on the schema (schemas can't import ``app.domain``);
    # the dispatcher validates against the registered templates so
    # ``entity_update(set, ...)`` can't write a template name that
    # ``sequence_optimize`` will later reject.
    template_name_val = getattr(validated, "template_name", None) if entity == "set" else None
    if template_name_val is not None and template_name_val not in list_template_names():
        raise ValidationError(
            f"unknown template_name {template_name_val!r}; "
            f"valid templates: {sorted(list_template_names())}",
            details={"template_name": template_name_val},
        )

    # ``transition.fx_type`` is a free-form string on the schema (the
    # schema can't import ``app.domain``) but downstream Neural Mix
    # recipe builders + UI renderers only know the seven enum values.
    # A typo like ``fx_type="lol_wut"`` used to slip into the row and
    # then either crash the renderer or silently fall back to defaults.
    # Validate against the same enum the picker / recipe builders use.
    fx_type_val = getattr(validated, "fx_type", None) if entity == "transition" else None
    if fx_type_val is not None:
        allowed = [t.value for t in NeuralMixTransition]
        if fx_type_val not in allowed:
            raise ValidationError(
                f"unknown fx_type {fx_type_val!r}; "
                f"valid Neural Mix transitions: {sorted(allowed)}",
                details={"fx_type": fx_type_val},
            )

    # FK gates — generic, data-driven (see ``EntityConfig.fk_constraints``
    # auto-derived from ORM in ``app.registry.defaults._wire_fk_constraints``).
    # SQLite (default FK enforcement off — overridden in
    # ``app/db/session.py`` via ``PRAGMA foreign_keys=ON``) would otherwise
    # silently write orphan FK refs; PostgreSQL would raise an opaque
    # FK violation. The app-level gate gives an informative typed error
    # naming the bad id BEFORE the DB rejects it. ``partial_keys=data.keys()``
    # ensures only FK fields actually present in the patch payload are
    # checked (others stay at their existing row values).
    await validate_fk_constraints(uow, config, validated, partial_keys=data.keys())

    # Cross-row BPM-range invariant for ``set``: ``SetUpdate`` schema
    # can only catch the case where BOTH sides come in the same payload
    # (``_validate_bpm_range``). Partial updates that change only one
    # side need a DB read to check against the existing value.
    # Previously this slipped through — ``entity_update(set, id=N, data=
    # {target_bpm_min: 150})`` on a row with ``target_bpm_max=140``
    # ended with a row violating ``min <= max``.
    if entity == "set" and ("target_bpm_min" in data or "target_bpm_max" in data):
        existing = await uow.sets.get(id)
        if existing is not None:
            new_min = data.get("target_bpm_min", existing.target_bpm_min)
            new_max = data.get("target_bpm_max", existing.target_bpm_max)
            if new_min is not None and new_max is not None and new_min > new_max:
                raise ValidationError(
                    f"target_bpm_min ({new_min}) must be <= target_bpm_max "
                    f"({new_max}) after applying partial update",
                    details={
                        "target_bpm_min": new_min,
                        "target_bpm_max": new_max,
                    },
                )

    # Audit iter 53 (T-51): playlist hierarchy cycle prevention.
    # ``entity_update(playlist, id=X, data={parent_id: Y})`` used to
    # accept ``Y == X`` (self-cycle) and ``Y`` already in ``X``'s
    # descendants (N-cycle), corrupting the playlist tree. Walk Y's
    # ancestor chain and reject if X appears in it.
    if entity == "playlist":
        new_parent_id = data.get("parent_id")
        if new_parent_id is not None:
            if new_parent_id == id:
                raise ValidationError(
                    f"playlist {id} cannot be its own parent (self-cycle)",
                    details={"playlist_id": id, "parent_id": new_parent_id},
                )
            ancestor_chain = await uow.playlists.ancestor_ids(new_parent_id)
            if id in ancestor_chain:
                raise ValidationError(
                    f"setting playlist {id}'s parent to {new_parent_id} would "
                    f"create a cycle (chain: {' → '.join(str(p) for p in ancestor_chain)} → {id})",
                    details={
                        "playlist_id": id,
                        "parent_id": new_parent_id,
                        "ancestor_chain": ancestor_chain,
                    },
                )

    repo = getattr(uow, config.repo_attr)
    row = await repo.update(id, **validated.model_dump(exclude_unset=True))
    view = config.view_schema.model_validate(row).model_dump()
    # Audit iter 49 (T-47): same view-enricher hook as get/list/create
    # so derived fields stay populated after an update too.
    if config.view_enricher is not None:
        view = await config.view_enricher(uow, row, view)
    return EntityUpdateResult(entity=entity, id=id, data=view)
