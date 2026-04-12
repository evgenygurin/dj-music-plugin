"""Delivery & export tools (2 tools, tag: delivery).

Thin wrappers calling :class:`DeliveryService` via ``Depends()``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_deliver_set_workflow
from app.controllers.tools._shared import (
    ANNOTATIONS_WRITE,
    ANNOTATIONS_WRITE_OPEN_WORLD,
    ICON_DELIVERY,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_dict, ensure_list
from app.services.workflows.deliver_set_workflow import DeliverSetWorkflow


@tool(
    title="Deliver Set",
    tags={ToolCategory.DELIVERY.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_DELIVERY,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def deliver_set(
    set_id: int,
    version: str | None = None,
    output_dir: str | None = None,
    copy_files: bool = True,
    sync_to_ym: bool = False,
    formats: Any = None,
    dry_run: bool = False,
    workflow: DeliverSetWorkflow = Depends(get_deliver_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Multi-stage set delivery: score transitions, copy files, generate exports."""
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


@tool(
    title="Export Set",
    tags={ToolCategory.DELIVERY.value},
    annotations=ANNOTATIONS_WRITE,
    icons=ICON_DELIVERY,
    meta=TOOL_META,
)
@map_domain_errors
async def export_set(
    set_id: int,
    format: str = "m3u8",
    output_path: str | None = None,
    rekordbox_options: Any = None,
    workflow: DeliverSetWorkflow = Depends(get_deliver_set_workflow),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Export set to format: ``m3u8``, ``rekordbox``, ``json``, ``cheatsheet``."""
    del ctx
    return await workflow.export_set(
        set_id=set_id,
        format=format,
        output_path=output_path,
        rekordbox_options=ensure_dict(rekordbox_options),
    )
