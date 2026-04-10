"""Sync tools — bidirectional playlist sync with Yandex Music (2 tools).

Thin wrappers calling :class:`SyncService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_sync_playlist_workflow
from app.controllers.tools._shared import ToolCategory, map_domain_errors
from app.services.workflows.sync_playlist_workflow import SyncPlaylistWorkflow

_SYNC_ANNOTATIONS: dict[str, bool] = {"readOnlyHint": False, "openWorldHint": True}


@tool(tags={ToolCategory.SYNC.value}, annotations=_SYNC_ANNOTATIONS)
@map_domain_errors
async def sync_playlist(
    playlist_id: int,
    direction: str = "pull",
    conflict_strategy: str = "source_wins",
    dry_run: bool = True,
    workflow: SyncPlaylistWorkflow = Depends(get_sync_playlist_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Sync local playlist with Yandex Music.

    ``direction`` ∈ ``{pull, push, diff}``; ``dry_run`` is ``True`` by default.
    """
    del ctx
    return await workflow.sync_playlist(
        playlist_id=playlist_id,
        direction=direction,
        conflict_strategy=conflict_strategy,
        dry_run=dry_run,
    )


@tool(tags={ToolCategory.SYNC.value}, annotations=_SYNC_ANNOTATIONS)
@map_domain_errors
async def push_set_to_ym(
    set_id: int,
    ym_playlist_name: str | None = None,
    mode: str = "auto",
    workflow: SyncPlaylistWorkflow = Depends(get_sync_playlist_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Push DJ set as YM playlist. ``mode`` ∈ ``{create, update, auto}``."""
    del ctx
    return await workflow.push_set_to_ym(
        set_id=set_id,
        ym_playlist_name=ym_playlist_name,
        mode=mode,
    )
