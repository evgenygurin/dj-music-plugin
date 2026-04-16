"""DJ-specific reasoning tools: suggest, explain, replace, compare, quick review, narrative.

Thin wrappers calling :class:`ReasoningService` / :class:`SetNarrativeEngine`
via ``Depends()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp.dependencies import CurrentContext, Depends
from fastmcp.server.context import Context
from fastmcp.tools import tool
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_reasoning_service
from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared import (
    ANNOTATIONS_READ_ONLY,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
    map_domain_errors,
)
from app.db.repositories.set import SetRepository
from app.services.reasoning_service import ReasoningService
from app.services.set_narrative import SetNarrativeEngine


def _get_set_repo(session: AsyncSession = Depends(get_db_session)) -> SetRepository:  # noqa: B008
    return SetRepository(session)


@tool(
    title="Suggest Next Track",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def suggest_next_track(
    set_id: Annotated[int, Field(description="DJ set ID")],
    after_position: Annotated[int, Field(description="0-based position after which to suggest")],
    count: Annotated[int, Field(description="Number of suggestions to return", ge=1)] = 5,
    prefer_mood: Annotated[str | None, Field(description="Filter by subgenre mood")] = None,
    energy_direction: Annotated[
        Literal["up", "down", "any"], Field(description="Energy direction bias")
    ] = "any",
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Suggests ranked next tracks after a slot using neighbor-aware transition scoring. Use when extending a set with mood or energy-direction bias."""
    return await svc.suggest_next_track(
        set_id=set_id,
        after_position=after_position,
        count=count,
        prefer_mood=prefer_mood,
        energy_direction=energy_direction,
    )


@tool(
    title="Explain Transition",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def explain_transition(
    from_track_id: Annotated[int, Field(description="Outgoing local track ID")],
    to_track_id: Annotated[int, Field(description="Incoming local track ID")],
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Explains transition quality with a per-component score breakdown. Use when debugging a blend or understanding why a pair passes or fails."""
    return await svc.explain_transition(from_track_id, to_track_id)


@tool(
    title="Find Replacement",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def find_replacement(
    set_id: Annotated[int, Field(description="DJ set ID")],
    position: Annotated[int, Field(description="0-based slot to replace")],
    count: Annotated[int, Field(description="Number of replacement candidates", ge=1)] = 5,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Finds replacement candidates for one slot scored against adjacent tracks. Use when swapping a weak track without rebuilding the whole set."""
    return await svc.find_replacement(
        set_id=set_id,
        position=position,
        count=count,
    )


@tool(
    title="Compare Versions",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def compare_set_versions(
    set_id: Annotated[int, Field(description="DJ set ID")],
    version_a: Annotated[int | None, Field(description="First version number to compare")] = None,
    version_b: Annotated[int | None, Field(description="Second version number to compare")] = None,
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Compares two set versions for track churn and transition-score deltas. Use when reviewing what changed between rebuilds or edits."""
    return await svc.compare_set_versions(
        set_id=set_id,
        version_a=version_a,
        version_b=version_b,
    )


@tool(
    title="Quick Set Review",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def quick_set_review(
    set_id: Annotated[int, Field(description="DJ set ID")],
    svc: ReasoningService = Depends(get_reasoning_service),  # noqa: B008
    ctx: Context = CurrentContext(),  # noqa: B008
) -> dict[str, Any]:
    """Returns tracks, weak transitions, and problem flags in one pass. Use when doing a fast QA sweep before export or playback."""
    return await svc.quick_set_review(set_id)


@tool(
    title="Analyze Set Narrative",
    tags={ToolCategory.SETS.value},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def analyze_set_narrative(
    set_id: Annotated[int, Field(description="DJ set ID to analyze")],
    repo: SetRepository = Depends(_get_set_repo),  # noqa: B008
) -> dict[str, Any]:
    """Analyzes narrative arc, phases, variety, and flow from stored track features. Use when evaluating story quality after ``build_set`` or before narrative tweaks."""
    from app.db.repositories.feature import FeatureRepository

    set_obj = await repo.get_by_id(set_id)
    if set_obj is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("DjSet", set_id)

    versions = await repo.get_latest_versions(set_id)
    if not versions:
        return {"error": "no versions"}

    latest = versions[0]
    items = await repo.get_version_items(latest.id)

    if not items:
        return {"error": "no tracks in version"}

    feature_repo = FeatureRepository(repo.session)
    track_ids = [item.track_id for item in items]
    features_map = await feature_repo.get_scoring_features_batch(track_ids)

    total = len(items)
    tracks_data = []
    for i, item in enumerate(items):
        feat = features_map.get(item.track_id)
        tracks_data.append(
            {
                "position": i / max(1, total - 1),
                "title": f"Track {item.track_id}",
                "bpm": feat.bpm if feat else None,
                "energy_lufs": feat.integrated_lufs if feat else None,
                "mood": feat.mood if feat and hasattr(feat, "mood") else None,
            }
        )

    engine = SetNarrativeEngine()
    return engine.analyze_narrative(tracks_data, set_obj.template_name)
