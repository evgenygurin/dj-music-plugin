"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via `unlock_tools(action="unlock", category="audio")`.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp.dependencies import (
    get_audio_service,
    get_db_session,
    get_tiered_pipeline,
    get_track_service,
)
from app.mcp.tools._helpers import resolve_track_id
from app.services.audio_service import AudioService
from app.services.tiered_pipeline import TieredPipeline

# ── 1. analyze_track ─────────────────────────────────


@tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    timeout=600.0,
)
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: Any = None,
    force: bool = False,
    level: int | None = None,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    track_svc: Any = Depends(get_track_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline + mood classification on a track.

    If level is set (2/3/4/5), uses TieredPipeline (downloads from YM, no local file needed).
    """
    from app.audio.level_config import AnalysisLevel
    from app.core.parsing import ensure_list

    analyzers = ensure_list(analyzers) or None
    track_id = await resolve_track_id(id=track_id, query=track_query, svc=track_svc)

    # Level-based tiered analysis (downloads from YM, no local file needed)
    if level is not None:
        target = AnalysisLevel(level)
        if ctx:
            await ctx.info(f"Tiered analysis L{level} for track {track_id}...")
        analysis = await tiered.ensure_level([track_id], target)
        return {
            "track_id": track_id,
            "level": level,
            "status": "analyzed" if analysis["analyzed"] > 0 else "skipped",
            **analysis,
        }

    if ctx:
        await ctx.info(f"Analyzing track {track_id}...")

    result = await svc.analyze_track(track_id, analyzers=analyzers, force=force)

    if ctx and result.get("status") == "analyzed":
        await ctx.info(
            f"Analysis complete: {result.get('feature_count', 0)} features, mood={result.get('mood')}"
        )

    return result


# ── 2. analyze_batch ─────────────────────────────────


@tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    timeout=600.0,
    task=True,
)
async def analyze_batch(
    track_ids: Any = None,
    playlist_id: int | None = None,
    analyzers: Any = None,
    priority: str = "normal",
    level: int | None = None,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch audio analysis for multiple tracks or a playlist.

    If level is set (2/3/4/5), uses TieredPipeline (downloads from YM, no local file needed).
    """
    from app.audio.level_config import AnalysisLevel
    from app.core.parsing import ensure_list

    track_ids = ensure_list(track_ids) or None
    analyzers = ensure_list(analyzers) or None
    if track_ids is None and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")
    if track_ids is not None and playlist_id is not None:
        raise ToolError("Provide track_ids or playlist_id, not both")

    # Resolve playlist to track IDs
    if playlist_id is not None:
        from sqlalchemy import select

        from app.models.playlist import PlaylistItem

        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        db_result = await session.execute(stmt)
        track_ids = [r[0] for r in db_result.all()]

    if not track_ids:
        raise ToolError("No tracks to analyze")

    # Level-based tiered analysis (downloads from YM, no local file needed)
    if level is not None:
        target = AnalysisLevel(level)
        if ctx:
            await ctx.info(f"Tiered batch analysis L{level}: {len(track_ids)} tracks")
        analysis = await tiered.ensure_level(track_ids, target)
        if ctx:
            await ctx.info(
                f"Batch complete: {analysis['analyzed']} analyzed, "
                f"{analysis['skipped']} skipped, {analysis['failed']} failed"
            )
        return {
            "total_tracks": len(track_ids),
            "completed": analysis["analyzed"],
            "failed": analysis["failed"],
            "skipped": analysis["skipped"],
            "level": level,
        }

    total = len(track_ids)
    completed = 0
    failed = 0
    skipped = 0

    if ctx:
        await ctx.info(f"Batch analysis: {total} tracks, priority={priority}")
        await ctx.report_progress(0, total)

    for i, tid in enumerate(track_ids):
        result = await svc.analyze_track(tid, analyzers=analyzers)
        status = result.get("status", "error")
        if status == "analyzed":
            completed += 1
        elif status == "cached":
            skipped += 1
        else:
            failed += 1

        if ctx and (i + 1) % 5 == 0:
            await ctx.report_progress(i + 1, total)

    if ctx:
        await ctx.report_progress(total, total)
        await ctx.info(f"Batch complete: {completed} analyzed, {skipped} cached, {failed} failed")

    return {
        "total_tracks": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
    }


# ── 3. separate_stems ────────────────────────────────


@tool(tags={"audio"}, timeout=600.0)
async def separate_stems(
    track_id: int | None = None,
    track_query: str | None = None,
    stems: Any = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ML-based stem separation (vocals, drums, bass, other). Requires [stems] extra."""
    from app.core.parsing import ensure_list
    from app.mcp.tools._helpers import validate_id_or_query

    stems = ensure_list(stems) or None
    validate_id_or_query(track_id, track_query, "track")

    valid_stems = {"vocals", "drums", "bass", "other"}
    if stems:
        invalid = set(stems) - valid_stems
        if invalid:
            raise ToolError(f"Invalid stems: {sorted(invalid)}. Valid: {sorted(valid_stems)}")

    return {
        "track_id": track_id,
        "track_query": track_query,
        "stems_requested": stems or sorted(valid_stems),
        "status": "stub",
        "output_files": {},
        "note": "Requires [stems] extra: uv sync --extra stems",
    }
