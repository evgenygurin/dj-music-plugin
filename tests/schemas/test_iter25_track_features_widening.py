"""Audit iter 25: TrackFeaturesFilter scalar + confidence widening."""

from __future__ import annotations

import pytest

from app.schemas.track_features import TrackFeaturesFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("mood_confidence__gte", 0.1),
        ("mood_confidence__lte", 0.5),
        ("mood__isnull", True),
        ("energy_mean__gte", 0.4),
        ("energy_mean__lte", 0.8),
        ("spectral_centroid_hz__gte", 1500),
        ("spectral_centroid_hz__lte", 3500),
        ("hp_ratio__gte", 1.0),
        ("hp_ratio__lte", 3.0),
        ("kick_prominence__gte", 0.5),
        ("kick_prominence__lte", 0.9),
    ],
)
def test_track_features_filter_accepts_scalar_lookups(lookup: str, value: object) -> None:
    TrackFeaturesFilter.model_validate({lookup: value})
