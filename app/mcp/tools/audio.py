"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via `unlock_tools(action="unlock", category="audio")`.
"""

from __future__ import annotations

from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

# ── 1. analyze_track ───────────────────────────────


@tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    timeout=120.0,
)
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: list[str] | None = None,
    force: bool = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline on a single track.

    analyzers: list of analyzer names (None = all available).
    force: re-analyze even if features already exist.
    """
    if track_id is None and track_query is None:
        raise ToolError("Provide track_id or track_query")

    # Stub — real implementation needs audio files + pipeline
    return {
        "track_id": track_id,
        "track_query": track_query,
        "analyzers_requested": analyzers or "all",
        "force": force,
        "status": "stub",
        "features": {},
        "errors": [],
        "note": "Stub — audio files required for real analysis",
    }


# ── 2. analyze_batch ──────────────────────────────


@tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    timeout=600.0,
    task=True,
)
async def analyze_batch(
    track_ids: list[int] | None = None,
    playlist_id: int | None = None,
    analyzers: list[str] | None = None,
    priority: str = "normal",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch audio analysis for multiple tracks or a playlist.

    Provide track_ids or playlist_id (not both).
    priority: low | normal | high.
    """
    if track_ids is None and playlist_id is None:
        raise ToolError("Provide track_ids or playlist_id")
    if track_ids is not None and playlist_id is not None:
        raise ToolError("Provide track_ids or playlist_id, not both")

    valid_priorities = ("low", "normal", "high")
    if priority not in valid_priorities:
        raise ToolError(f"Invalid priority: {priority}. Valid: {', '.join(valid_priorities)}")

    total = len(track_ids) if track_ids else 0

    if ctx:
        await ctx.report_progress(0, total or 1)
        await ctx.info(f"Batch analysis requested: {total} tracks, priority={priority}")

    # Stub — real implementation needs audio files + pipeline
    if ctx:
        await ctx.report_progress(total or 1, total or 1)

    return {
        "track_ids": track_ids,
        "playlist_id": playlist_id,
        "analyzers_requested": analyzers or "all",
        "priority": priority,
        "total_tracks": total,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "note": "Stub — audio files required for real analysis",
    }


# ── 3. separate_stems ─────────────────────────────


@tool(
    tags={"audio"},
    timeout=300.0,
)
async def separate_stems(
    track_id: int | None = None,
    track_query: str | None = None,
    stems: list[str] | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ML-based stem separation (vocals, drums, bass, other).

    stems: list of stems to extract (None = all). Options: vocals, drums, bass, other.
    """
    if track_id is None and track_query is None:
        raise ToolError("Provide track_id or track_query")

    valid_stems = {"vocals", "drums", "bass", "other"}
    if stems:
        invalid = set(stems) - valid_stems
        if invalid:
            raise ToolError(f"Invalid stems: {sorted(invalid)}. Valid: {sorted(valid_stems)}")

    # Stub — real implementation needs ML model + audio files
    return {
        "track_id": track_id,
        "track_query": track_query,
        "stems_requested": stems or sorted(valid_stems),
        "status": "stub",
        "output_files": {},
        "note": "Stub — ML stem separation model required",
    }
