"""Curation tools (5 tools, tag: curation).

Thin wrappers calling CurationService via Depends().
Tools:
- classify_mood: classify tracks by 15 techno subgenres
- audit_playlist: audit playlist for quality criteria
- quick_set_review: review set transitions quality
- distribute_to_subgenres: sort tracks into subgenre playlists
- get_library_stats: library dashboard stats
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_curation_service, get_playlist_repo, get_tiered_pipeline
from app.repositories.playlist import PlaylistRepository
from app.services.curation_service import CurationService
from app.services.tiered_pipeline import TieredPipeline

# ── 1. classify_mood ─────────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": False}, timeout=600.0, task=True)
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
    from app.audio.level_config import AnalysisLevel
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    if not track_ids and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")

    # Resolve all track IDs for auto-analysis
    ids_for_analysis: list[int] = list(track_ids) if track_ids else []
    if playlist_id is not None:
        ids_for_analysis.extend(await playlist_repo.get_track_ids(playlist_id))

    if ids_for_analysis:
        analysis = await tiered.ensure_level(ids_for_analysis, AnalysisLevel.TRIAGE)
        if ctx and analysis["analyzed"] > 0:
            await ctx.info(f"Auto-analyzed {analysis['analyzed']} tracks (L2 triage)")

    return await svc.classify_mood(
        track_ids=list(track_ids) if track_ids else None,
        playlist_id=playlist_id,
        reclassify=reclassify,
    )


# ── 2. audit_playlist ───────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True}, timeout=600.0, task=True)
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
    from app.audio.level_config import AnalysisLevel
    from app.mcp.tools._helpers import validate_id_or_query

    validate_id_or_query(playlist_id, playlist_query, "playlist")

    # Auto-analyze tracks to L2 (triage) before auditing — mood classifier only needs L1+L2 features
    if playlist_id is not None:
        ids = await playlist_repo.get_track_ids(playlist_id)
        if ids:
            analysis = await tiered.ensure_level(ids, AnalysisLevel.TRIAGE)
            if ctx and analysis["analyzed"] > 0:
                await ctx.info(f"Auto-analyzed {analysis['analyzed']} tracks (L2 triage)")

    return await svc.audit_playlist(
        playlist_id=playlist_id,
        playlist_query=playlist_query,
    )


# ── 3. quick_set_review ─────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def quick_set_review(
    set_id: int,
    version: str | None = None,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Review set quality: transition scores, BPM flow, energy arc, quality rating."""
    return await svc.review_set_quality(set_id=set_id, version_label=version)


# ── 4. distribute_to_subgenres ──────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": False})
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
    from app.audio.level_config import AnalysisLevel

    # Auto-analyze tracks to L2 (triage) — mood classifier only needs L1+L2 features
    if source_playlist_id is not None:
        ids = await playlist_repo.get_track_ids(source_playlist_id)
        if ids:
            analysis = await tiered.ensure_level(ids, AnalysisLevel.TRIAGE)
            if ctx and analysis["analyzed"] > 0:
                await ctx.info(f"Auto-analyzed {analysis['analyzed']} tracks (L2 triage)")

    return await svc.distribute_to_subgenres(
        source_playlist_id=source_playlist_id,
        mode=mode,
        dry_run=dry_run,
    )


# ── 5. get_library_stats ────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def get_library_stats(
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Library dashboard: counts, coverage, distributions."""
    return await svc.get_library_stats()
