"""Audio analysis tools — hidden by default (3 tools, tag: audio).

These tools require explicit unlock via
``unlock_tools(action="unlock", category="audio")``.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends, Progress
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import (
    get_analyze_track_workflow,
    get_track_service,
)
from app.controllers.tools._shared import (
    ToolCategory,
    ToolContext,
    ToolTimeout,
    ensure_reference,
    map_domain_errors,
    resolve_track_id,
)
from app.core.utils.parsing import ensure_list
from app.services.track_service import TrackService
from app.services.workflows.analyze_track_workflow import AnalyzeTrackWorkflow

_VALID_STEMS = frozenset({"vocals", "drums", "bass", "other"})


@tool(
    title="Analyze Track",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_AUDIO,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def analyze_track(
    track_id: int | None = None,
    track_query: str | None = None,
    analyzers: Any = None,
    force: bool = False,
    level: int = 3,
    workflow: AnalyzeTrackWorkflow = Depends(get_analyze_track_workflow),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis on a track. Default: L3 SCORING via TieredPipeline.

    ``level``: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    If ``analyzers`` is set explicitly, uses the local file pipeline
    instead of the tiered path.
    """
    log = ToolContext(ctx)
    analyzers_list = ensure_list(analyzers) or None
    resolved_id = await resolve_track_id(
        entity_id=track_id, query=track_query, search=track_svc.search
    )
    return await workflow.analyze_track(
        track_id=resolved_id,
        analyzers=analyzers_list,
        force=force,
        level=level,
        log=log,
    )


@tool(
    title="Analyze Batch",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_AUDIO,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
    task=True,
)
@map_domain_errors
async def analyze_batch(
    track_ids: Any = None,
    playlist_id: int | None = None,
    batch_size: int = 20,
    analyzers: Any = None,
    level: int = 3,
    force: bool = False,
    workflow: AnalyzeTrackWorkflow = Depends(get_analyze_track_workflow),  # noqa: B008
    progress: Progress = Progress(),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Batch audio analysis. Default: L3 SCORING, 20 tracks per batch.

    ``level``: 2=TRIAGE, 3=SCORING (default), 4=TRANSITION, 5=ADVANCED.
    ``batch_size``: max tracks per batch (default 20).
    If ``analyzers`` is set explicitly, uses the local file pipeline
    instead of the tiered path.
    """
    del ctx
    return await workflow.analyze_batch(
        track_ids=ensure_list(track_ids) or None,
        playlist_id=playlist_id,
        batch_size=batch_size,
        analyzers=ensure_list(analyzers) or None,
        level=level,
        force=force,
        progress=progress,
    )


@tool(
    title="Separate Stems",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_WRITE_OPEN_WORLD,
    icons=ICON_AUDIO,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def separate_stems(
    track_id: int | None = None,
    track_query: str | None = None,
    stems: Any = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """ML-based stem separation (vocals, drums, bass, other). Requires ``[stems]`` extra."""
    stems_list = ensure_list(stems) or None
    ensure_reference(track_id, track_query, entity_name="track")

    if stems_list:
        invalid = set(stems_list) - _VALID_STEMS
        if invalid:
            raise ToolError(f"Invalid stems: {sorted(invalid)}. Valid: {sorted(_VALID_STEMS)}")

    return {
        "track_id": track_id,
        "track_query": track_query,
        "stems_requested": stems_list or sorted(_VALID_STEMS),
        "status": "stub",
        "output_files": {},
        "note": "Requires [stems] extra: uv sync --extra stems",
    }
