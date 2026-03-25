"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via `unlock_tools(action="unlock", category="audio")`.

All audio tools run as background tasks with progress reporting.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastmcp.dependencies import Progress
from fastmcp.server.context import Context
from fastmcp.server.tasks import TaskConfig

from app.config import settings
from app.server import mcp

# ── 1. analyze_track ───────────────────────────────


@mcp.tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    task=TaskConfig(
        mode="optional",
        poll_interval=timedelta(seconds=settings.task_poll_interval_seconds),
    ),
    timeout=120.0,
)
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: list[str] | None = None,
    force: bool = False,
    progress: Progress = Progress(),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline on a single track.

    analyzers: list of analyzer names (None = all available).
    force: re-analyze even if features already exist.

    Runs as background task when client requests it, with progress reporting.
    """
    if track_id is None and track_query is None:
        return {"error": "Provide track_id or track_query"}

    await progress.set_total(100)
    await progress.set_message(f"Starting analysis for track {track_id or track_query}")

    # Stub — real implementation needs audio files + pipeline
    # Simulated progress stages
    await progress.increment(20)
    await progress.set_message("Loading audio file...")

    await progress.increment(30)
    await progress.set_message("Running analyzers...")

    await progress.increment(40)
    await progress.set_message("Computing features...")

    await progress.increment(10)
    await progress.set_message("Analysis complete")

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


@mcp.tool(
    tags={"audio"},
    annotations={"idempotentHint": True},
    task=TaskConfig(
        mode="optional",  # can run sync or background
        poll_interval=timedelta(seconds=settings.task_poll_interval_seconds),
    ),
    timeout=600.0,
)
async def analyze_batch(
    track_ids: list[int] | None = None,
    playlist_id: int | None = None,
    analyzers: list[str] | None = None,
    priority: str = "normal",
    progress: Progress = Progress(),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch audio analysis for multiple tracks or a playlist.

    Provide track_ids or playlist_id (not both).
    priority: low | normal | high.

    Recommended to run as background task for large batches.
    """
    if track_ids is None and playlist_id is None:
        return {"error": "Provide track_ids or playlist_id"}
    if track_ids is not None and playlist_id is not None:
        return {"error": "Provide track_ids or playlist_id, not both"}

    valid_priorities = ("low", "normal", "high")
    if priority not in valid_priorities:
        return {"error": f"Invalid priority: {priority}. Valid: {', '.join(valid_priorities)}"}

    total = len(track_ids) if track_ids else 0

    # Set up progress tracking
    await progress.set_total(total if total > 0 else 100)
    await progress.set_message(f"Starting batch analysis of {total} tracks...")

    # Stub — real implementation would:
    # 1. Resolve playlist_id → track_ids if needed
    # 2. For each track:
    #    - await progress.set_message(f"Analyzing {track.title}")
    #    - Run pipeline
    #    - await progress.increment()
    # 3. Return final results

    completed = 0
    failed = 0
    skipped = 0

    await progress.set_message("Analysis complete (stub)")

    return {
        "track_ids": track_ids,
        "playlist_id": playlist_id,
        "analyzers_requested": analyzers or "all",
        "priority": priority,
        "total_tracks": total,
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "note": "Stub — audio files required for real analysis",
    }


# ── 3. separate_stems ─────────────────────────────


@mcp.tool(
    tags={"audio"},
    task=TaskConfig(
        mode="required",  # stem separation is always slow, require background
        poll_interval=timedelta(seconds=10),  # longer poll interval
    ),
    timeout=300.0,
)
async def separate_stems(
    track_id: int | None = None,
    track_query: str | None = None,
    stems: list[str] | None = None,
    progress: Progress = Progress(),
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ML-based stem separation (vocals, drums, bass, other).

    stems: list of stems to extract (None = all). Options: vocals, drums, bass, other.

    Always runs as background task (ML inference is slow).
    """
    if track_id is None and track_query is None:
        return {"error": "Provide track_id or track_query"}

    valid_stems = {"vocals", "drums", "bass", "other"}
    if stems:
        invalid = set(stems) - valid_stems
        if invalid:
            return {"error": f"Invalid stems: {sorted(invalid)}. Valid: {sorted(valid_stems)}"}

    requested_stems = stems or sorted(valid_stems)
    await progress.set_total(len(requested_stems))
    await progress.set_message(f"Loading ML model for stem separation...")

    # Stub — real implementation would:
    # for stem in requested_stems:
    #     await progress.set_message(f"Separating {stem}...")
    #     # run demucs model
    #     await progress.increment()

    await progress.set_message("Stem separation complete (stub)")

    return {
        "track_id": track_id,
        "track_query": track_query,
        "stems_requested": requested_stems,
        "status": "stub",
        "output_files": {},
        "note": "Stub — ML stem separation model required",
    }
