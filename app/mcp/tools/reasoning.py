"""DJ-specific reasoning tools: suggest, explain, replace, compare, quick review.

Thin wrappers calling ReasoningService via Depends().
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.mcp.dependencies import get_reasoning_service
from app.services.reasoning_service import ReasoningService


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def suggest_next_track(
    set_id: int,
    after_position: int,
    count: int = 5,
    prefer_mood: str | None = None,
    energy_direction: str = "any",
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Suggest best tracks for a set position, scored against both neighbors."""
    return await svc.suggest_next_track(
        set_id=set_id,
        after_position=after_position,
        count=count,
    )


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def explain_transition(
    from_track_id: int,
    to_track_id: int,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Explain why a transition works or doesn't — 5-component breakdown."""
    return await svc.explain_transition(from_track_id, to_track_id)


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def find_replacement(
    set_id: int,
    position: int,
    count: int = 5,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find replacement tracks for a set position, scored against both neighbors."""
    return {
        "set_id": set_id,
        "position": position,
        "candidates": [],
        "note": "Full replacement engine requires Sub-Project #5 (transition scoring)",
    }


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def compare_set_versions(
    set_id: int,
    version_a: int | None = None,
    version_b: int | None = None,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Compare two versions of a set: tracks added/removed, score changes."""
    return await svc.compare_set_versions(
        set_id=set_id,
        version_a=version_a,
        version_b=version_b,
    )


@tool(tags={"sets"}, annotations={"readOnlyHint": True})
async def quick_set_review(
    set_id: int,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Complete set review in one call: tracks, weak transitions, problems."""
    return await svc.quick_set_review(set_id)
