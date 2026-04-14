"""Curation tools (4 tools, tag: curation).

Thin wrappers calling :class:`CurationService` via ``Depends()``.

Tools:
- ``classify_mood`` — classify tracks by 15 techno subgenres
- ``audit_playlist`` — audit playlist for quality criteria
- ``distribute_to_subgenres`` — sort tracks into subgenre playlists
- ``get_library_stats`` — library dashboard stats
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.audio.level_config import AnalysisLevel
from app.controllers.dependencies import (
    get_curation_service,
    get_playlist_repo,
    get_tiered_pipeline,
)
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_CURATION,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    ensure_reference,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_list
from app.db.repositories.playlist import PlaylistRepository
from app.services.curation.facade import CurationService
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
    title="Classify Mood",
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_CURATION,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def classify_mood(
    track_ids: Annotated[list[int] | None, Field(description="Track IDs to classify")] = None,
    playlist_id: Annotated[
        int | None, Field(description="Classify all tracks in playlist")
    ] = None,
    reclassify: Annotated[bool, Field(description="Overwrite existing mood labels")] = False,
    svc: Annotated[
        CurationService,
        Field(description="Curation service for mood classification"),
    ] = Depends(get_curation_service),  # noqa: B008
    tiered: Annotated[
        TieredPipeline,
        Field(description="Tiered analysis pipeline for auto-triage"),
    ] = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: Annotated[
        PlaylistRepository,
        Field(description="Playlist repository for playlist track IDs"),
    ] = Depends(get_playlist_repo),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP context for tool logging"),
    ] = None,
) -> dict[str, Any]:
    """Classifies tracks into 15 techno subgenres with the mood classifier. Use when labeling tracks or a whole playlist before curation."""
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
    title="Audit Playlist",
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_CURATION,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def audit_playlist(
    playlist_id: Annotated[int | None, Field(description="Local playlist ID")] = None,
    playlist_query: Annotated[
        str | None, Field(description="Resolve playlist by name query")
    ] = None,
    check: Annotated[str | None, Field(description="Named audit check to run (optional)")] = None,
    template: Annotated[str | None, Field(description="Audit template name (optional)")] = None,
    svc: Annotated[
        CurationService,
        Field(description="Curation service for playlist audits"),
    ] = Depends(get_curation_service),  # noqa: B008
    tiered: Annotated[
        TieredPipeline,
        Field(description="Tiered analysis pipeline for auto-triage"),
    ] = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: Annotated[
        PlaylistRepository,
        Field(description="Playlist repository for playlist track IDs"),
    ] = Depends(get_playlist_repo),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP context for tool logging"),
    ] = None,
) -> dict[str, Any]:
    """Audits a playlist against techno quality and gap checks. Use when reviewing library health before a set or cleanup."""
    log = ToolContext(ctx)
    ensure_reference(playlist_id, playlist_query, entity_name="playlist")

    if playlist_id is not None:
        await _auto_triage(await playlist_repo.get_track_ids(playlist_id), tiered, log)

    return await svc.audit_playlist(
        playlist_id=playlist_id,
        playlist_query=playlist_query,
    )


@tool(
    title="Distribute to Subgenres",
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_WRITE_DESTRUCTIVE_OPEN,
    icons=ICON_CURATION,
    meta=TOOL_META,
)
@map_domain_errors
async def distribute_to_subgenres(
    source_playlist_id: Annotated[
        int | None, Field(description="Source playlist whose tracks to distribute")
    ] = None,
    mode: Annotated[
        Literal["append", "replace"],
        Field(description="How to update subgenre playlists"),
    ] = "append",
    sync_to_ym: Annotated[bool, Field(description="Mirror changes to Yandex Music")] = False,
    dry_run: Annotated[bool, Field(description="Preview without modifying playlists")] = False,
    svc: Annotated[
        CurationService,
        Field(description="Curation service for subgenre distribution"),
    ] = Depends(get_curation_service),  # noqa: B008
    tiered: Annotated[
        TieredPipeline,
        Field(description="Tiered analysis pipeline for auto-triage"),
    ] = Depends(get_tiered_pipeline),  # noqa: B008
    playlist_repo: Annotated[
        PlaylistRepository,
        Field(description="Playlist repository for playlist track IDs"),
    ] = Depends(get_playlist_repo),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP context for tool logging"),
    ] = None,
) -> dict[str, Any]:
    """Routes tracks from a source playlist into per-subgenre playlists from mood labels. Use when reorganizing the library after classification."""
    log = ToolContext(ctx)

    if source_playlist_id is not None:
        await _auto_triage(await playlist_repo.get_track_ids(source_playlist_id), tiered, log)

    return await svc.distribute_to_subgenres(
        source_playlist_id=source_playlist_id,
        mode=mode,
        dry_run=dry_run,
    )


@tool(
    title="Library Stats",
    tags={ToolCategory.CURATION.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_CURATION,
    meta=TOOL_META,
)
@map_domain_errors
async def get_library_stats(
    svc: Annotated[
        CurationService,
        Field(description="Curation service for aggregate library metrics"),
    ] = Depends(get_curation_service),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="Optional MCP context for tool logging"),
    ] = None,
) -> dict[str, Any]:
    """Returns aggregate library stats such as counts and coverage. Use when you need a quick dashboard view of the collection."""
    return await svc.get_library_stats()
