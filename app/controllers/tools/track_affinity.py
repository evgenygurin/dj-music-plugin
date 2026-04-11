"""MCP tools — track affinity (AI set builder Phase 2)."""

from __future__ import annotations

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from app.db.repositories.track_affinity import TrackAffinityRepository
from app.schemas.track_affinity import AffinityRecommendation
from app.services.track_affinity import TrackAffinityService


def _get_svc(session: AsyncSession = Depends(get_db_session)) -> TrackAffinityService:  # noqa: B008
    return TrackAffinityService(TrackAffinityRepository(session))


@tool(tags={ToolCategory.CORE.value, "memory"})
@map_domain_errors
async def refresh_affinity(
    svc: TrackAffinityService = Depends(_get_svc),
) -> dict[str, int]:
    """Rebuild track affinity matrix from transition_history.

    Aggregates all transition history into pair-level sentiment scores.
    Run after a listening session to update affinity data.
    """
    count = await svc.refresh()
    return {"pairs_updated": count}


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_track_affinity(
    track_a_id: int,
    track_b_id: int,
    svc: TrackAffinityService = Depends(_get_svc),
) -> dict:
    """Get affinity data for a specific track pair."""
    result = await svc.get_pair(track_a_id, track_b_id)
    if result is None:
        return {"found": False, "track_a_id": track_a_id, "track_b_id": track_b_id}
    return {"found": True, **result}


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_affinity_recommendations(
    track_id: int,
    limit: int = 10,
    svc: TrackAffinityService = Depends(_get_svc),
) -> list[AffinityRecommendation]:
    """Top-N tracks with best proven chemistry for a given track.

    Based on historical transition outcomes — play count, likes, bans.
    Use alongside suggest_next_track for best results.
    """
    pairs = await svc.get_recommendations(track_id, limit)
    return [AffinityRecommendation.model_validate(p) for p in pairs]
