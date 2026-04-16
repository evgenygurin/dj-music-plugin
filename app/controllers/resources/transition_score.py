"""Transition resources — score and recipe details between track pairs."""

from __future__ import annotations

from typing import Annotated

from fastmcp.dependencies import Depends
from fastmcp.resources import ResourceResult, resource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.dependencies import get_db_session, get_feature_repo
from app.controllers.resources._shared import json_resource
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_SETS,
    RESOURCE_META,
    RESOURCE_VERSION,
)
from app.core.errors import NotFoundError
from app.db.models.transition import Transition
from app.db.repositories.feature import FeatureRepository
from app.transition.scorer import TransitionScorer


@resource(
    uri="transition://{from_id}/{to_id}/score",
    name="Transition Score",
    title="Transition Compatibility Score",
    description=(
        "Compatibility score between two tracks based on BPM, key, energy, "
        "and spectral similarity. Returns 0-1 score with component breakdown."
    ),
    mime_type="application/json",
    tags={"sets"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def transition_score(
    from_id: Annotated[int, "Source track ID"],
    to_id: Annotated[int, "Destination track ID"],
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> ResourceResult:
    """Get transition compatibility score between two tracks."""
    features_map = await feat_repo.get_scoring_features_batch([from_id, to_id])

    if from_id not in features_map or to_id not in features_map:
        missing = [tid for tid in (from_id, to_id) if tid not in features_map]
        return json_resource(
            {
                "from_id": from_id,
                "to_id": to_id,
                "score": None,
                "error": f"Missing features for track(s): {missing}",
            }
        )

    scorer = TransitionScorer()
    result = scorer.score(features_map[from_id], features_map[to_id])

    if result.hard_reject:
        return json_resource(
            {
                "from_id": from_id,
                "to_id": to_id,
                "score": 0.0,
                "hard_reject": True,
                "reject_reason": result.reject_reason,
            }
        )

    return json_resource(
        {
            "from_id": from_id,
            "to_id": to_id,
            "score": round(result.overall, 4),
            "components": {
                "bpm": round(result.bpm, 4),
                "harmonic": round(result.harmonic, 4),
                "energy": round(result.energy, 4),
                "spectral": round(result.spectral, 4),
                "groove": round(result.groove, 4),
                "timbral": round(result.timbral, 4),
            },
            "compatible": result.overall >= 0.5,
            "vocal_conflict": result.vocal_conflict,
            "drum_conflict": result.drum_conflict,
        }
    )


@resource(
    uri="transition://{from_id}/{to_id}/recipe",
    name="Transition Recipe",
    title="Transition Recipe",
    description="Stored transition recipe/FX details for a track pair, if available",
    mime_type="application/json",
    tags={"sets"},
    annotations=ANNOTATIONS_READ_ONLY,
    icons=ICON_SETS,
    meta=RESOURCE_META,
    version=RESOURCE_VERSION,
)
async def transition_recipe(
    from_id: Annotated[int, "Source track ID"],
    to_id: Annotated[int, "Destination track ID"],
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
    session: AsyncSession = Depends(get_db_session),  # noqa: B008
) -> ResourceResult:
    """Return persisted transition recipe fields for a pair."""
    # Validate both tracks are known to the system via existing scoring feature source.
    features_map = await feat_repo.get_scoring_features_batch([from_id, to_id])
    if from_id not in features_map or to_id not in features_map:
        missing = [tid for tid in (from_id, to_id) if tid not in features_map]
        raise NotFoundError("Track features", missing)

    transition = (
        await session.execute(
            select(Transition).where(
                Transition.from_track_id == from_id,
                Transition.to_track_id == to_id,
            )
        )
    ).scalar_one_or_none()

    data = {
        "from_id": from_id,
        "to_id": to_id,
        "exists": transition is not None,
        "recipe": (
            {
                "transition_id": transition.id,
                "overall_quality": transition.overall_quality,
                "hard_reject": transition.hard_reject,
                "reject_reason": transition.reject_reason,
                "fx_type": transition.fx_type,
                "transition_bars": transition.transition_bars,
                "transition_recipe_json": transition.transition_recipe_json,
            }
            if transition is not None
            else None
        ),
    }
    return json_resource(data)
