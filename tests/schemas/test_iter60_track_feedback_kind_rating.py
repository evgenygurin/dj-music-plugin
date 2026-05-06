"""Smoke test 2026-05-07: ``TrackFeedbackCreate`` after schema sync.

The prior ``kind`` (``like``/``ban``/``rate``) triplet was retired
when prod schema turned out to use ``status``
(``active``/``liked``/``banned``/``archived``) with a non-null
``rating`` defaulting to 3. Cross-field rules are now schema-enforced
(CHECK constraints in DB + Literal in Pydantic), so this file holds
only the behavioural sanity tests.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_feedback import TrackFeedbackCreate


class TestStatusEnum:
    def test_default_status_active(self) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146})
        assert c.status == "active"
        assert c.rating == 3

    @pytest.mark.parametrize("status", ["active", "liked", "banned", "archived"])
    def test_known_status_values_accepted(self, status: str) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146, "status": status})
        assert c.status == status

    def test_unknown_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "status": "bogus"})


class TestRatingBoundsStillEnforced:
    def test_rating_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "rating": 0})

    def test_rating_above_five_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "rating": 6})

    def test_notes_independently_optional(self) -> None:
        c = TrackFeedbackCreate.model_validate(
            {"track_id": 146, "status": "liked", "notes": "hot track"}
        )
        assert c.notes == "hot track"


class TestCounters:
    def test_play_count_round_trips(self) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146, "play_count": 12})
        assert c.play_count == 12

    def test_skip_count_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "skip_count": -1})
