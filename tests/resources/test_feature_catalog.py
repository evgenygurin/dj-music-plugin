# tests/resources/test_feature_catalog.py
from __future__ import annotations

from app.models.track_features import TrackAudioFeaturesComputed
from app.models.transition import Transition
from app.resources._feature_catalog import (
    TRACK_FEATURE_CATALOG,
    TRANSITION_FEATURE_CATALOG,
    describe_field,
)


def test_track_feature_catalog_covers_every_model_column() -> None:
    model_columns = {c.name for c in TrackAudioFeaturesComputed.__table__.columns}
    catalog_columns = set(TRACK_FEATURE_CATALOG.keys())
    missing = model_columns - catalog_columns
    assert not missing, f"missing catalog entries for columns: {sorted(missing)}"


def test_transition_feature_catalog_covers_every_score_column() -> None:
    model_columns = {c.name for c in Transition.__table__.columns}
    catalog_columns = set(TRANSITION_FEATURE_CATALOG.keys())
    missing = model_columns - catalog_columns
    assert not missing, f"missing catalog entries for columns: {sorted(missing)}"


def test_every_catalog_entry_has_group_label_description() -> None:
    for catalog in (TRACK_FEATURE_CATALOG, TRANSITION_FEATURE_CATALOG):
        for name, entry in catalog.items():
            assert entry["group"], f"{name} missing group"
            assert entry["label"], f"{name} missing label"
            assert entry["description"], f"{name} missing description"


def test_describe_field_wraps_value_with_metadata() -> None:
    described = describe_field(TRACK_FEATURE_CATALOG, "bpm", 128.4)
    assert described == {
        "value": 128.4,
        "label": TRACK_FEATURE_CATALOG["bpm"]["label"],
        "description": TRACK_FEATURE_CATALOG["bpm"]["description"],
        "group": TRACK_FEATURE_CATALOG["bpm"]["group"],
    }


def test_describe_field_handles_null_value() -> None:
    described = describe_field(TRACK_FEATURE_CATALOG, "beatport_isrc", None)
    assert described["value"] is None
    assert described["label"] == TRACK_FEATURE_CATALOG["beatport_isrc"]["label"]


def test_describe_field_unknown_column_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        describe_field(TRACK_FEATURE_CATALOG, "not_a_real_column", 1)
