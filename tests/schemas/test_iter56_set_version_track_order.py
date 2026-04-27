"""Audit iter 56 (T-54): ``SetVersionCreate.track_order`` accepted
duplicates and single-track lists. Live confirmation:

    entity_create(set_version, {"set_id":5, "label":"x",
                                "track_order":[146, 147, 146]})
    -> 200 OK   ← persisted with track 146 played twice
    entity_create(set_version, {"set_id":5, "label":"y",
                                "track_order":[146]})
    -> 200 OK   ← single-track "set" with no transitions

A real DJ set never repeats a track and needs at least 2 tracks
to have any transitions. The dispatcher's downstream
``sequence_optimize`` and ``transition_score_pool`` already
reject duplicates — set creation was the missing link.

Now ``model_validator(mode="after")`` rejects both pathologies.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.set import SetVersionCreate


class TestSetVersionCreateTrackOrder:
    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"duplicate id"):
            SetVersionCreate.model_validate(
                {"set_id": 5, "label": "v1", "track_order": [146, 147, 146]}
            )

    def test_three_duplicates_rejected_with_full_list(self) -> None:
        with pytest.raises(ValidationError, match=r"\[146, 147\]"):
            SetVersionCreate.model_validate(
                {
                    "set_id": 5,
                    "label": "v1",
                    "track_order": [146, 147, 146, 147, 148],
                }
            )

    def test_single_track_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"at least 2"):
            SetVersionCreate.model_validate({"set_id": 5, "label": "v1", "track_order": [146]})

    def test_empty_track_order_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"at least 2"):
            SetVersionCreate.model_validate({"set_id": 5, "label": "v1", "track_order": []})

    def test_two_unique_tracks_accepted(self) -> None:
        c = SetVersionCreate.model_validate(
            {"set_id": 5, "label": "v1", "track_order": [146, 147]}
        )
        assert c.track_order == [146, 147]

    def test_long_unique_track_order_accepted(self) -> None:
        c = SetVersionCreate.model_validate(
            {"set_id": 5, "label": "v1", "track_order": list(range(146, 156))}
        )
        assert len(c.track_order) == 10
