"""Atomic audio tools — one operation per track (tag: atomic, hidden).

Unlock via ``unlock_tools(action="unlock", category="atomic")``.
Composites (``analyze_batch``, ``classify_mood``, ...) call these
internally.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.config import settings
from app.controllers.dependencies import get_audio_service, get_ym_client
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_AUDIO,
    TOOL_META,
    ToolCategory,
    ToolTimeout,
    map_domain_errors,
)
from app.core.utils.parsing import ensure_list
from app.services.audio_service import AudioService
from app.ym.client import YandexMusicClient
from app.ym.filters import genre_ok, is_excluded_title, ym_track_summary


@tool(
    title="Analyze One Track",
    tags={ToolCategory.ATOMIC.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_AUDIO,
    meta=TOOL_META,
    timeout=ToolTimeout.BATCH,
)
@map_domain_errors
async def analyze_one_track(
    track_id: int,
    analyzers: Any = None,
    force: bool = False,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline on ONE track. Saves features to DB."""
    analyzers_list = ensure_list(analyzers) or None
    result = await svc.analyze_track(track_id, analyzers=analyzers_list, force=force)

    status = result.get("status")
    err = result.get("error") or ""
    if status == "error" and err == "Track not found":
        raise ToolError(f"Track {track_id} not found")
    if status == "error" and "No audio file" in err:
        raise ToolError(f"No audio file for track {track_id}")
    if status == "error" and ("not found" in err.lower() or "iCloud stub" in err):
        raise ToolError(err)

    return result


@tool(
    title="Classify One Track",
    tags={ToolCategory.ATOMIC.value},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def classify_one_track(
    track_id: int,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Classify ONE track mood/subgenre and SAVE to DB."""
    result = await svc.classify_track(track_id)

    if result.get("status") == "error" and result.get("error") == "No features":
        raise ToolError(f"No audio features for track {track_id}. Run analyze_one_track first.")
    return result


@tool(
    title="Gate One Track",
    tags={ToolCategory.ATOMIC.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def gate_one_track(
    track_id: int,
    criteria: dict[str, float] | None = None,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Check ONE track against audio quality criteria. Returns pass/fail + reasons."""
    return await svc.gate_track(track_id, criteria=criteria)


@tool(
    title="Get Similar One Track",
    tags={ToolCategory.ATOMIC.value},
    annotations=ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    icons=ICON_AUDIO,
    meta=TOOL_META,
)
@map_domain_errors
async def get_similar_one_track(
    ym_track_id: str,
    limit: int = 20,
    min_duration_ms: int | None = None,
    max_duration_ms: int | None = None,
    genre_filter: list[str] | None = None,
    genre_blacklist: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    ym: YandexMusicClient = Depends(get_ym_client),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get similar tracks from YM for ONE track ID. Raw YM API with filters."""
    raw_similar = await ym.get_similar(ym_track_id)

    min_dur = min_duration_ms or settings.discovery_min_duration_ms
    max_dur = max_duration_ms or settings.discovery_max_duration_ms

    filtered: list[dict[str, Any]] = []
    for t in raw_similar:
        dur = t.duration_ms or 0
        if dur and (dur < min_dur or dur > max_dur):
            continue
        if is_excluded_title(t.title, exclude_patterns):
            continue
        if not genre_ok(t.albums or [], whitelist=genre_filter, blacklist=genre_blacklist):
            continue
        filtered.append(ym_track_summary(t))
        if len(filtered) >= limit:
            break

    return {
        "ym_track_id": ym_track_id,
        "total_raw": len(raw_similar),
        "after_filter": len(filtered),
        "similar": filtered,
    }
