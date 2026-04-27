"""Audit iter 54 (T-52): three relational schemas accepted "from track
to itself" / "track paired with itself" rows that are logically
meaningless:

- ``TransitionCreate``           (from_track_id == to_track_id)
- ``TransitionHistoryCreate``    (from_track_id == to_track_id)
- ``TrackAffinityCreate``        (track_a_id  == track_b_id)

Live confirmation:

    entity_create(transition, {"from_track_id":146,"to_track_id":146})
      -> 200 OK with overall=0.93 (track scored against itself)
    entity_create(transition_history, {"from_track_id":146,"to_track_id":146})
      -> 200 OK

Now ``model_validator(mode="after")`` rejects same-id endpoints with
a clean message at schema-validation time.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_affinity import TrackAffinityCreate
from app.schemas.transition import TransitionCreate
from app.schemas.transition_history import TransitionHistoryCreate


class TestTransitionCreateDistinctEndpoints:
    def test_self_pair_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"must differ"):
            TransitionCreate.model_validate({"from_track_id": 146, "to_track_id": 146})

    def test_distinct_pair_accepted(self) -> None:
        c = TransitionCreate.model_validate({"from_track_id": 146, "to_track_id": 147})
        assert c.from_track_id != c.to_track_id


class TestTransitionHistoryCreateDistinctEndpoints:
    def test_self_pair_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"must differ"):
            TransitionHistoryCreate.model_validate({"from_track_id": 42, "to_track_id": 42})

    def test_distinct_pair_accepted(self) -> None:
        TransitionHistoryCreate.model_validate(
            {"from_track_id": 42, "to_track_id": 43, "user_reaction": "positive"}
        )


class TestTrackAffinityCreateDistinctEndpoints:
    def test_self_pair_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"must differ"):
            TrackAffinityCreate.model_validate({"track_a_id": 7, "track_b_id": 7})

    def test_distinct_pair_accepted(self) -> None:
        a = TrackAffinityCreate.model_validate(
            {"track_a_id": 7, "track_b_id": 8, "avg_score": 0.6}
        )
        assert a.track_a_id != a.track_b_id
