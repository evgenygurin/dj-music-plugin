"""Audit iter 6: ``TrackFeaturesFilter`` rejected ``key_code__in`` even
though key-based queries are central to DJ scoring.

Same class as Bug A (TrackFilter underspec): the schema only declared
``track_id``, ``analysis_level``, ``bpm``, and ``mood`` lookups.
``key_code`` is the input to every harmonic compatibility check;
without ``__eq/in/range`` lookups the filter API can't answer "find
all tracks in 8A and 8B" without a follow-up Python filter.

Add the missing key_code lookups + integrated_lufs (loudness queries).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_features import TrackFeaturesFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("key_code__eq", 14),
        ("key_code__in", [13, 14]),
        ("key_code__range", [10, 14]),
        ("integrated_lufs__gte", -14.0),
        ("integrated_lufs__lte", -8.0),
        ("integrated_lufs__range", [-14.0, -8.0]),
    ],
)
def test_track_features_filter_accepts_key_and_lufs_lookups(lookup: str, value: object) -> None:
    TrackFeaturesFilter.model_validate({lookup: value})


def test_track_features_filter_still_rejects_garbage() -> None:
    with pytest.raises(ValidationError):
        TrackFeaturesFilter.model_validate({"bogus_field__eq": 1})
