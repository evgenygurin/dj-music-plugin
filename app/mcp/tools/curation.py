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

from app.mcp.dependencies import get_curation_service
from app.services.curation_service import CurationService

# ── 1. classify_mood ─────────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": False})
async def classify_mood(
    track_ids: Any = None,
    playlist_id: int | None = None,
    reclassify: bool = False,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify tracks by 15 techno subgenres using rule-based MoodClassifier."""
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    if not track_ids and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")
    return await svc.classify_mood(
        track_ids=list(track_ids) if track_ids else None,
        playlist_id=playlist_id,
        reclassify=reclassify,
    )


# ── 2. audit_playlist ───────────────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": True})
async def audit_playlist(
    playlist_id: int | None = None,
    playlist_query: str | None = None,
    check: str | None = None,
    template: str | None = None,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Audit playlist for techno quality criteria and library gaps."""
    if playlist_id is None and playlist_query is None:
        raise ToolError("Provide playlist_id or playlist_query")
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
    return await svc.review_set_quality(set_id=set_id, version=version)


# ── 4. distribute_to_subgenres ──────────────────────


@tool(tags={"curation"}, annotations={"readOnlyHint": False})
async def distribute_to_subgenres(
    source_playlist_id: int | None = None,
    mode: str = "append",
    sync_to_ym: bool = False,
    dry_run: bool = False,
    svc: CurationService = Depends(get_curation_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Distribute tracks to 15 subgenre playlists based on mood classification."""
    return await svc.distribute_to_subgenres(
        source_playlist_id=source_playlist_id,
        mode=mode,
        sync_to_ym=sync_to_ym,
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
