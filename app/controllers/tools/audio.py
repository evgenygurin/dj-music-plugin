"""Audio analysis tools — hidden by default (6 tools, tag: audio).

Unlock via ``unlock_tools(action="unlock", category="audio")``.

Tools:
- analyze_track — single track analysis (tiered or custom analyzers)
- analyze_batch — batch analysis with progress
- classify_track — mood/subgenre classification for one track
- gate_track — quality gate check for one track
- get_similar_tracks — YM similar tracks with filters
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.exceptions import NotFoundError as FastMCPNotFoundError
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field

from app.config import settings
from app.controllers.dependencies import (
    get_analyze_track_workflow,
    get_audio_service,
    get_track_service,
)
from app.controllers.dependencies.external import get_music_provider
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_AUDIO,
    TOOL_META,
    ToolCategory,
    ToolContext,
    ToolTimeout,
    map_domain_errors,
    resolve_track_id,
)
from app.core.utils.filters import is_excluded_title
from app.core.utils.parsing import ensure_list
from app.providers.protocol import MusicProvider
from app.services.audio_service import AudioService
from app.services.track_service import TrackService
from app.services.workflows.analyze_track_workflow import AnalyzeTrackWorkflow


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
    track_id: Annotated[int | None, Field(description="Local track ID")] = None,
    track_query: Annotated[str | None, Field(description="Text search to resolve track")] = None,
    analyzers: Annotated[
        list[str] | None, Field(description="Specific analyzers to run (default: all)")
    ] = None,
    force: Annotated[bool, Field(description="Re-analyze even if results exist")] = False,
    level: Annotated[
        int,
        Field(description="Analysis level: 2=TRIAGE, 3=SCORING, 4=TRANSITION", ge=2, le=5),
    ] = 3,
    workflow: AnalyzeTrackWorkflow = Depends(get_analyze_track_workflow),  # noqa: B008
    track_svc: TrackService = Depends(get_track_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Runs tiered or custom-pipeline audio analysis for one resolved track. Use when scoring, triage, or transition prep needs up-to-date features. ``level`` 2-5 maps TRIAGE through ADVANCED; explicit ``analyzers`` selects the local-file pipeline instead of tiered."""
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
)
@map_domain_errors
async def analyze_batch(
    track_ids: Annotated[list[int] | None, Field(description="Track IDs to analyze")] = None,
    playlist_id: Annotated[
        int | None, Field(description="Analyze all tracks in this playlist")
    ] = None,
    batch_size: Annotated[int, Field(description="Max tracks per batch", ge=1)] = 20,
    analyzers: Annotated[
        list[str] | None, Field(description="Specific analyzers to run (default: tiered path)")
    ] = None,
    level: Annotated[
        int,
        Field(description="Analysis level: 2=TRIAGE, 3=SCORING, 4=TRANSITION", ge=2, le=5),
    ] = 3,
    force: Annotated[bool, Field(description="Re-analyze even if results exist")] = False,
    workflow: AnalyzeTrackWorkflow = Depends(get_analyze_track_workflow),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Runs analysis across track IDs or a whole playlist in batches with progress reporting. Use when bulk-refreshing many tracks; ``level`` and ``analyzers`` behave like ``analyze_track``."""

    async def _report(current: int, total: int) -> None:
        await ctx.report_progress(current, total)

    return await workflow.analyze_batch(
        track_ids=ensure_list(track_ids) or None,
        playlist_id=playlist_id,
        batch_size=batch_size,
        analyzers=ensure_list(analyzers) or None,
        level=level,
        force=force,
        on_progress=_report,
    )


@tool(
    title="Classify Track",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def classify_track(
    track_id: Annotated[int, Field(description="Local track ID")],
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
) -> dict[str, Any]:
    """Classifies mood/subgenre from stored audio features and persists labels. Use when labeling tracks that already have features; run ``analyze_track`` first if analysis is missing."""
    result = await svc.classify_track(track_id)
    if result.get("status") == "error" and result.get("error") == "No features":
        raise FastMCPNotFoundError(
            f"No audio features for track {track_id}. Run analyze_track first."
        )
    return result


@tool(
    title="Gate Track",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def gate_track(
    track_id: Annotated[int, Field(description="Local track ID")],
    criteria: Annotated[
        dict[str, float] | None, Field(description="Numeric thresholds for quality gates")
    ] = None,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
) -> dict[str, Any]:
    """Evaluates one track against numeric quality gates and returns pass/fail with reasons. Use when gatekeeping library additions or pre-export checks."""
    return await svc.gate_track(track_id, criteria=criteria)


@tool(
    title="Get Similar Tracks",
    tags={ToolCategory.AUDIO.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def get_similar_tracks(
    ym_track_id: Annotated[str, Field(description="Yandex Music track ID")],
    limit: Annotated[int, Field(description="Max similar tracks after filtering", ge=1)] = 20,
    min_duration_ms: Annotated[
        int | None, Field(description="Minimum track duration (ms)")
    ] = None,
    max_duration_ms: Annotated[
        int | None, Field(description="Maximum track duration (ms)")
    ] = None,
    genre_filter: Annotated[list[str] | None, Field(description="Genre whitelist")] = None,
    genre_blacklist: Annotated[list[str] | None, Field(description="Genre blacklist")] = None,
    exclude_patterns: Annotated[
        list[str] | None, Field(description="Title patterns to exclude")
    ] = None,
    provider: MusicProvider = Depends(get_music_provider),  # noqa: B008
) -> dict[str, Any]:
    """Fetches Yandex Music similar tracks for a seed and applies duration, genre, and title filters. Use when discovering candidates from an existing YM track."""
    raw_similar = await provider.get_similar(ym_track_id)

    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms
    bad_genres = [b.strip().lower() for b in settings.discovery_bad_genres.split(",")]

    filtered: list[dict[str, Any]] = []
    for t in raw_similar:
        dur = t.duration_ms or 0
        if dur and (dur < min_dur or dur > max_dur):
            continue
        if is_excluded_title(t.title, exclude_patterns):
            continue
        genre = (t.album_genre or "").lower()
        if genre_filter and genre not in [g.lower() for g in genre_filter]:
            continue
        if genre_blacklist:
            if genre and genre in [b.lower() for b in genre_blacklist]:
                continue
        elif genre and genre in bad_genres:
            continue
        filtered.append(
            {
                "ym_id": t.id,
                "title": t.title,
                "artists": t.artist_names,
                "duration_ms": t.duration_ms,
                "album_id": t.album_id or "",
                "album_genre": t.album_genre or "",
            }
        )
        if len(filtered) >= limit:
            break

    return {
        "ym_track_id": ym_track_id,
        "total_raw": len(raw_similar),
        "after_filter": len(filtered),
        "similar": filtered,
    }
