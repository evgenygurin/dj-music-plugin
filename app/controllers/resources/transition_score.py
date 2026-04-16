"""Transition score resource — cached compatibility score between two tracks."""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp.dependencies import Depends
from fastmcp.resources import resource

from app.controllers.dependencies import get_feature_repo
from app.controllers.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ICON_SETS,
    RESOURCE_META,
)
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
)
async def transition_score(
    from_id: Annotated[int, "Source track ID"],
    to_id: Annotated[int, "Destination track ID"],
    feat_repo: FeatureRepository = Depends(get_feature_repo),  # noqa: B008
) -> dict[str, Any]:
    """Get transition compatibility score between two tracks."""
    features_map = await feat_repo.get_scoring_features_batch([from_id, to_id])

    if from_id not in features_map or to_id not in features_map:
        missing = [tid for tid in (from_id, to_id) if tid not in features_map]
        return {
            "from_id": from_id,
            "to_id": to_id,
            "score": None,
            "error": f"Missing features for track(s): {missing}",
        }

    scorer = TransitionScorer()
    result = scorer.score(features_map[from_id], features_map[to_id])

    if result.hard_reject:
        return {
            "from_id": from_id,
            "to_id": to_id,
            "score": 0.0,
            "hard_reject": True,
            "reject_reason": result.reject_reason,
        }

    return {
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
