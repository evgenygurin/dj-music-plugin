"""Audit iter 24: ScoringProfileFilter weight lookups."""

from __future__ import annotations

import pytest

from app.schemas.scoring_profile import ScoringProfileFilter


@pytest.mark.parametrize(
    "lookup",
    [
        "bpm_weight__gte",
        "harmonics_weight__lte",
        "energy_weight__gte",
        "bass_weight__lte",
        "drums_weight__gte",
        "vocals_weight__lte",
    ],
)
def test_scoring_profile_filter_accepts_weight_lookups(lookup: str) -> None:
    ScoringProfileFilter.model_validate({lookup: 0.2})


def test_scoring_profile_filter_accepts_id_lookups() -> None:
    ScoringProfileFilter.model_validate({"id__eq": 1})
    ScoringProfileFilter.model_validate({"id__in": [1, 2]})
