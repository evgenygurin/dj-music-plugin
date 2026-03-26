"""Import & download tools (2 tools, tag: discovery).

Thin wrappers calling ImportService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_import_service
from app.services.import_service import ImportService

# ── 1. import_tracks ─────────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "idempotentHint": True},
)
async def import_tracks(
    track_refs: Any = None,
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    svc: ImportService = Depends(get_import_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Accepts strings or ints. Idempotent — skips existing."""
    from app.core.parsing import ensure_list

    track_refs = ensure_list(track_refs)
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    result = await svc.import_tracks(track_refs=[str(ref) for ref in track_refs])

    if ctx:
        await ctx.info(
            f"Import complete: {result['imported']} new, "
            f"{result['skipped']} skipped, {result['enriched']} enriched"
        )

    if playlist_id:
        result["playlist_note"] = "Use manage_playlist(add_tracks) to add to playlist"
    if auto_analyze:
        result["auto_analyze_note"] = "Use analyze_batch to trigger audio analysis"
    return result


# ── 2. download_tracks ───────────────────────────────


@tool(
    tags={"discovery"},
    annotations={"readOnlyHint": False, "openWorldHint": True},
    timeout=600.0,
    task=True,
)
async def download_tracks(
    track_refs: Any = None,
    target_dir: str | None = None,
    skip_existing: bool = True,
    prefer_bitrate: int = 320,
    svc: ImportService = Depends(get_import_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM and link to library. Accepts YM track IDs.

    Downloads files, creates DjLibraryItem records (so analyze_track finds them).
    target_dir: where to save (default: settings.ym_library_path).
    skip_existing: skip if file already exists.
    prefer_bitrate: target bitrate in kbps (320, 192, 128).
    """
    from app.core.parsing import ensure_list

    track_refs = ensure_list(track_refs)
    if not track_refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    total = len(track_refs)
    if ctx:
        await ctx.info(f"Starting download of {total} tracks...")

    result = await svc.download_tracks(
        track_refs=[str(ref) for ref in track_refs],
        target_dir=target_dir,
        skip_existing=skip_existing,
        prefer_bitrate=prefer_bitrate,
    )

    if ctx:
        await ctx.report_progress(total, total)
        await ctx.info(
            f"Done: {result['downloaded']} downloaded, {result['skipped']} skipped, "
            f"{result['linked_to_library']} linked, {result['failed']} failed"
        )

    return result
