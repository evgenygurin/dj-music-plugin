"""MCP tools — adaptive energy arc (Phase 4)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import ANNOTATIONS_READ_ONLY, ToolCategory
from app.db.repositories.transition_history import TransitionHistoryRepository
from app.services.adaptive_arc import AdaptiveArcService


def _get_svc(session: AsyncSession = Depends(get_db_session)) -> AdaptiveArcService:  # noqa: B008
    return AdaptiveArcService(TransitionHistoryRepository(session))


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_energy_trend(
    last_n: int = 10,
    svc: AdaptiveArcService = Depends(_get_svc),
) -> dict[str, str]:
    """Analyze recent transitions to determine energy direction.

    Returns 'rising', 'falling', 'plateau', or 'unknown'.
    Use before suggest_next_track to inform energy_direction param.
    """
    trend = await svc.get_energy_trend(last_n)
    return {"trend": trend}


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def suggest_energy_direction(
    last_n: int = 10,
    svc: AdaptiveArcService = Depends(_get_svc),
) -> dict[str, Any]:
    """Suggest what energy direction the next track should take.

    Analyzes recent likes/skips and score trends to recommend
    'ramp_up', 'maintain', or 'any'. Feed into build_set or
    suggest_next_track energy_direction parameter.
    """
    return await svc.suggest_energy_direction(last_n)


@tool(tags={ToolCategory.CORE.value, "memory"}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def get_session_arc(
    limit: int = 50,
    svc: AdaptiveArcService = Depends(_get_svc),
) -> list[dict[str, Any]]:
    """Get the energy arc of the current session.

    Returns chronological list of transitions with position (0-1),
    score, style, and user reaction. Visualize to understand
    the session's energy flow.
    """
    return await svc.compute_preferred_arc(limit=limit)
