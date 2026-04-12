"""MCP tools — per-track persistent feedback (Phase 3)."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_WRITE_DESTRUCTIVE,
    ANNOTATIONS_WRITE_IDEMPOTENT,
    ICON_MEMORY,
    TOOL_META,
    ToolCategory,
)
from app.db.repositories.track_feedback import TrackFeedbackRepository
from app.schemas.track_feedback import TrackFeedbackRead


def _get_repo(session: AsyncSession = Depends(get_db_session)) -> TrackFeedbackRepository:  # noqa: B008
    return TrackFeedbackRepository(session)


@tool(
    title="Like Track",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def like_track(
    track_id: int,
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> TrackFeedbackRead:
    """Mark a track as liked. Liked tracks get priority in set building."""
    entry = await repo.upsert(track_id, status="liked", rating=5)
    return TrackFeedbackRead.model_validate(entry)


@tool(
    title="Ban Track",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_WRITE_DESTRUCTIVE,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def ban_track(
    track_id: int,
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> TrackFeedbackRead:
    """Ban a track. Banned tracks are excluded from all future sets."""
    entry = await repo.upsert(track_id, status="banned", rating=1)
    return TrackFeedbackRead.model_validate(entry)


@tool(
    title="Rate Track",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_WRITE_IDEMPOTENT,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def rate_track(
    track_id: int,
    rating: int,
    notes: str | None = None,
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> TrackFeedbackRead:
    """Rate a track 1-5. Higher ratings boost the track in set building.

    Args:
        track_id: Track to rate.
        rating: 1 (terrible) to 5 (amazing).
        notes: Optional freeform notes about the track.
    """
    entry = await repo.upsert(track_id, rating=rating, notes=notes)
    return TrackFeedbackRead.model_validate(entry)


@tool(
    title="Get Track Feedback",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def get_track_feedback(
    track_id: int,
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> dict:
    """Get feedback for a track (rating, status, play/skip counts)."""
    entry = await repo.get_by_track(track_id)
    if entry is None:
        return {"found": False, "track_id": track_id}
    return {"found": True, **TrackFeedbackRead.model_validate(entry).model_dump()}


@tool(
    title="Get Banned Tracks",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def get_banned_tracks(
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> list[int]:
    """Get all banned track IDs. Use to exclude from set building."""
    return await repo.get_banned_ids()


@tool(
    title="Get Liked Tracks",
    tags={ToolCategory.CORE.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_MEMORY,
    meta=TOOL_META,
)
@map_domain_errors
async def get_liked_tracks(
    repo: TrackFeedbackRepository = Depends(_get_repo),  # noqa: B008
) -> list[int]:
    """Get all liked track IDs. Use to prioritize in set building."""
    return await repo.get_liked_ids()
