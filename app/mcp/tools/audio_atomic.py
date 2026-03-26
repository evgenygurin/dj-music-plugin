"""Atomic audio tools — one operation per one track (tag: atomic, hidden by default).

Unlock via: unlock_tools(action="unlock", category="atomic")
Composites (analyze_batch, classify_mood, gate_by_audio) call these internally.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.config import settings
from app.core.schemas import genre_ok, is_excluded_title, ym_track_summary
from app.mcp.dependencies import get_audio_service, get_ym_client
from app.services.audio_service import AudioService
from app.ym.client import YandexMusicClient

# ── 1. analyze_one_track ─────────────────────────────


@tool(tags={"atomic"}, annotations={"readOnlyHint": False}, timeout=180.0)
async def analyze_one_track(
    track_id: int,
    analyzers: Any = None,
    force: bool = False,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Run audio analysis pipeline on ONE track. Saves features to DB."""
    from app.core.parsing import ensure_list

    analyzers_list = ensure_list(analyzers) or None
    result = await svc.analyze_track(track_id, analyzers=analyzers_list, force=force)

    if result.get("status") == "error" and result.get("error") == "Track not found":
        raise ToolError(f"Track {track_id} not found")
    if result.get("status") == "error" and "No audio file" in result.get("error", ""):
        raise ToolError(f"No audio file for track {track_id}")
    if result.get("status") == "error" and "not found" in result.get("error", "").lower():
        raise ToolError(result["error"])
    if result.get("status") == "error" and "iCloud stub" in result.get("error", ""):
        raise ToolError(result["error"])

    return result


# ── 2. classify_one_track ────────────────────────────


@tool(tags={"atomic"}, annotations={"readOnlyHint": False})
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


# ── 3. gate_one_track ───────────────────────────────


@tool(tags={"atomic"}, annotations={"readOnlyHint": True})
async def gate_one_track(
    track_id: int,
    criteria: dict[str, float] | None = None,
    svc: AudioService = Depends(get_audio_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Check ONE track against audio quality criteria. Returns pass/fail + reasons."""
    return await svc.gate_track(track_id, criteria=criteria)


# ── 4. get_similar_one_track ────────────────────────


@tool(tags={"atomic"}, annotations={"readOnlyHint": True, "openWorldHint": True})
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

    filtered = []
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
