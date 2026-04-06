"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via `unlock_tools(action="unlock", category="audio")`.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import (
    Depends,
    Progress,
)
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
    level: int = 3,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    track_svc: Any = Depends(get_track_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis on a track. Default: L3 SCORING via TieredPipeline.

    level: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    If analyzers is set explicitly, uses local file pipeline instead of tiered.
    """
    from app.audio.level_config import AnalysisLevel
    from app.core.parsing import ensure_list

    analyzers = ensure_list(analyzers) or None
    track_id = await resolve_track_id(id=track_id, query=track_query, svc=track_svc)

    # Custom analyzers → use local file pipeline (legacy path)
    if analyzers is not None:
        if ctx:
            await ctx.info(f"Analyzing track {track_id} with custom analyzers...")
        result = await svc.analyze_track(track_id, analyzers=analyzers, force=force)
        if result.get("error") == "No audio file linked":
            if ctx:
                await ctx.info("No local file — falling back to tiered pipeline...")
            analysis = await tiered.ensure_level([track_id], AnalysisLevel.SCORING, force=force)
            return {
                "track_id": track_id,
                "level": int(AnalysisLevel.SCORING),
                "status": "analyzed" if analysis["analyzed"] > 0 else "error",
                **analysis,
            }
        return result

    # Tiered pipeline (default path)
    valid_levels = [lv.value for lv in AnalysisLevel if lv != AnalysisLevel.NONE]
    if level not in valid_levels:
        raise ToolError(
            f"Invalid level: {level}. Valid levels: {valid_levels} "
            f"(TRIAGE=2, SCORING=3, TRANSITION=4, ADVANCED=5)"
        )
    target = AnalysisLevel(level)
    if ctx:
        await ctx.info(f"Tiered analysis L{level} for track {track_id}...")
    analysis = await tiered.ensure_level([track_id], target, force=force)
    return {
        "track_id": track_id,
        "level": level,
        "status": "analyzed" if analysis["analyzed"] > 0 else "skipped",
        **analysis,
    }


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
    batch_size: int = 20,
    analyzers: Any = None,
    level: int = 3,
    force: bool = False,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    progress: Progress = Progress(),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch audio analysis. Default: L3 SCORING, 20 tracks per batch.

    level: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    batch_size: max tracks per batch (default 20). Provide more and they'll be chunked.
    If analyzers is set explicitly, uses local file pipeline instead of tiered.
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

    # Limit to batch_size
    track_ids = track_ids[:batch_size]
    total = len(track_ids)
    await progress.set_total(total)

    valid_levels = [lv.value for lv in AnalysisLevel if lv != AnalysisLevel.NONE]
    if level not in valid_levels:
        raise ToolError(
            f"Invalid level: {level}. Valid levels: {valid_levels} "
            f"(TRIAGE=2, SCORING=3, TRANSITION=4, ADVANCED=5)"
        )
    target = AnalysisLevel(level)

    # Custom analyzers → per-track local file pipeline (legacy path)
    if analyzers is not None:
        completed = 0
        failed = 0
        skipped = 0
        await progress.set_message(f"Analyzing {total} tracks with custom analyzers...")

        for i, tid in enumerate(track_ids):
            await progress.set_message(f"Track {i + 1}/{total} (id={tid})")
            result = await svc.analyze_track(tid, analyzers=analyzers, force=force)
            if result.get("error") == "No audio file linked":
                tr = await tiered.ensure_level([tid], target, force=force)
                result = {"status": "analyzed" if tr["analyzed"] > 0 else "error"}
            status = result.get("status", "error")
            if status == "analyzed":
                completed += 1
            elif status == "cached":
                skipped += 1
            else:
                failed += 1
            await progress.increment()

        return {
            "total_tracks": total,
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }

    # Tiered pipeline (default path)
    await progress.set_message(f"Tiered batch L{level}: {total} tracks")
    analysis = await tiered.ensure_level(track_ids, target, force=force)
    await progress.increment(total)
    return {
        "total_tracks": total,
        "completed": analysis["analyzed"],
        "failed": analysis["failed"],
        "skipped": analysis["skipped"],
        "level": level,
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
