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
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.services.set.facade import SetService
from app.services.workflows.build_set_workflow import BuildSetWorkflow


@tool(
    title="Build Set",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def build_set(
    name: str,
    playlist_id: int | None = None,
    source: str = "playlist",
    template: str | None = None,
    target_duration_min: int | None = None,
    algorithm: str = "greedy",
    dry_run: bool = False,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    moods: list[str] | None = None,
    energy_min: float | None = None,
    energy_max: float | None = None,
    pool_size: int = 500,
    workflow: BuildSetWorkflow = Depends(get_build_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Build optimized DJ set from playlist or library. Supports ``greedy`` or ``ga`` algorithm.

    ``source="playlist"`` builds from a specific playlist (requires ``playlist_id``).
    ``source="library"`` selects candidates from the full track library using
    BPM/mood/energy filters — no MP3 downloads needed.
    """
    return await workflow.build_set(
        playlist_id=playlist_id,
        name=name,
        source=source,
        template=template,
        target_duration_min=target_duration_min,
        algorithm=algorithm,
        dry_run=dry_run,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        moods=moods,
        energy_min=energy_min,
        energy_max=energy_max,
        pool_size=pool_size,
        log=ToolContext(ctx),
    )


@tool(
    title="Rebuild Set",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_SETS,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
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


@tool(
    title="Score Transitions",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_SETS,
    meta=TOOL_META,
)
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


@tool(
    title="Set Cheat Sheet",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def get_set_cheat_sheet(
    set_id: int,
    version: str | None = None,
    svc: SetService = Depends(get_set_service),  # noqa: B008
    ctx: Context | None = None,
) -> str:
    """Human-readable cheat sheet: BPM flow, key changes, energy arc."""
    return await svc.get_cheat_sheet(set_id, version=version)
