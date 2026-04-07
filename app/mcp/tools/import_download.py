"""Import & download tools (2 tools, tag: discovery).

Thin wrappers calling :class:`ImportService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.core.parsing import ensure_list
from app.mcp.dependencies import get_import_service
from app.mcp.tools._shared import (
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.services.import_service import ImportService

_IMPORT_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "idempotentHint": True}
_DOWNLOAD_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "openWorldHint": True}


@tool(tags={ToolCategory.DISCOVERY.value}, annotations=_IMPORT_ANNOTATIONS)
@map_domain_errors
async def import_tracks(
    track_refs: Any = None,
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    svc: ImportService = Depends(get_import_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Idempotent — skips existing."""
    log = ToolContext(ctx)
    refs = ensure_list(track_refs)
    if not refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    result = await svc.import_tracks(track_refs=[str(ref) for ref in refs])

    await log.info(
        f"Import complete: {result['imported']} new, "
        f"{result['skipped']} skipped, {result['enriched']} enriched"
    )

    if playlist_id:
        result["playlist_note"] = "Use manage_playlist(add_tracks) to add to playlist"
    if auto_analyze:
        result["auto_analyze_note"] = "Use analyze_batch to trigger audio analysis"
    return result


@tool(
    tags={ToolCategory.DISCOVERY.value},
    annotations=_DOWNLOAD_ANNOTATIONS,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def download_tracks(
    track_refs: Any = None,
    target_dir: str | None = None,
    skip_existing: bool = True,
    prefer_bitrate: int = 320,
    svc: ImportService = Depends(get_import_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Download MP3 from YM and link to the local library.

    ``track_refs`` accepts local track IDs (``"1"``, ``"42"``) or YM IDs
    (``"12345678"``, ``"ym:12345678"``). Local IDs are resolved via
    ``track_external_ids``. Files are persisted as :class:`DjLibraryItem`
    records so ``analyze_track`` can find them.

    ``target_dir`` defaults to ``settings.ym_library_path``.
    ``skip_existing`` skips paths that already exist.
    ``prefer_bitrate`` selects download bitrate (320 / 192 / 128).
    """
    log = ToolContext(ctx)
    refs = ensure_list(track_refs)
    if not refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    total = len(refs)
    await log.info(f"Starting download of {total} tracks...")

    result = await svc.download_tracks(
        track_refs=[str(ref) for ref in refs],
        target_dir=target_dir,
        skip_existing=skip_existing,
        prefer_bitrate=prefer_bitrate,
    )

    await log.progress(total, total)
    await log.info(
        f"Done: {result['downloaded']} downloaded, {result['skipped']} skipped, "
        f"{result['linked_to_library']} linked, {result['failed']} failed"
    )
    return result
