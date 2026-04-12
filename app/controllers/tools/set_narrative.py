"""MCP tools — set narrative analysis (Phase 5)."""

from __future__ import annotations

from typing import Any

from fastmcp.dependencies import Depends
from fastmcp.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies.db import get_db_session
from app.controllers.tools._shared.errors import map_domain_errors
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_SETS,
    TOOL_META,
    ToolCategory,
)
from app.db.repositories.set import SetRepository
from app.services.set_narrative import SetNarrativeEngine


def _get_set_repo(session: AsyncSession = Depends(get_db_session)) -> SetRepository:  # noqa: B008
    return SetRepository(session)


@tool(
    title="Analyze Set Narrative",
    tags={ToolCategory.SETS.value, "memory"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=TOOL_META,
)
@map_domain_errors
async def analyze_set_narrative(
    set_id: int,
    repo: SetRepository = Depends(_get_set_repo),  # noqa: B008
) -> dict[str, Any]:
    """Analyze a set's narrative structure — phases, flow, variety, arc.

    Returns phase breakdown (opening/building/tension/peak/release/closing),
    quality scores (flow, variety, arc), and actionable suggestions.
    Use after build_set to evaluate narrative quality.
    """
    from app.db.repositories.feature import FeatureRepository

    set_obj = await repo.get_by_id(set_id)
    if set_obj is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("DjSet", set_id)

    # Get latest version tracks
    versions = await repo.get_versions(set_id)
    if not versions:
        return {"error": "no versions"}

    latest = versions[0]
    items = await repo.get_version_items(latest.id)

    if not items:
        return {"error": "no tracks in version"}

    # Build track data for narrative analysis
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
