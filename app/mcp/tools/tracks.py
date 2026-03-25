"""Track tools — list, get, manage, features (4 tools, tag: core).

Thin wrappers calling TrackService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import PaginatedResponse, TrackBrief, TrackStandard
from app.mcp.dependencies import get_db_session, get_track_service
from app.models.audio import TrackSection
from app.services.track_service import TrackService


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def list_tracks(
    limit: int = 20,
    cursor: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> PaginatedResponse[TrackBrief]:
    """List tracks with optional filters and cursor pagination."""
    if bpm_min is not None or bpm_max is not None:
        page = await svc.filter_by_features(
            bpm_min=bpm_min, bpm_max=bpm_max, limit=limit, cursor=cursor
        )
    else:
        page = await svc.list_all(limit=limit, cursor=cursor)

    return PaginatedResponse[TrackBrief](
        items=[svc.to_brief(t) for t in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
    )


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_track(
    id: int | None = None,
    query: str | None = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Get full track details by id or text query."""
    if id is None and query is None:
        raise ToolError("Provide id or query")

    if id is not None:
        track, features = await svc.get_with_features(id)
    else:
        results = await svc.search(query, limit=1)  # type: ignore[arg-type]
        if not results:
            raise ToolError("Track not found")
        track, features = await svc.get_with_features(results[0].id)

    return svc.to_standard(track, features)


@tool(tags={"core"}, annotations={"readOnlyHint": False})
async def manage_tracks(
    action: str,
    data: Any = None,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
) -> TrackStandard:
    """Create, update, archive, or unarchive a track. action: create|update|archive|unarchive."""
    from app.core.parsing import ensure_dict

    data = ensure_dict(data)
    if action not in ("create", "update", "archive", "unarchive"):
        raise ToolError(f"Unknown action: {action}")

    if action == "create":
        if not data or "title" not in data:
            raise ToolError("data.title required for create")
        track = await svc.create(data["title"], data.get("duration_ms"))
        return svc.to_standard(track)

    track_id = (data or {}).get("id")
    if track_id is None:
        raise ToolError("data.id required")

    if action == "archive":
        track = await svc.archive(track_id)
    elif action == "unarchive":
        track = await svc.unarchive(track_id)
    elif action == "update" and data:
        fields = {k: v for k, v in data.items() if k != "id"}
        track = await svc.update(track_id, **fields)
    else:
        raise ToolError("Unreachable")

    return svc.to_standard(track)


@tool(tags={"core"}, annotations={"readOnlyHint": True})
async def get_track_features(
    id: int | None = None,
    query: str | None = None,
    include_sections: bool = False,
    svc: TrackService = Depends(get_track_service),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> dict[str, Any]:
    """Get audio features for a track by id or query. Optionally include sections."""
    if id is None and query is None:
        raise ToolError("Provide id or query")

    if id is not None:
        track, features = await svc.get_with_features(id)
    else:
        results = await svc.search(query, limit=1)  # type: ignore[arg-type]
        if not results:
            raise ToolError("Track not found")
        track, features = await svc.get_with_features(results[0].id)

    if features is None:
        return {"track_id": track.id, "title": track.title, "has_features": False}

    response: dict[str, Any] = {
        "track_id": track.id,
        "title": track.title,
        "has_features": True,
        "tempo": {"bpm": features.bpm, "confidence": features.bpm_confidence},
        "loudness": {"integrated_lufs": features.integrated_lufs},
        "energy": {"mean": features.energy_mean, "max": features.energy_max},
        "spectral": {
            "centroid_hz": features.spectral_centroid_hz,
            "flatness": features.spectral_flatness,
        },
        "key": {"key_code": features.key_code, "confidence": features.key_confidence},
        "rhythm": {"kick_prominence": features.kick_prominence, "onset_rate": features.onset_rate},
        "mood": features.mood,
    }

    if include_sections:
        result = await session.execute(
            select(TrackSection)
            .where(TrackSection.track_id == track.id)
            .order_by(TrackSection.start_ms)
        )
        response["sections"] = [
            {"type": s.section_type, "start_ms": s.start_ms, "end_ms": s.end_ms}
            for s in result.scalars().all()
        ]

    return response

