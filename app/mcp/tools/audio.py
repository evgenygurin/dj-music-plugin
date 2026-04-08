"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via
``unlock_tools(action="unlock", category="audio")``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends, Progress
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.level_config import AnalysisLevel
from app.core.utils.parsing import ensure_list
from app.mcp.dependencies import (
    get_audio_service,
    get_db_session,
    get_tiered_pipeline,
    get_track_service,
)
from app.mcp.tools._shared import (
    ToolCategory,
    ToolContext,
    ToolTimeout,
    ensure_reference,
    map_domain_errors,
    resolve_track_id,
)
from app.models.playlist import PlaylistItem
from app.services.audio_service import AudioService
from app.services.tiered_pipeline import TieredPipeline
from app.services.track_service import TrackService

_ANALYSIS_IDEMPOTENT: dict[str, bool] = {"idempotentHint": True}
_VALID_STEMS = frozenset({"vocals", "drums", "bass", "other"})
_VALID_LEVELS = tuple(lv.value for lv in AnalysisLevel if lv != AnalysisLevel.NONE)


def _resolve_level(level: int) -> AnalysisLevel:
    if level not in _VALID_LEVELS:
        raise ToolError(
            f"Invalid level: {level}. Valid levels: {list(_VALID_LEVELS)} "
            "(TRIAGE=2, SCORING=3, TRANSITION=4, ADVANCED=5)"
        )
    return AnalysisLevel(level)


@tool(
    tags={ToolCategory.AUDIO.value},
    annotations=_ANALYSIS_IDEMPOTENT,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: Any = None,
    force: bool = False,
    level: int = 3,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis on a track. Default: L3 SCORING via TieredPipeline.

    ``level``: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    If ``analyzers`` is set explicitly, uses the local file pipeline
    instead of the tiered path.
    """
    log = ToolContext(ctx)
    analyzers_list = ensure_list(analyzers) or None
    resolved_id = await resolve_track_id(
        entity_id=track_id, query=track_query, search=track_svc.search
    )

    # Custom analyzers → use local file pipeline (legacy path)
    if analyzers_list is not None:
        await log.info(f"Analyzing track {resolved_id} with custom analyzers...")
        result = await svc.analyze_track(resolved_id, analyzers=analyzers_list, force=force)
        if result.get("error") == "No audio file linked":
            await log.info("No local file — falling back to tiered pipeline...")
            analysis = await tiered.ensure_level([resolved_id], AnalysisLevel.SCORING, force=force)
            return {
                "track_id": resolved_id,
                "level": int(AnalysisLevel.SCORING),
                "status": "analyzed" if analysis["analyzed"] > 0 else "error",
                **analysis,
            }
        return result

    target = _resolve_level(level)
    await log.info(f"Tiered analysis L{level} for track {resolved_id}...")
    analysis = await tiered.ensure_level([resolved_id], target, force=force)
    return {
        "track_id": resolved_id,
        "level": level,
        "status": "analyzed" if analysis["analyzed"] > 0 else "skipped",
        **analysis,
    }


@tool(
    tags={ToolCategory.AUDIO.value},
    annotations=_ANALYSIS_IDEMPOTENT,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
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

    ``level``: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    ``batch_size``: max tracks per batch (default 20).
    If ``analyzers`` is set explicitly, uses the local file pipeline
    instead of the tiered path.
    """
    ids_list: list[int] | None = ensure_list(track_ids) or None
    analyzers_list = ensure_list(analyzers) or None
    if ids_list is None and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")
    if ids_list is not None and playlist_id is not None:
        raise ToolError("Provide track_ids or playlist_id, not both")

    if playlist_id is not None:
        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        db_result = await session.execute(stmt)
        ids_list = [r[0] for r in db_result.all()]

    if not ids_list:
        raise ToolError("No tracks to analyze")

    ids_list = ids_list[:batch_size]
    total = len(ids_list)
    await progress.set_total(total)

    target = _resolve_level(level)

    # Custom analyzers → per-track local file pipeline (legacy path)
    if analyzers_list is not None:
        completed = 0
        failed = 0
        skipped = 0
        await progress.set_message(f"Analyzing {total} tracks with custom analyzers...")

        for i, tid in enumerate(ids_list):
            await progress.set_message(f"Track {i + 1}/{total} (id={tid})")
            result = await svc.analyze_track(tid, analyzers=analyzers_list, force=force)
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
    analysis = await tiered.ensure_level(ids_list, target, force=force)
    await progress.increment(total)
    return {
        "total_tracks": total,
        "completed": analysis["analyzed"],
        "failed": analysis["failed"],
        "skipped": analysis["skipped"],
        "level": level,
    }


@tool(tags={ToolCategory.AUDIO.value}, timeout=ToolTimeout.BATCH)
@map_domain_errors
async def separate_stems(
    track_id: int | None = None,
    track_query: str | None = None,
    stems: Any = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ML-based stem separation (vocals, drums, bass, other). Requires ``[stems]`` extra."""
    stems_list = ensure_list(stems) or None
    ensure_reference(track_id, track_query, entity_name="track")

    if stems_list:
        invalid = set(stems_list) - _VALID_STEMS
        if invalid:
            raise ToolError(f"Invalid stems: {sorted(invalid)}. Valid: {sorted(_VALID_STEMS)}")

    return {
        "track_id": track_id,
        "track_query": track_query,
        "stems_requested": stems_list or sorted(_VALID_STEMS),
        "status": "stub",
        "output_files": {},
        "note": "Requires [stems] extra: uv sync --extra stems",
    }
