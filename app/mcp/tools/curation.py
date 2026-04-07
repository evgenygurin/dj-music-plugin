"""Curation tools (5 tools, tag: curation).

Thin wrappers calling :class:`CurationService` via ``Depends()``.

Tools:
- ``classify_mood`` — classify tracks by 15 techno subgenres
- ``audit_playlist`` — audit playlist for quality criteria
- ``review_set_quality`` — review set transitions quality
- ``distribute_to_subgenres`` — sort tracks into subgenre playlists
- ``get_library_stats`` — library dashboard stats
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.audio.level_config import AnalysisLevel
from app.core.parsing import ensure_list
from app.mcp.dependencies import (
    get_curation_service,
    get_playlist_repo,
    get_tiered_pipeline,
)
from app.mcp.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    ensure_reference,
    map_domain_errors,
)
from app.repositories.playlist import PlaylistRepository
from app.services.curation_service import CurationService
from app.services.tiered_pipeline import TieredPipeline


async def _auto_triage(
    track_ids: list[int],
    tiered: TieredPipeline,
    log: ToolContext,
) -> None:
    """Shared tiered auto-trigger boilerplate used by every curation tool."""
    if not track_ids:
        return
    analysis = await tiered.ensure_level(track_ids, AnalysisLevel.TRIAGE)
    if analysis["analyzed"] > 0:
        await log.info(f"Auto-analyzed {analysis['analyzed']} tracks (L2 triage)")


@tool(
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_WRITE,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def classify_mood(
    track_ids: Any = None,
    playlist_id: int | None = None,
    reclassify: bool = False,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify tracks by 15 techno subgenres using rule-based MoodClassifier."""
    log = ToolContext(ctx)
    ids = ensure_list(track_ids) or None
    if not ids and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")

    all_ids: list[int] = list(ids) if ids else []
    if playlist_id is not None:
        all_ids.extend(await playlist_repo.get_track_ids(playlist_id))

    await _auto_triage(all_ids, tiered, log)

    return await svc.classify_mood(
        track_ids=list(ids) if ids else None,
        playlist_id=playlist_id,
        reclassify=reclassify,
    )


@tool(
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_READ_ONLY,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def audit_playlist(
    playlist_id: int | None = None,
    playlist_query: str | None = None,
    check: str | None = None,
    template: str | None = None,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Audit playlist for techno quality criteria and library gaps."""
    log = ToolContext(ctx)
    ensure_reference(playlist_id, playlist_query, entity_name="playlist")

    if playlist_id is not None:
        await _auto_triage(await playlist_repo.get_track_ids(playlist_id), tiered, log)

    return await svc.audit_playlist(
        playlist_id=playlist_id,
        playlist_query=playlist_query,
    )


@tool(tags={ToolCategory.CURATION.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def review_set_quality(
    set_id: int,
    version: str | None = None,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Review set quality: transition scores, BPM flow, energy arc, rating."""
    return await svc.review_set_quality(set_id=set_id, version_label=version)


@tool(tags={ToolCategory.CURATION.value}, annotations=ANNOTATIONS_WRITE)
@map_domain_errors
async def distribute_to_subgenres(
    source_playlist_id: int | None = None,
    mode: str = "append",
    sync_to_ym: bool = False,
    dry_run: bool = False,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: PlaylistRepository = Depends(get_playlist_repo),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Distribute tracks to 15 subgenre playlists based on mood classification."""
    log = ToolContext(ctx)

    if source_playlist_id is not None:
        await _auto_triage(await playlist_repo.get_track_ids(source_playlist_id), tiered, log)

    return await svc.distribute_to_subgenres(
        source_playlist_id=source_playlist_id,
        mode=mode,
        dry_run=dry_run,
    )


@tool(tags={ToolCategory.CURATION.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_library_stats(
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Library dashboard: counts, coverage, distributions."""
    return await svc.get_library_stats()
