"""Import & download tools (2 tools, tag: discovery).

Thin wrappers calling :class:`ImportService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_import_tracks_workflow
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_DISCOVERY,
    TOOL_META,
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
    track_refs: Annotated[
        str | list[str] | None, Field(description="YM track IDs to import")
    ] = None,
    playlist_id: Annotated[
        int | None, Field(description="Append imported tracks to this playlist")
    ] = None,
    auto_analyze: Annotated[bool, Field(description="Run L3 analysis after import")] = False,
    workflow: Annotated[
        ImportTracksWorkflow,
        Field(description="Injected import-tracks workflow."),
    ] = Depends(get_import_tracks_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="MCP context for logging and progress reporting."),
    ] = None,
) -> dict[str, Any]:
    """Imports Yandex Music track IDs into the local library with optional playlist append and analysis. Use when onboarding tracks after search or discovery."""
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
)
@map_domain_errors
async def download_tracks(
    track_refs: Annotated[
        str | list[str] | None,
        Field(description="Track IDs (local or YM) to download"),
    ] = None,
    target_dir: Annotated[
        str | None, Field(description="Download directory (default: library path)")
    ] = None,
    skip_existing: Annotated[bool, Field(description="Skip already downloaded files")] = True,
    prefer_bitrate: Annotated[int, Field(description="Preferred bitrate: 128, 192, or 320")] = 320,
    workflow: Annotated[
        ImportTracksWorkflow,
        Field(description="Injected import-tracks workflow."),
    ] = Depends(get_import_tracks_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="MCP context for logging and progress reporting."),
    ] = None,
) -> dict[str, Any]:
    """Downloads MP3s for local or YM track references into the library or a target folder. Use when preparing files for analysis or offline playback."""
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
