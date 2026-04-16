"""Delivery tools (1 tool, tag: delivery).

Thin wrapper calling :class:`DeliverSetWorkflow` via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.controllers.dependencies import get_deliver_set_workflow
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_DELIVERY,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_list
from app.services.workflows.deliver_set_workflow import DeliverSetWorkflow


@tool(
    title="Deliver Set",
    tags={ToolCategory.DELIVERY.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_DELIVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def deliver_set(
    set_id: Annotated[int, Field(description="DJ set ID")],
    version: Annotated[str | None, Field(description="Set version label (optional)")] = None,
    output_dir: Annotated[str | None, Field(description="Output directory for exports")] = None,
    copy_files: Annotated[
        bool, Field(description="Copy audio files into output directory")
    ] = True,
    sync_to_ym: Annotated[
        bool, Field(description="Sync resulting playlist to Yandex Music")
    ] = False,
    formats: Annotated[
        list[str] | None,
        Field(description="Export formats: m3u8, rekordbox, json, cheatsheet"),
    ] = None,
    dry_run: Annotated[
        bool, Field(description="Preview without writing files or syncing")
    ] = False,
    workflow: DeliverSetWorkflow = Depends(get_deliver_set_workflow),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Runs the delivery pipeline for a set: transitions, exports, optional file copy, and optional YM sync. Use when shipping a set to decks, files, or streaming."""
    return await workflow.deliver_set(
        set_id=set_id,
        version=version,
        output_dir=output_dir,
        copy_files=copy_files,
        sync_to_ym=sync_to_ym,
        formats=ensure_list(formats) or None,
        dry_run=dry_run,
        log=ToolContext(ctx),
    )
