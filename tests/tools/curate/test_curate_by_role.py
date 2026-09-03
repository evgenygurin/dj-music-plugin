"""Task 1: TrackFeatureFilters + Preset — failing test."""

from __future__ import annotations


def test_track_feature_filters_all_fields_optional() -> None:
    from app.schemas.curate import Preset, TrackFeatureFilters

    f = TrackFeatureFilters(bpm__range=(126, 133), energy_low__gte=0.4)
    assert f.bpm__range == (126, 133)
    assert f.key_code__in is None
    # preset defaults
    assert Preset.liebing_hypnotic.value == "liebing_hypnotic"


def test_track_feature_filters_83_fields_accessible() -> None:
    """All 83 columns of track_audio_features_computed are available as Optional."""
    from app.schemas.curate import TrackFeatureFilters

    # пустой конструктор — все None/default
    f = TrackFeatureFilters()
    assert f.bpm__range is None
    # проверяем, что модель имеет >=83 поля-фильтра
    fields = set(TrackFeatureFilters.model_fields.keys())
    # ключевые поля из брифа должны существовать
    for name in [
        "bpm__range",
        "integrated_lufs__range",
        "energy_low__gte",
        "spectral_centroid_hz__lte",
        "key_code__in",
        "atonality__eq",
        "phrase_boundaries_ms__isnull",
        "variable_tempo__eq",
    ]:
        assert name in fields, f"missing {name}"
    assert len(fields) >= 83, f"expected >=83 filter fields, got {len(fields)}"


def test_preset_values() -> None:
    from app.schemas.curate import Preset

    assert Preset.liebing_industrial.value == "liebing_industrial"
    assert Preset.peak_time.value == "peak_time"
    assert Preset.custom.value == "custom"


def test_curate_by_role_result_shape() -> None:
    from app.schemas.curate import CurateByRoleResult, TrackRef

    r = CurateByRoleResult(tracks=[TrackRef(id=1, title="Test")])
    assert len(r.tracks) == 1
    assert r.tracks[0].id == 1
