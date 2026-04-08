"""Import & download tools (2 tools, tag: discovery).

Thin wrappers calling :class:`ImportService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.audio.level_config import AnalysisLevel
from app.core.parsing import ensure_list
from app.mcp.dependencies import get_import_service, get_tiered_pipeline
from app.mcp.tools._shared import (
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.services.import_service import ImportService
from app.services.tiered_pipeline import TieredPipeline

_IMPORT_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "idempotentHint": True}
_DOWNLOAD_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "openWorldHint": True}


@tool(
    tags={ToolCategory.DISCOVERY.value},
    annotations=_IMPORT_ANNOTATIONS,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def import_tracks(
    track_refs: Any = None,
    playlist_id: int | None = None,
    auto_analyze: bool = False,
    svc: ImportService = Depends(get_import_service),  # noqa: B008
    tiered: TieredPipeline = Depends(get_tiered_pipeline),  # noqa: B008
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

    result = await svc.import_tracks(
        track_refs=[str(ref) for ref in refs],
        playlist_id=playlist_id,
    )

    await log.info(
        f"Import complete: {result['imported']} new, "
        f"{result['skipped']} skipped, {result['enriched']} enriched"
    )
    if playlist_id is not None:
        await log.info(f"Added {result['playlist_added']} tracks to playlist {playlist_id}")

    if auto_analyze and result["id_mapping"]:
        local_ids = list(result["id_mapping"].values())
        await log.info(f"Running L3 tiered analysis on {len(local_ids)} tracks...")
        analysis = await tiered.ensure_level(local_ids, AnalysisLevel.SCORING)
        result["analysis"] = analysis

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
