"""Import & download tools (2 tools, tag: discovery).

Thin wrappers calling :class:`ImportService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_import_tracks_workflow
from app.controllers.tools._shared import (
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_list
from app.services.workflows.import_tracks_workflow import ImportTracksWorkflow


@tool(
    title="Import Tracks",
    tags={ToolCategory.DISCOVERY.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def import_tracks(
    track_refs: Any = None,
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    workflow: ImportTracksWorkflow = Depends(get_import_tracks_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Import YM track IDs into local DB. Idempotent — skips existing.

    Returns ``id_mapping`` (ym_id → local_id) for all refs. If
    ``playlist_id`` is given, tracks are appended to that playlist.
    If ``auto_analyze=True``, runs L3 tiered analysis on imported tracks.
    """
    log = ToolContext(ctx)
    refs = ensure_list(track_refs)
    if not refs:
        raise ToolError("track_refs is required (list of YM track IDs)")

    return await workflow.import_tracks(
        track_refs=[str(ref) for ref in refs],
        playlist_id=playlist_id,
        auto_analyze=auto_analyze,
        log=log,
    )


@tool(
    title="Download Tracks",
    tags={ToolCategory.DISCOVERY.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_DISCOVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def download_tracks(
    track_refs: Any = None,
    target_dir: str | None = None,
    skip_existing: bool = True,
    prefer_bitrate: int = 320,
    workflow: ImportTracksWorkflow = Depends(get_import_tracks_workflow),  # noqa: B008
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

    return await workflow.download_tracks(
        track_refs=[str(ref) for ref in refs],
        target_dir=target_dir,
        skip_existing=skip_existing,
        prefer_bitrate=prefer_bitrate,
        log=log,
    )
