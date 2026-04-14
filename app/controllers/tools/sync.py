"""Sync tools — bidirectional playlist sync with Yandex Music (2 tools).

Thin wrappers calling :class:`SyncService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_sync_playlist_workflow
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_SYNC,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.services.workflows.sync_playlist_workflow import SyncPlaylistWorkflow


@tool(
    title="Sync Playlist",
    tags={ToolCategory.SYNC.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_SYNC,
    meta=TOOL_META,
)
@map_domain_errors
async def sync_playlist(
    playlist_id: Annotated[int, Field(description="Local playlist ID")],
    direction: Annotated[
        Literal["pull", "push", "diff"], Field(description="Sync direction")
    ] = "pull",
    conflict_strategy: Annotated[
        Literal["source_wins", "target_wins", "manual"],
        Field(description="Conflict resolution"),
    ] = "source_wins",
    dry_run: Annotated[bool, Field(description="Preview without applying changes")] = True,
    workflow: Annotated[
        SyncPlaylistWorkflow,
        Field(description="Injected playlist sync workflow."),
    ] = Depends(get_sync_playlist_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="MCP context (unused; reserved for future logging)."),
    ] = None,
) -> dict[str, Any]:
    """Synchronizes a local playlist with Yandex Music via pull, push, or diff. Use when mirroring curation to or from YM or previewing conflicts before applying changes."""
    del ctx
    return await workflow.sync_playlist(
        playlist_id=playlist_id,
        direction=direction,
        conflict_strategy=conflict_strategy,
        dry_run=dry_run,
    )


@tool(
    title="Push Set to YM",
    tags={ToolCategory.SYNC.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_SYNC,
    meta=TOOL_META,
)
@map_domain_errors
async def push_set_to_ym(
    set_id: Annotated[int, Field(description="DJ set ID to push")],
    ym_playlist_name: Annotated[
        str | None, Field(description="Target YM playlist name (optional)")
    ] = None,
    mode: Annotated[Literal["create", "update", "auto"], Field(description="Push mode")] = "auto",
    workflow: Annotated[
        SyncPlaylistWorkflow,
        Field(description="Injected playlist sync workflow."),
    ] = Depends(get_sync_playlist_workflow),  # noqa: B008
    ctx: Annotated[
        Context | None,
        Field(description="MCP context (unused; reserved for future logging)."),
    ] = None,
) -> dict[str, Any]:
    """Publishes a DJ set as a Yandex Music playlist with create, update, or auto behavior. Use when exporting a finished set to your streaming library."""
    del ctx
    return await workflow.push_set_to_ym(
        set_id=set_id,
        ym_playlist_name=ym_playlist_name,
        mode=mode,
    )
