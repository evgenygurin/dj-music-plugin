"""entity_create — polymorphic create with optional custom handler."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

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
from app.shared.errors import ValidationError
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
    meta={"timeout_s": 120.0},
    timeout=120.0,
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

    # Audit iter 54 (T-52): schema validation must run BEFORE the
    # handler dispatch — previously the handler path read ``data``
    # raw and skipped Pydantic validators, bypassing
    # cross-field invariants like ``from_track_id != to_track_id``.
    # Single-pass validate + cache the validated model so handlers
    # that want it can pull the typed fields, while handlers that
    # ignore it (e.g. ``track_import``) still get the raw dict.
    try:
        validated = config.create_schema.model_validate(data)
    except PydanticValidationError as exc:
        # Convert Pydantic schema errors into a domain ValidationError so
        # DomainErrorMiddleware emits a clean "invalid input: ..." message
        # instead of the generic "internal error" wrapper (which in prod,
        # with ``mask_details=True``, leaked zero diagnostic info).
        raise ValidationError(
            f"invalid payload for entity {entity!r}: {exc.error_count()} "
            f"schema error(s); {exc.errors(include_url=False)}",
            details={"errors": exc.errors(include_url=False)},
        ) from exc

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

    # Default path: straight insert (schema already validated above).
    # Audit iter 16 (T-16): post-validate cross-domain references that
    # the schema can't enforce alone (schemas may not import
    # ``app.domain`` per the v2-server import contract). For sets,
    # ``template_name`` must point at a registered template -
    # otherwise the optimizer rejects it later, and the set lingers
    # with a bogus name that nothing can use.
    template_name_val = getattr(validated, "template_name", None) if entity == "set" else None
    if template_name_val is not None:
        from app.domain.template.registry import list_template_names

        if template_name_val not in list_template_names():
            raise ValidationError(
                f"unknown template_name {template_name_val!r}; "
                f"valid templates: {sorted(list_template_names())}",
                details={"template_name": template_name_val},
            )

    # ── Foreign-key gates ────────────────────────────────────────────
    # SQLite (default FK enforcement off) lets bogus references through
    # to the row; PostgreSQL rejects them as opaque
    # ``ForeignKeyViolationError`` long after a clean message would have
    # named the bad id. Validate per-entity up front.
    if entity == "set":
        src_pl = getattr(validated, "source_playlist_id", None)
        if src_pl is not None and await uow.playlists.get(src_pl) is None:
            raise ValidationError(
                f"source_playlist_id {src_pl} does not reference an existing playlist",
                details={"source_playlist_id": src_pl},
            )
    elif entity == "playlist":
        parent_id = getattr(validated, "parent_id", None)
        if parent_id is not None and await uow.playlists.get(parent_id) is None:
            raise ValidationError(
                f"parent_id {parent_id} does not reference an existing playlist",
                details={"parent_id": parent_id},
            )
    elif entity == "track_feedback":
        tid = getattr(validated, "track_id", None)
        if tid is not None and await uow.tracks.get(tid) is None:
            raise ValidationError(
                f"track_id {tid} does not reference an existing track",
                details={"track_id": tid},
            )
    elif entity == "track_affinity":
        # Two FK references — validate both with a single round-trip.
        a = getattr(validated, "track_a_id", None)
        b = getattr(validated, "track_b_id", None)
        missing: list[tuple[str, int]] = []
        if a is not None and await uow.tracks.get(a) is None:
            missing.append(("track_a_id", a))
        if b is not None and await uow.tracks.get(b) is None:
            missing.append(("track_b_id", b))
        if missing:
            details_msg = ", ".join(f"{name}={tid}" for name, tid in missing)
            raise ValidationError(
                f"track_affinity references missing track(s): {details_msg}",
                details={"missing": [{"field": n, "id": t} for n, t in missing]},
            )

    repo = getattr(uow, config.repo_attr)
    row = await repo.create(**validated.model_dump())
    view = config.view_schema.model_validate(row).model_dump()
    # Audit iter 49 (T-47): also run the View enricher on create so
    # derived fields (item_count, version_count) are populated in the
    # response — a fresh row has 0 items / 0 versions but the field
    # should be ``0`` not ``null``.
    if config.view_enricher is not None:
        view = await config.view_enricher(uow, row, view)
    return EntityCreateResult(entity=entity, data=view, meta={"via": "default"})
