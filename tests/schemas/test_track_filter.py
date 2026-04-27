"""Regression tests for ``TrackFilter`` lookup coverage.

Audit (2026-04-27) found ``TrackFilter`` declared only 7 explicit
lookups (id__in, id__eq, title__icontains, status__eq/in,
duration_ms__gte/lte) and rejected common Django-style probes that
docs claim are supported across all entities (id__gt/lt/gte/lte,
title__contains, has_features).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track import TrackFilter


@pytest.mark.parametrize(
    "lookup",
    [
        "id__gt",
        "id__gte",
        "id__lt",
        "id__lte",
    ],
)
def test_track_filter_accepts_id_range_lookups(lookup: str) -> None:
    """`id__gt/gte/lt/lte` are required by paging/range queries."""
    TrackFilter.model_validate({lookup: 100})


def test_track_filter_accepts_title_contains() -> None:
    """Case-sensitive `title__contains` complements `title__icontains`."""
    TrackFilter.model_validate({"title__contains": "Liebing"})


def test_track_filter_accepts_has_features_true() -> None:
    """`has_features` magic boolean filter is documented in repositories.md.

    Schema must accept it so the entity_list dispatcher's Pydantic
    validation step doesn't strip it before the repository sees it.
    """
    TrackFilter.model_validate({"has_features": True})


def test_track_filter_accepts_has_features_false() -> None:
    TrackFilter.model_validate({"has_features": False})


def test_track_filter_still_rejects_garbage() -> None:
    """Coverage is widened, not loosened — strict ``extra="forbid"`` stays."""
    with pytest.raises(ValidationError):
        TrackFilter.model_validate({"definitely_not_a_field": 42})
