"""sequence_optimize — GA or greedy track-ordering optimizer."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.repositories.unit_of_work import UnitOfWork
from app.schemas.tool_responses import SequenceOptimizeResult
from app.server.di import get_optimizer, get_transition_scorer, get_uow
from app.shared.errors import ValidationError
from app.shared.types import JsonIntList, JsonIntListOrNone


@tool(
    name="sequence_optimize",
    tags={"namespace:compute", "read"},
    annotations={"readOnlyHint": True, "idempotentHint": False},
    description=(
        "Find optimal track ordering via GA or greedy. Supports pinned/excluded "
        "tracks + template-aware fitness. Returns ordering + quality score."
    ),
    meta={"timeout_s": 300.0},
    timeout=300.0,
)
async def sequence_optimize(
    track_ids: Annotated[
        JsonIntList, Field(min_length=2, max_length=500, description="Pool of track IDs")
    ],
    algorithm: Annotated[
        Literal["ga", "greedy"], Field(description="Optimization algorithm")
    ] = "ga",
    template: Annotated[
        str | None, Field(description="Set template name (for template-aware fitness)")
    ] = None,
    pinned: Annotated[JsonIntListOrNone, Field(description="Must-include track IDs")] = None,
    excluded: Annotated[JsonIntListOrNone, Field(description="Banned track IDs")] = None,
    uow: UnitOfWork = Depends(get_uow),
    scorer: Any = Depends(get_transition_scorer),
    optimizer_builder: Any = Depends(get_optimizer),
    ctx: Context = CurrentContext(),
) -> SequenceOptimizeResult:
    # Audit iter 11 (T-14): validate ``template`` name up front against
    # the registered templates. Prior behaviour accepted any string and
    # silently passed ``template=None`` to the optimizer regardless,
    # giving callers a parameter they thought worked but didn't. Now
    # invalid names fail fast and valid names resolve to a real
    # ``SetTemplateDefinition`` that the optimizer can actually use.
    template_def = None
    if template is not None:
        from app.domain.template.registry import get_template as _get_template
        from app.domain.template.registry import (
            list_template_names as _list_template_names,
        )

        if template not in _list_template_names():
            raise ValidationError(
                f"unknown template {template!r}; "
                f"valid templates: {sorted(_list_template_names())}",
                details={"template": template},
            )
        template_def = _get_template(template)

    # Audit iter 5 (T-2): reject pinned/excluded overlap up front. The
    # optimizer previously let pinned win silently, so a caller
    # passing ``pinned=[146], excluded=[146]`` got 146 in the result
    # despite asking for it banned - the contradiction never
    # surfaced.
    pinned_set = set(pinned or [])
    excluded_set = set(excluded or [])
    overlap = pinned_set & excluded_set
    if overlap:
        raise ValidationError(
            f"track_ids cannot be both pinned and excluded: {sorted(overlap)}",
            details={"overlap": sorted(overlap)},
        )

    # Audit iter 3: reject duplicate ids explicitly. Prior behaviour
    # silently deduped through ``set()`` inside the optimizer, so
    # callers passing ``[146, 146, 147]`` got a 2-track order back
    # without a signal. ``transition_score_pool`` agreed on the same
    # validation in iter 3.
    if len(set(track_ids)) != len(track_ids):
        seen: set[int] = set()
        duplicates: list[int] = []
        for tid in track_ids:
            if tid in seen and tid not in duplicates:
                duplicates.append(tid)
            seen.add(tid)
        raise ValidationError(
            f"track_ids contains duplicate id(s): {duplicates}",
            details={"duplicates": duplicates},
        )

    features = await uow.track_features.get_scoring_features_batch(track_ids)
    features_list = [features.get(tid) for tid in track_ids]

    optimizer = optimizer_builder(algorithm=algorithm, scorer=scorer)

    async def _progress(gen: int, score: float) -> None:
        await ctx.report_progress(progress=gen, total=100, message=f"best={score:.3f}")

    result = optimizer.optimize(
        tracks=features_list,
        track_ids=track_ids,
        pinned=set(pinned or []),
        excluded=set(excluded or []),
        template=template_def,
        moods=None,
        on_progress=lambda g, s: None,
    )

    return SequenceOptimizeResult(
        track_order=list(result.track_order),
        quality_score=float(result.quality_score),
        algorithm=algorithm,
        generations=result.generations or 0,
    )
