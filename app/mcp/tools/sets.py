"""Set building tools: build, rebuild, score transitions, cheat sheet.

Thin wrappers calling :class:`SetService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.audio.level_config import AnalysisLevel
from app.mcp.dependencies import get_playlist_repo, get_set_service, get_tiered_pipeline
from app.mcp.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.repositories.playlist import PlaylistRepository
from app.services.set.facade import SetService
from app.services.tiered_pipeline import TieredPipeline


async def _ensure_scoring_level(
    track_ids: list[int],
    tiered: TieredPipeline,
    log: ToolContext,
) -> None:
    """Run L3 scoring-level triage on ``track_ids`` and log the outcome."""
    if not track_ids:
        return
    analysis = await tiered.ensure_level(track_ids, AnalysisLevel.SCORING)
    if analysis["analyzed"] > 0:
        await log.info(f"Auto-analyzed {analysis['analyzed']} tracks (L3 scoring)")


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
    svc: SetService = Depends(get_set_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Build optimized DJ set from playlist. Supports ``greedy`` or ``ga`` algorithm."""
    log = ToolContext(ctx)
    await log.info(f"Building set '{name}' from playlist {playlist_id}...")
    await log.progress(0, 3)

    await _ensure_scoring_level(
        await playlist_repo.get_track_ids(playlist_id),
        tiered,
        log,
    )

    if dry_run:
        return await svc.build_set_dry_run(
            playlist_id=playlist_id,
            template=template,
            algorithm=algorithm,
        )

    dj_set, version, quality, used_algorithm = await svc.build_set(
        playlist_id=playlist_id,
        name=name,
        template=template,
        target_duration_min=target_duration_min,
        algorithm=algorithm,
    )

    items = await svc.get_version_items(version.id)
    await log.info(f"Set created: {dj_set.id}, version: {version.id}")
    await log.progress(3, 3)

    return {
        "set_id": dj_set.id,
        "version_id": version.id,
        "version_label": version.label,
        "track_count": len(items),
        "algorithm": used_algorithm,
        "quality_score": round(quality, 4) if quality else None,
        "template": template,
    }


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
    svc: SetService = Depends(get_set_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Rebuild existing set with pinned/excluded tracks. Creates new version."""
    log = ToolContext(ctx)
    await log.info(f"Rebuilding set {set_id}...")

    version = await svc.rebuild_set(
        set_id=set_id,
        pin_tracks=pin_tracks,
        exclude_tracks=exclude_tracks,
        version_label=version_label,
        algorithm=algorithm,
    )

    return {
        "set_id": set_id,
        "version_id": version.id,
        "version_label": version.label,
    }


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def score_transitions(
    mode: str = "set",
    set_id: int | None = None,
    from_track_id: int | None = None,
    to_track_id: int | None = None,
    track_id: int | None = None,
    top_n: int = 10,
    svc: SetService = Depends(get_set_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Score transitions.

    ``mode`` ∈ ``{set, pair, track_candidates}``. Computes scores via
    :class:`TransitionScorer` and **saves** them to the database.
    """
    log = ToolContext(ctx)

    if mode == "pair" and from_track_id and to_track_id:
        await _ensure_scoring_level([from_track_id, to_track_id], tiered, log)
        return await svc.score_pair(from_track_id, to_track_id)

    if mode == "track_candidates" and track_id:
        await _ensure_scoring_level([track_id], tiered, log)
        return await svc.get_transition_candidates(track_id, top_n=top_n)

    if mode == "set" and set_id:
        result = await svc._sets.load_version_with_items(set_id)
        if result:
            _, items = result
            await _ensure_scoring_level([item.track_id for item in items], tiered, log)
        return await svc.score_set_transitions(set_id)

    raise ToolError("Invalid mode or missing parameters")


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
