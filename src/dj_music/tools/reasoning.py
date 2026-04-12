"""DJ-specific reasoning tools: suggest, explain, replace, compare, quick review.

Thin wrappers calling :class:`ReasoningService` via ``Depends()``. All
domain errors (``NotFoundError``, ``ValidationError``) are translated
to :class:`fastmcp.exceptions.ToolError` by the shared
:func:`map_domain_errors` decorator.
"""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool

from app.controllers.dependencies import get_reasoning_service
from dj_music.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ToolCategory,
    map_domain_errors,
)
from dj_music.services.reasoning_service import ReasoningService


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def suggest_next_track(
    set_id: int,
    after_position: int,
    count: int = 5,
    prefer_mood: str | None = None,
    energy_direction: str = "any",
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Suggest best tracks for a set position, scored against both neighbours.

    ``prefer_mood`` filters candidates by classified subgenre.
    ``energy_direction`` ∈ ``{up, down, any}`` nudges scoring toward
    higher or lower LUFS candidates (defaults to ``any``, no bias).
    """
    return await svc.suggest_next_track(
        set_id=set_id,
        after_position=after_position,
        count=count,
        prefer_mood=prefer_mood,
        energy_direction=energy_direction,
    )


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def explain_transition(
    from_track_id: int,
    to_track_id: int,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Explain why a transition works or does not — component breakdown."""
    return await svc.explain_transition(from_track_id, to_track_id)


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def find_replacement(
    set_id: int,
    position: int,
    count: int = 5,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Find replacement tracks for a set position, scored against both neighbours.

    Each candidate is scored against the prev *and* next track (whichever
    exist) using :class:`TransitionScorer`; hard-rejects on either side
    are dropped. Returns the top ``count`` ranked by average score.
    """
    return await svc.find_replacement(
        set_id=set_id,
        position=position,
        count=count,
    )


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
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


@tool(tags={ToolCategory.SETS.value}, annotations=ANNOTATIONS_READ_ONLY)
@map_domain_errors
async def quick_set_review(
    set_id: int,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Complete set review in one call: tracks, weak transitions, problems."""
    return await svc.quick_set_review(set_id)
