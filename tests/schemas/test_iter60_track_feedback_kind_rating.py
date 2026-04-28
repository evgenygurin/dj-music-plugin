"""Audit iter 60 (T-58): ``TrackFeedbackCreate`` had no cross-field
validation between ``kind`` and ``rating``. The strict semantic is:

- ``kind="rate"`` → ``rating`` REQUIRED (1-5)
- ``kind="like"`` → ``rating`` MUST be absent (binary signal)
- ``kind="ban"``  → ``rating`` MUST be absent (binary signal)

Without this, ``entity_create(track_feedback, {kind:"rate"})``
persisted with ``rating=null`` (a "rate" with no rating);
``{kind:"like", rating:5}`` persisted a stray rating next to a
binary like. Both forms break downstream consumers.

Now ``model_validator(mode="after")`` enforces the pairing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_feedback import TrackFeedbackCreate


class TestKindRatePairing:
    def test_rate_with_rating_accepted(self) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "rate", "rating": 5})
        assert c.rating == 5

    def test_rate_without_rating_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"kind='rate' requires a rating"):
            TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "rate"})


class TestKindLikePairing:
    def test_like_without_rating_accepted(self) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "like"})
        assert c.rating is None

    def test_like_with_rating_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"kind='like' is binary"):
            TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "like", "rating": 5})


class TestKindBanPairing:
    def test_ban_without_rating_accepted(self) -> None:
        c = TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "ban"})
        assert c.rating is None

    def test_ban_with_rating_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"kind='ban' is binary"):
            TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "ban", "rating": 3})


class TestRatingBoundsStillEnforced:
    """Sanity: existing ge=1 / le=5 bounds still fire (kind='rate'
    case, where rating is supplied)."""

    def test_rating_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "rate", "rating": 0})

    def test_rating_above_five_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeedbackCreate.model_validate({"track_id": 146, "kind": "rate", "rating": 6})

    def test_notes_independently_optional(self) -> None:
        c = TrackFeedbackCreate.model_validate(
            {"track_id": 146, "kind": "like", "notes": "hot track"}
        )
        assert c.notes == "hot track"
