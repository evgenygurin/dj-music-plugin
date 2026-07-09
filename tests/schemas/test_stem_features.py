from __future__ import annotations

import pytest

from app.models.stem_features import StemFeatures
from app.schemas.stem_features import StemFeaturesView


def test_stem_features_view_from_orm():
    row = StemFeatures(
        id=1,
        track_id=42,
        stem_name="drums",
        bpm=135.0,
        key_code=7,
        integrated_lufs=-8.5,
        kick_prominence=0.9,
    )
    view = StemFeaturesView.model_validate(row)
    assert view.track_id == 42
    assert view.stem_name == "drums"
    assert view.bpm == 135.0
    assert view.key_code == 7


def test_stem_features_filter_forbids_unknown():
    with pytest.raises(ValueError):
        from app.schemas.stem_features import StemFeaturesFilter
        StemFeaturesFilter(random_field__eq=1)
