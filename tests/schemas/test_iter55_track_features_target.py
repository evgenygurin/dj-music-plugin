"""Audit iter 55 (T-53): ``TrackFeaturesCreate`` accepted payloads
with neither ``track_id`` nor ``track_ids`` set, leaking a bare
``KeyError: 'track_ids'`` from the analyze handler.

Live confirmation:

    entity_create(track_features, {"level": 3})
    -> Error calling tool 'entity_create': 'track_ids'

Now ``model_validator(mode="after")`` requires exactly one of the
two — mirrors the equivalent guard on ``AudioFileCreate``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.track_features import TrackFeaturesCreate


class TestTrackFeaturesCreateExactlyOneTarget:
    def test_neither_supplied_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"exactly one"):
            TrackFeaturesCreate.model_validate({"level": 3})

    def test_both_supplied_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"exactly one"):
            TrackFeaturesCreate.model_validate({"track_id": 1, "track_ids": [2, 3], "level": 3})

    def test_track_id_alone_accepted(self) -> None:
        c = TrackFeaturesCreate.model_validate({"track_id": 146})
        assert c.track_id == 146
        assert c.track_ids is None

    def test_track_ids_alone_accepted(self) -> None:
        c = TrackFeaturesCreate.model_validate({"track_ids": [146, 147]})
        assert c.track_ids == [146, 147]
        assert c.track_id is None

    def test_empty_track_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match=r"at least one"):
            TrackFeaturesCreate.model_validate({"track_ids": []})

    def test_default_level_3(self) -> None:
        c = TrackFeaturesCreate.model_validate({"track_id": 1})
        assert c.level == 3

    def test_level_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TrackFeaturesCreate.model_validate({"track_id": 1, "level": 0})
        with pytest.raises(ValidationError):
            TrackFeaturesCreate.model_validate({"track_id": 1, "level": 6})
