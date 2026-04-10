"""Set building tools: build, rebuild, score transitions, cheat sheet.

Thin wrappers calling :class:`SetService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_build_set_workflow, get_set_service
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.services.set.facade import SetService
from app.services.workflows.build_set_workflow import BuildSetWorkflow


@tool(
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def build_set(
    playlist_id: int,
    name: str,
    template: str | None = None,
    target_duration_min: int | None = None,
    algorithm: str = "greedy",
    dry_run: bool = False,
    workflow: BuildSetWorkflow = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Build optimized DJ set from playlist. Supports ``greedy`` or ``ga`` algorithm."""
    return await workflow.build_set(
        playlist_id=playlist_id,
        name=name,
        template=template,
        target_duration_min=target_duration_min,
        algorithm=algorithm,
        dry_run=dry_run,
        log=ToolContext(ctx),
    )


@tool(
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def rebuild_set(
    set_id: int,
    pin_tracks: list[int] | None = None,
    exclude_tracks: list[int] | None = None,
    algorithm: str = "greedy",
    version_label: str | None = None,
    workflow: BuildSetWorkflow = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Rebuild existing set with pinned/excluded tracks. Creates new version."""
    return await workflow.rebuild_set(
        set_id=set_id,
        pin_tracks=pin_tracks,
        exclude_tracks=exclude_tracks,
        algorithm=algorithm,
        version_label=version_label,
        log=ToolContext(ctx),
    )


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def score_transitions(
    mode: str = "set",
    set_id: int | None = None,
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    track_id: int | None = None,
    top_n: int = 10,
    workflow: BuildSetWorkflow = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Score transitions.

    ``mode`` ∈ ``{set, pair, track_candidates}``. Computes scores via
    :class:`TransitionScorer` and **saves** them to the database.
    """
    return await workflow.score_transitions(
        mode=mode,
        set_id=set_id,
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        track_id=track_id,
        top_n=top_n,
        log=ToolContext(ctx),
    )


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_set_cheat_sheet(
    set_id: int,
    version: str | None = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
    ctx: Context | None = None,
) -> str:
    """Human-readable cheat sheet: BPM flow, key changes, energy arc."""
    return await svc.get_cheat_sheet(set_id, version=version)
