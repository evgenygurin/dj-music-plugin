"""Audit iter 6: ``TrackFeedbackFilter`` rejected ``rating__gte`` even
though "find tracks rated >= 4" is the canonical feedback query.

Same class as Bug A: declared lookups < documented contract.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_feedback import TrackFeedbackFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("rating__eq", 5),
        ("rating__gte", 4),
        ("rating__lte", 2),
        ("rating__in", [4, 5]),
        ("status__in", ["liked", "active"]),
    ],
)
def test_track_feedback_filter_accepts_rating_and_status_in(lookup: str, value: object) -> None:
    """``kind__in`` was retired with the 2026-05-07 schema sync; the
    canonical "find recently engaged tracks" query now goes through
    ``status__in`` (active / liked / banned / archived)."""
    TrackFeedbackFilter.model_validate({lookup: value})


def test_track_feedback_filter_still_rejects_garbage() -> None:
    with pytest.raises(ValidationError):
        TrackFeedbackFilter.model_validate({"bogus": 1})
