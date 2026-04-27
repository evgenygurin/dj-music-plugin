"""Audit iter 38 (T-36): TransitionView and TransitionFilter were
under-specified relative to the underlying ``transitions`` table.

The ``transitions`` model persists 7 columns that the View dropped
on the floor — ``key_distance_weighted``, ``low_conflict_score``,
``transition_bars``, ``overlap_ms``, ``from_section_id``,
``to_section_id``, ``transition_recipe_json``. Some of them
(``transition_bars`` and ``transition_recipe_json``) are even
write-able via ``TransitionUpdate`` — i.e. callers could write but
not read back what they wrote.

Filter side: missing ``id__eq/in/gt/lt/gte/lte`` (canonical
"load these specific scored pairs" query), plus no lookups on the
two compound scores or the mix-execution metadata columns.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.transition import TransitionFilter, TransitionView


class TestTransitionViewExposesPersistedColumns:
    def test_key_distance_weighted_round_trips(self) -> None:
        view = TransitionView.model_validate(
            {"id": 1, "from_track_id": 1, "to_track_id": 2, "key_distance_weighted": 1.5}
        )
        assert view.key_distance_weighted == 1.5

    def test_low_conflict_score_round_trips(self) -> None:
        view = TransitionView.model_validate(
            {"id": 1, "from_track_id": 1, "to_track_id": 2, "low_conflict_score": 0.3}
        )
        assert view.low_conflict_score == 0.3

    def test_transition_bars_round_trips(self) -> None:
        view = TransitionView.model_validate(
            {"id": 1, "from_track_id": 1, "to_track_id": 2, "transition_bars": 32}
        )
        assert view.transition_bars == 32

    def test_section_anchors_round_trip(self) -> None:
        view = TransitionView.model_validate(
            {
                "id": 1,
                "from_track_id": 1,
                "to_track_id": 2,
                "from_section_id": 11,
                "to_section_id": 22,
            }
        )
        assert view.from_section_id == 11
        assert view.to_section_id == 22

    def test_overlap_ms_round_trips(self) -> None:
        view = TransitionView.model_validate(
            {"id": 1, "from_track_id": 1, "to_track_id": 2, "overlap_ms": 16000}
        )
        assert view.overlap_ms == 16000

    def test_recipe_json_round_trips(self) -> None:
        view = TransitionView.model_validate(
            {
                "id": 1,
                "from_track_id": 1,
                "to_track_id": 2,
                "transition_recipe_json": '{"style":"BASS_SWAP_LONG"}',
            }
        )
        assert view.transition_recipe_json == '{"style":"BASS_SWAP_LONG"}'

    def test_all_new_fields_default_none(self) -> None:
        """Schema must not require any of the new fields."""
        view = TransitionView.model_validate({"id": 1, "from_track_id": 1, "to_track_id": 2})
        for f in (
            "key_distance_weighted",
            "low_conflict_score",
            "transition_bars",
            "from_section_id",
            "to_section_id",
            "overlap_ms",
            "transition_recipe_json",
        ):
            assert getattr(view, f) is None


class TestTransitionFilterIdLookups:
    def test_id_eq_accepted(self) -> None:
        TransitionFilter.model_validate({"id__eq": 42})

    def test_id_in_accepted(self) -> None:
        TransitionFilter.model_validate({"id__in": [1, 2, 3]})

    @pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
    def test_id_range_lookups(self, op: str) -> None:
        TransitionFilter.model_validate({f"id__{op}": 100})


class TestTransitionFilterMixMetadata:
    def test_transition_bars_eq(self) -> None:
        TransitionFilter.model_validate({"transition_bars__eq": 32})

    def test_transition_bars_in(self) -> None:
        TransitionFilter.model_validate({"transition_bars__in": [16, 32, 64]})

    def test_transition_bars_range(self) -> None:
        TransitionFilter.model_validate({"transition_bars__gte": 16, "transition_bars__lte": 64})

    def test_overlap_ms_range(self) -> None:
        TransitionFilter.model_validate({"overlap_ms__gte": 8000, "overlap_ms__lte": 32000})


class TestTransitionFilterCompoundScores:
    def test_key_distance_weighted_range(self) -> None:
        TransitionFilter.model_validate(
            {"key_distance_weighted__gte": 0.0, "key_distance_weighted__lte": 1.0}
        )

    def test_low_conflict_score_range(self) -> None:
        TransitionFilter.model_validate(
            {"low_conflict_score__gte": 0.0, "low_conflict_score__lte": 1.0}
        )


class TestTransitionFilterRejectsUnknown:
    def test_unknown_lookup_still_rejected(self) -> None:
        """The filter remains ``extra="forbid"`` — typos still caught."""
        with pytest.raises(ValidationError):
            TransitionFilter.model_validate({"id__contains": "foo"})
