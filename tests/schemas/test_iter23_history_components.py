"""Audit iter 23: TransitionHistoryFilter component scores +
tempo_match_ratio - mirrors the symmetry added to TransitionFilter
in v1.2.22.
"""

from __future__ import annotations

import pytest

from app.schemas.transition_history import TransitionHistoryFilter


@pytest.mark.parametrize(
    "lookup,value",
    [
        ("bpm_score__gte", 0.7),
        ("harmonics_score__lte", 0.4),
        ("energy_score__gte", 0.5),
        ("bass_score__lte", 0.5),
        ("drums_score__gte", 0.6),
        ("vocals_score__lte", 0.5),
        ("tempo_match_ratio__gte", 0.95),
    ],
)
def test_transition_history_filter_accepts_component_lookups(lookup: str, value: object) -> None:
    TransitionHistoryFilter.model_validate({lookup: value})
