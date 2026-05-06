"""Audit iter 22: TransitionFilter component scores + fx_type;
TransitionHistoryFilter duration_sec."""

from __future__ import annotations

import pytest

from app.schemas.transition import TransitionFilter
from app.schemas.transition_history import TransitionHistoryFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("bpm_score__gte", 0.9),
        ("harmonics_score__lte", 0.5),
        ("energy_score__gte", 0.7),
        ("bass_score__lte", 0.6),
        ("drums_score__gte", 0.8),
        ("vocals_score__lte", 0.4),
        ("fx_type__eq", "long_blend"),
        ("fx_type__in", ["bass_swap_short", "echo_out"]),
    ],
)
def test_transition_filter_accepts_component_score_lookups(lookup: str, value: object) -> None:
    TransitionFilter.model_validate({lookup: value})


def test_transition_history_filter_accepts_duration_lookups() -> None:
    TransitionHistoryFilter.model_validate({"duration_sec__gte": 60})
    TransitionHistoryFilter.model_validate({"duration_sec__range": [30, 90]})
